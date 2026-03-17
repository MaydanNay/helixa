# app.services.validation/schema_utils.py

import json
import logging
import jsonschema
from jsonschema import ValidationError, SchemaError

from app.services.utils import extract_agents_from_response
from app.services.utils import _resp_to_parsed, _truncate, _unwrap_llm_response


def ensure_schema_valid(schema, name: str) -> dict:
    """Гарантирует, что schema — dict пригодный для jsonschema.validate.
    Если schema — JSON-string попытаемся распарсить, если пустая/некорректная — вернём permissive fallback.
    Логируем всё подозрительное.
    """
    try:
        if isinstance(schema, str):
            s = schema.strip()
            if not s:
                logging.warning("Schema for %s is empty string -> replacing with permissive object", name)
                return {"type": "object"}
            try:
                parsed = json.loads(s)
                if not isinstance(parsed, dict):
                    logging.warning("Schema for %s parsed from string but not dict -> using permissive object", name)
                    return {"type": "object"}
                schema = parsed
            except Exception:
                logging.warning("Schema for %s is non-json string -> using permissive object", name)
                return {"type": "object"}

        if not isinstance(schema, dict):
            logging.warning("Schema for %s is not a dict (%r) -> using permissive object", name, type(schema))
            return {"type": "object"}

        # quick sanity: avoid passing empty string as nested property
        return schema
    except Exception as e:
        logging.exception("ensure_schema_valid failed for %s: %s", name, e)
        return {"type": "object"}


def wrap_schema_if_needed(wrapper_name: str, schema: dict) -> dict:
    """Если schema уже содержит wrapper_name (в properties или required) — возвращаем как есть.
    Иначе — оборачиваем schema в объект { wrapper_name: schema } и запрещаем additionalProperties.
    """
    # нормализуем: если schema приходит как JSON-string — попробуем распарсить
    try:
        if isinstance(schema, str) and schema.strip():
            try:
                parsed = json.loads(schema)
                schema = parsed
            except Exception:
                # если это пустая строка или невалидный JSON — заменяем на permissive schema
                schema = {"type": "object"}

        if not isinstance(schema, dict):
            # guard: если (всё ещё) не dict — делаем простую object-схему для внутреннего значения
            inner = {"type": "object"} if schema is None or schema == "" else schema
            return {
                "type": "object",
                "properties": {wrapper_name: inner},
                "required": [wrapper_name],
                "additionalProperties": False
            }

        props = schema.get("properties", {})
        req = schema.get("required", []) or []
        if wrapper_name in props or wrapper_name in req:
            return schema
    except Exception:
        return {
            "type": "object",
            "properties": {wrapper_name: {"type": "object"}},
            "required": [wrapper_name],
            "additionalProperties": False
        }

    return {
        "type": "object",
        "properties": {wrapper_name: schema},
        "required": [wrapper_name],
        "additionalProperties": False
    }


def _coerce_types(instance, schema):
    """
    Recursively coerces types to match schema where possible:
    1. null -> "" for string fields
    2. null -> [] for array fields (if optional/nullable issues)
    3. dict -> [dict] for array fields (common LLM mistake for single-item lists)
    """
    if schema is None:
        return instance

    s_type = schema.get("type") if isinstance(schema, dict) else None

    # Union types (e.g. ["string", "null"], ["string", "boolean", "null"])
    if isinstance(s_type, list):
        if instance is None and "null" in s_type:
            return None
        # Boolean given but string expected (not boolean allowed) → cast to "yes"/"no"
        if isinstance(instance, bool) and "boolean" not in s_type and "string" in s_type:
            return "yes" if instance else "no"
        if instance is None and "integer" in s_type:
            return 0
        if "integer" in s_type and isinstance(instance, (int, float)):
            return int(round(float(instance)))
        return instance

    # 1. String: null -> ""
    if s_type == "string":
        if instance is None:
            return ""
        # Boolean given for a strict string field → cast to "yes"/"no"
        if isinstance(instance, bool):
            return "yes" if instance else "no"
        return instance

    # 2. Array: dict -> [dict] coercion + minItems/maxItems handling
    if s_type == "array":
        if isinstance(instance, dict):
            # The LLM returned a single object instead of a list of objects. Wrap it.
            instance = [instance]
        
        if isinstance(instance, list):
            items_schema = schema.get("items") if isinstance(schema, dict) else None
            for i, item in enumerate(instance):
                instance[i] = _coerce_types(item, items_schema or {})
            
            # Handle minItems/maxItems constraints (especially for energy_curve arrays)
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            
            if min_items is not None and len(instance) < min_items:
                # Pad array with last value or default
                default_val = instance[-1] if instance else _get_default_for_schema(items_schema or {})
                while len(instance) < min_items:
                    instance.append(default_val)
                logging.debug("Padded array from %d to %d items", len(instance) - (min_items - len(instance)), min_items)
            
            if max_items is not None and len(instance) > max_items:
                # Truncate array
                instance = instance[:max_items]
                logging.debug("Truncated array to %d items", max_items)
            
            return instance

    # 3. Integer/Number: handle coercion and rounding
    if s_type == "integer":
        if isinstance(instance, (int, float)):
            return int(round(float(instance)))
        if isinstance(instance, str):
            try:
                return int(round(float(instance)))
            except ValueError:
                return instance
        return instance

    if s_type == "number":
        if isinstance(instance, (int, float)):
            return float(instance)
        if isinstance(instance, str):
            try:
                return float(instance)
            except ValueError:
                return instance
        return instance

    # 4. Object: recurse or handle scalar-to-object mismatch
    if s_type == "object":
        if instance is None:
            instance = {}
        if isinstance(instance, dict):
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            for k, v in list(instance.items()):
                prop_schema = props.get(k) if isinstance(props, dict) else None
                instance[k] = _coerce_types(v, prop_schema or {})
            return instance
        elif instance is not None:
            # LLM provided a scalar for an object field. 
            # Strategy: if it's a number/str, we might want to put it into the first required property?
            # For now, just logging and doing a simple wrap if possible.
            logging.debug("LLM provided scalar %r for object-type field. Schema: %r", instance, schema)
            # Special case: if schema has only one number field (like expenses), maybe try to fit it?
            # For now, return as is and let _fill_missing_required handle it later or fail validation.
            return instance

    return instance


def _get_default_for_schema(schema):
    """Returns a safe default value for a given schema node."""
    if not isinstance(schema, dict):
        return None
    
    # 1. Enum: always pick the first valid option
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    # 2. Type handling
    t = schema.get("type")
    
    # Handle union types like ['integer', 'null'] -> prefer null
    if isinstance(t, list):
        if "null" in t:
            return None
        # if not nullable, pick the first type and recurse
        t = t[0] if t else "string"

    if t == "string":
        return ""
    elif t == "array":
        return []
    elif t == "object":
        return {}
    elif t == "boolean":
        return False
    elif t in ("integer", "number"):
        return 0
    elif t == "null":
        return None
    
    return None


def _fill_missing_required(instance, schema):
    """Fill missing required keys in `instance` according to `schema` with safe defaults.
    Recursively ensures that if a required object is missing, its own required fields are also filled.
    """
    try:
        if not isinstance(schema, dict): 
            return instance
            
        # 1. If instance is None or wrong type (and not nullable), get full default
        if instance is None:
            s_type = schema.get("type")
            if isinstance(s_type, list) and "null" in s_type:
                return None
            return _get_default_for_schema(schema)

        # 2. If it is an object, fill missing keys
        if schema.get("type") == "object":
            if not isinstance(instance, dict):
                # Major type mismatch! If we can't coerce, we might have to replace with default.
                # But validation usually catches this. Let's try to be safe.
                return instance
            
            props = schema.get("properties", {}) or {}
            req = schema.get("required", []) or []

            # fill missing required fields
            for key in req:
                if key not in instance:
                    if key in props:
                        # Recursively get default for the missing field
                        instance[key] = _get_default_for_schema(props[key])
                        # New: immediately recurse into the newly created default if it's a dict
                        if isinstance(instance[key], dict):
                             instance[key] = _fill_missing_required(instance[key], props[key])
                else:
                    # key exists, recurse into it
                    if key in props:
                        instance[key] = _fill_missing_required(instance[key], props[key])
            
            return instance

        # 3. If it is an array, recurse into items
        if schema.get("type") == "array" and isinstance(instance, list):
            items_schema = schema.get("items")
            if isinstance(items_schema, dict):
                for i, item in enumerate(instance):
                    instance[i] = _fill_missing_required(item, items_schema)
            return instance

    except Exception:
        logging.exception("Failed to fill missing required fields")
    return instance


def _prune_extra_fields(instance, schema):
    """Recursively remove fields from instance that are not in schema properties."""
    try:
        if not isinstance(schema, dict) or not isinstance(instance, dict):
            return instance

        props = schema.get("properties")
        # If properties is not defined or is empty, we act conservatively:
        # If 'additionalProperties' is explicitly False, we must clear dict.
        # But here we simply rely on: if 'properties' IS defined, we prune everything else.
        if isinstance(props, dict):
            allowed_keys = set(props.keys())
            # Safe deletion
            for k in list(instance.keys()):
                if k not in allowed_keys:
                    # Note: We don't check 'patternProperties' here, assuming simple schemas.
                    del instance[k]
        
        # recurse
        for k, v in instance.items():
            if not isinstance(props, dict): 
                continue
            
            p_schema = props.get(k)
            if not isinstance(p_schema, dict):
                continue
                
            if isinstance(v, dict):
                _prune_extra_fields(v, p_schema)
            elif isinstance(v, list) and "items" in p_schema:
                item_schema = p_schema["items"]
                if isinstance(item_schema, dict):
                    for item in v:
                        if isinstance(item, dict):
                            _prune_extra_fields(item, item_schema)

    except Exception:
        logging.exception("Failed to prune extra fields")
    return instance


def _fix_enum_values(instance, schema):
    """Recursively checks enum constraints and fixes invalid values.
    Supports case-insensitive matching and handles empty strings.
    """
    try:
        if not isinstance(schema, dict):
            return instance

        # If current node is an enum and instance is a scalar (str/int/etc)
        if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
            # If value is invalid
            if instance not in schema["enum"]:
                # Try case-insensitive match for strings
                if isinstance(instance, str):
                    low_val = instance.strip().lower()
                    for enum_val in schema["enum"]:
                        if isinstance(enum_val, str) and enum_val.lower() == low_val:
                            return enum_val
                
                # If still invalid or empty string
                # Strategy: 
                # 1. Check if 'other' (case-insensitive) is an option?
                for enum_val in schema["enum"]:
                    if isinstance(enum_val, str) and enum_val.lower() == "other":
                        return enum_val
                
                # 2. Return first valid option (safe fallback)
                return schema["enum"][0]
        
        # Recurse
        if isinstance(instance, dict):
            props = schema.get("properties", {})
            if isinstance(props, dict):
                for k, v in instance.items():
                    if k in props:
                         instance[k] = _fix_enum_values(v, props[k])
        
        elif isinstance(instance, list):
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                 for i, item in enumerate(instance):
                     instance[i] = _fix_enum_values(item, item_schema)

    except Exception:
        logging.exception("Failed to fix enum values")
    return instance


async def validate_and_parse_response(llm_resp, schema, wrapper_name):
    """Разбирает llm_resp -> python объект и проверяет json-schema.
    Возвращает parsed object (python) при успехе, иначе бросает ValidationError/ValueError с компактным сообщением.
    """
    if isinstance(llm_resp, dict) and llm_resp.get("ok") is False:
        err = llm_resp.get("error") or ""
        raw = llm_resp.get("raw")
        err_display = err if err.strip() else "LLM API returned empty/no response"
        logging.warning(
            "LLM responded with ok=False for %s: err=%s raw=%s",
            wrapper_name, _truncate(err_display), _truncate(raw)
        )
        raise ValidationError(f"llm_error: {err_display} raw: {_truncate(raw)}")

    # Покажем большой raw-preview для дебага (но не схему)
    raw_preview = _truncate(_unwrap_llm_response(llm_resp), 2000)
    logging.debug("LLM raw preview for %s: %s", wrapper_name, raw_preview)

    parsed = _resp_to_parsed(llm_resp)

    # Custom Auto-Heal for Demographics where 'name' is often returned instead of 'agent_name'
    if wrapper_name == "core_demographics":
        # Handle cases where it is wrapped in dict
        if isinstance(parsed, dict) and "core_demographics" in parsed:
            demo_list = parsed["core_demographics"]
            if isinstance(demo_list, list) and len(demo_list) > 0:
                demo_obj = demo_list[0]
                if isinstance(demo_obj, dict):
                    if "name" in demo_obj and "agent_name" not in demo_obj:
                        demo_obj["agent_name"] = demo_obj.pop("name")
                    if "role" in demo_obj and "agent_role" not in demo_obj:
                        demo_obj["agent_role"] = demo_obj.pop("role")
                    if "agent_profile" not in demo_obj:
                        demo_obj["agent_profile"] = "Synthesized AI Agent profile."
        # Handle cases where it is not wrapped (pure list)
        elif isinstance(parsed, list) and len(parsed) > 0:
            demo_obj = parsed[0]
            if isinstance(demo_obj, dict):
                if "name" in demo_obj and "agent_name" not in demo_obj:
                    demo_obj["agent_name"] = demo_obj.pop("name")
                if "role" in demo_obj and "agent_role" not in demo_obj:
                    demo_obj["agent_role"] = demo_obj.pop("role")
                if "agent_profile" not in demo_obj:
                    demo_obj["agent_profile"] = "Synthesized AI Agent profile."
        # Handle cases where it is an unwrapped pure dict
        elif isinstance(parsed, dict) and "name" in parsed and "agent_name" not in parsed:
            parsed["agent_name"] = parsed.pop("name")
            if "role" in parsed and "agent_role" not in parsed:
                parsed["agent_role"] = parsed.pop("role")
            if "agent_profile" not in parsed:
                parsed["agent_profile"] = "Synthesized AI Agent profile."

    # Custom Auto-Heal for Psychology where 'core_values' is often placed inside 'personality'
    if wrapper_name == "core_psychology":
        psyc_items = parsed.get("core_psychology", parsed) if isinstance(parsed, dict) else parsed
        # If it's a single dict, wrap it in a list so the loop processes it, otherwise iterate
        psyc_list = [psyc_items] if isinstance(psyc_items, dict) else (psyc_items if isinstance(psyc_items, list) else [])
        for psyc_obj in psyc_list:
            if isinstance(psyc_obj, dict):
                # Flatten double wrapper if it exists inside the object
                for evil_key in ["psychology", "core_psychology", "data", "attributes"]:
                    if evil_key in psyc_obj and "religion" not in psyc_obj:
                        inner = psyc_obj.pop(evil_key)
                        if isinstance(inner, dict):
                            psyc_obj.update(inner)
                        
                pers = psyc_obj.get("personality", {})
                if isinstance(pers, dict):
                    # If core_values is missing at root, but exists in personality (as core_values or values)
                    if "core_values" not in psyc_obj:
                        val = pers.get("core_values") or pers.get("values")
                        if val:
                            psyc_obj["core_values"] = val
                    
                    # Ensure personality has 'values' (required by schema)
                    if "values" not in pers:
                        val = psyc_obj.get("core_values") or ["Empathetic", "Rational"]
                        pers["values"] = val

    # Custom Auto-Heal for Sociology
    if wrapper_name == "sociology":
        soc_items = parsed.get("sociology", parsed) if isinstance(parsed, dict) else parsed
        soc_list = [soc_items] if isinstance(soc_items, dict) else (soc_items if isinstance(soc_items, list) else [])
        for soc_obj in soc_list:
            if isinstance(soc_obj, dict):
                # Fix Part 1 Communication
                if "communication" in soc_obj:
                    comm = soc_obj["communication"]
                    if isinstance(comm, dict):
                        if "style" in comm and "communication_style" not in comm:
                            comm["communication_style"] = comm.pop("style")
                # Fix missing social_and_relationships wrapper often omitted by LLM
                elif any(k in soc_obj for k in ["social_circle_size", "civic_engagement", "political_views"]):
                    # Move these keys into a new 'social_and_relationships' dict
                    keys_to_move = ["social_circle_size", "civic_engagement", "political_views", "cultural_values"]
                    sar = {}
                    for k in keys_to_move:
                        if k in soc_obj:
                            sar[k] = soc_obj.pop(k)
                    soc_obj["social_and_relationships"] = sar

    # Custom Auto-Heal for Financial
    if wrapper_name == "family":
        fam_items = parsed.get("family", parsed) if isinstance(parsed, dict) else parsed
        fam_list = [fam_items] if isinstance(fam_items, dict) else (fam_items if isinstance(fam_items, list) else [])
        for fam_obj in fam_list:
            if isinstance(fam_obj, dict):
                for list_key in ["immediate_family", "extended_family"]:
                    members = fam_obj.get(list_key, [])
                    if isinstance(members, list):
                        for member in members:
                            if isinstance(member, dict):
                                g = member.get("gender")
                                if not g or (isinstance(g, str) and not g.strip()):
                                    member["gender"] = "Other"

    # Custom Auto-Heal for Financial
    if wrapper_name == "financial":
        fin_items = parsed.get("financial", parsed) if isinstance(parsed, dict) else parsed
        fin_list = [fin_items] if isinstance(fin_items, dict) else (fin_items if isinstance(fin_items, list) else [])
        for fin_obj in fin_list:
            if isinstance(fin_obj, dict):
                # Fix goals wrapper if missing
                if "financial_goals" in fin_obj and "goals" not in fin_obj:
                    fin_obj["goals"] = {"financial_goals": fin_obj.pop("financial_goals")}

    # Custom Auto-Heal for Experience
    if wrapper_name == "experience":
        exp_items = parsed.get("experience", parsed) if isinstance(parsed, dict) else parsed
        exp_list = [exp_items] if isinstance(exp_items, dict) else (exp_items if isinstance(exp_items, list) else [])
        for exp_obj in exp_list:
            if isinstance(exp_obj, dict):
                # Map 'tools' to 'tools_used_by' inside capabilities
                caps = exp_obj.get("capabilities", {})
                if isinstance(caps, dict) and "tools" in caps and "tools_used_by" not in caps:
                    caps["tools_used_by"] = caps.pop("tools")

    # Auto-healing: If wrapper_name is missing but content looks like inner object (or is the direct list), wrap it.
    if (isinstance(parsed, dict) and wrapper_name not in parsed) or isinstance(parsed, list):
        # Check if schema expects a wrapper
        if isinstance(schema, dict):
            props = schema.get("properties", {})
            if wrapper_name in props:
                # CRITICAL: Avoid wrapping if this looks like a raw LLM API response metadata dict
                # (which happens if _unwrap_llm_response returned the whole raw dict)
                if any(k in parsed for k in ["choices", "finish_reason", "usage", "model"]):
                    logging.warning("Response for %s looks like raw LLM metadata, not wrapping.", wrapper_name)
                else:
                    # We expect { wrapper_name: ... } but didn't get it.
                    # Let's see if 'parsed' matches the inner schema?
                    # Simple heuristic: wrap it, and check if it should be an array.
                    logging.warning("Response for %s missing root wrapper; auto-wrapping to attempt fix.", wrapper_name)
                    
                    # Ensure we wrap as a list if the schema expects an array
                    prop_schema = props[wrapper_name]
                    if isinstance(prop_schema, dict) and prop_schema.get("type") == "array" and not isinstance(parsed, list):
                        parsed = {wrapper_name: [parsed]}
                    else:
                        parsed = {wrapper_name: parsed}

    # coerce types (nulls -> strings, dict -> list for arrays)
    # NOTE: Run this AFTER auto-healing, so that the structure matches the schema (wrapper present)
    try:
        parsed = _coerce_types(parsed, schema)
    except Exception:
        logging.debug("Coercion of types failed for %s", wrapper_name, exc_info=True)

    # Пробуем валидацию. Если схема невалидна — ловим SchemaError.
    try:
        jsonschema.validate(instance=parsed, schema=schema)
        return parsed
    except SchemaError as se:
        logging.error("Invalid JSON schema for %s: %s", wrapper_name, se)
        logging.debug("Full schema for %s: %r", wrapper_name, schema)
        raise ValueError(f"invalid_schema: {se}")
    except ValidationError as ve:
        msg = getattr(ve, "message", str(ve))
        inst_summary = _truncate(parsed, 300)
        logging.warning("Schema validation failed for %s: %s; instance_preview=%s", wrapper_name, msg, inst_summary)
        
        # Попробуем корректировку: если модель вернула null для текстовых полей — сделаем coercion и попробуем снова.
        try:
            if isinstance(parsed, (dict, list)):
                # deepcopy-safe копия
                parsed_copy = json.loads(json.dumps(parsed, ensure_ascii=False))
                
                # 1. Coerce Types (Null -> Str, Dict -> List)
                coerced = _coerce_types(parsed_copy, schema)
                
                # if changes happened, validate
                try:
                    jsonschema.validate(instance=coerced, schema=schema)
                    logging.info("Validation succeeded for %s after coercing types", wrapper_name)
                    return coerced
                except Exception:
                    pass # Fall through to next step

                # 2. Prune Extra -> Fill Missing -> Fix Enums
                # Prune extra
                pruned = _prune_extra_fields(coerced, schema)
                # Fill missing
                filled = _fill_missing_required(pruned, schema)
                # Fix Enums (New!)
                fixed = _fix_enum_values(filled, schema)
            
                jsonschema.validate(instance=fixed, schema=schema)
                logging.info("Validation succeeded for %s after pruning/filling/fixing", wrapper_name)
                return fixed
                
        except Exception as e2:
             msg2 = getattr(e2, "message", str(e2))
             logging.warning("Deep healing failed for %s: %s", wrapper_name, msg2)
             msg = msg2

        logging.debug("Full LLM raw for %s (truncated 4000): %s", wrapper_name, _truncate(_unwrap_llm_response(llm_resp), 4000))
        raise ValueError(f"schema_validation_error: {msg}")

