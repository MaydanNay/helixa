import re
import json
import asyncio
import logging
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Single source of truth for stage ordering — import from here, don't redefine
STAGE_ORDER = [
    "demographics", "psychology", "health", "biography",
    "family", "experience", "behavioral", "sociology",
    "voice", "financial", "memory", "private", 
    "editor"
]

def extract_stage(obj: Any, key: str) -> Any:
    """
    Extracts the actual stage data from LLM wrapper response.
    Handles patterns: {key: [item]}, {key: item}, [item], or raw dict.
    Eliminates 15+ copy-paste instances of the same extraction logic.
    """
    if isinstance(obj, dict) and key in obj:
        val = obj[key]
        return val[0] if isinstance(val, list) and val else val
    if isinstance(obj, list) and obj:
        return obj[0]
    return obj



# --- From community_agents/utils.py ---

def _truncate(s, n=500):
    try:
        s = str(s)
        return s if len(s) <= n else s[:n] + "...(truncated)"
    except Exception:
        return "(unserializable)"

def _unwrap_llm_response(resp):
    """Превращает ответ wrapper-а в текст/объект."""
    try:
        if isinstance(resp, dict):
            # If it's a wrapper dict, extract string
            out = resp.get("output_text") or resp.get("content")
            if out:
                return out
            # If it contains raw
            raw = resp.get("raw")
            if raw is not None:
                try:
                    return json.dumps(raw, ensure_ascii=False)
                except Exception:
                    return str(raw)
            # If it's a pure dictionary without wrapper keys, it might be the deserialized payload already
            if "ok" not in resp and "output_text" not in resp and "content" not in resp:
                return json.dumps(resp, ensure_ascii=False)
            
            return json.dumps(resp, ensure_ascii=False)
        return resp
    except Exception:
        return str(resp)

def _normalize_response_for_field(resp_obj, field_name):
    """Нормализует варианты ответов LLM для поля."""
    if isinstance(resp_obj, dict) and field_name in resp_obj:
        return resp_obj, resp_obj.get(field_name)
    if isinstance(resp_obj, list):
        if len(resp_obj) == 1 and isinstance(resp_obj[0], dict) and field_name in resp_obj[0]:
            return resp_obj[0], resp_obj[0].get(field_name)
        return {field_name: resp_obj}, resp_obj
    if isinstance(resp_obj, str):
        try:
            parsed = json.loads(resp_obj)
            return _normalize_response_for_field(parsed, field_name)
        except Exception:
            pass
    return {"note": f"{field_name}_generation_error", "raw": resp_obj}, None

def extract_agents_from_response(resp: Any) -> Optional[List[Dict]]:
    """Извлечение списка агентов или объектов из ответа."""
    # 1) Try output_parsed
    parsed = getattr(resp, "output_parsed", None)
    if parsed is not None:
        return _unwrap_list(parsed)

    # 2) output_text
    out_text = getattr(resp, "output_text", None) if not isinstance(resp, dict) else resp.get("output_text")
    if out_text:
        parsed_json = _try_load_json(out_text)
        if parsed_json is not None:
            return _unwrap_list(parsed_json)

    # 3) regex fallback
    combined = out_text or str(resp)
    combined = re.sub(r"(?is)<think>.*?</think>", "", combined)
    
    m = re.search(r'(\{[\s\S]*?\}|\[[\s\S]*?\])', combined, flags=re.S)
    if m:
        try:
            parsed_json = json.loads(m.group(1))
            return _unwrap_list(parsed_json)
        except Exception:
            pass

    return None

def _try_load_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

def _unwrap_list(parsed: Any) -> Optional[List[Dict]]:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for k in ["agents", "items", "results"]:
            if k in parsed and isinstance(parsed[k], list):
                return parsed[k]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return None

def calculate_biorhythms(chronotype: str) -> List[float]:
    """Расчет циклов энергии на 24 часа."""
    chr_type = str(chronotype).lower()
    energy_cycle = []
    for h in range(24):
        val = 0.5
        if chr_type == "lark":
            if 6 <= h <= 14: val = 0.95
            elif 14 < h <= 21: val = 0.6
            else: val = 0.1
        elif chr_type == "owl":
            if 16 <= h <= 23 or 0 <= h <= 2: val = 0.95
            elif 11 <= h < 16: val = 0.6
            else: val = 0.1
        else: 
            if 8 <= h <= 19: val = 0.9
            elif 7 <= h < 8 or 19 < h <= 23: val = 0.6
            else: val = 0.1
        energy_cycle.append(val)
    return energy_cycle

# --- From community_agents/llm_parsing.py ---

def extract_json_candidate(text: str) -> Optional[str]:
    if not isinstance(text, str): return None
    txt = text.strip()
    txt = re.sub(r"(?is)<think>.*?</think>", "", txt)
    txt = re.sub(r"(?is)<pre[^>]*>\s*<code[^>]*>", "", txt)
    txt = re.sub(r"(?is)</code>\s*</pre>", "", txt)
    txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s*```$", "", txt)
    
    # If multiple candidates exist, we try to pick the largest one that looks like a root object
    first_curly = txt.find('{')
    first_sq = txt.find('[')
    starts = [i for i in (first_curly, first_sq) if i != -1]
    if not starts: return None
    start = min(starts)
    opening = txt[start]
    closing = '}' if opening == '{' else ']'
    
    # NEW: Better handling of nested structures, strings, and trailing text.
    # We find the matching closing character by balancing braces/brackets,
    # while correctly ignoring characters inside double-quoted strings.
    depth = 0
    in_string = False
    escaped = False
    last_idx = -1
    
    for i in range(start, len(txt)):
        char = txt[i]
        
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
                escaped = False
            elif char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    last_idx = i
                    break
    
    if last_idx != -1:
        return txt[start:last_idx+1].strip()
        
    # Fallback to rfind if balancing fails for some reason
    last = txt.rfind(closing)
    if last != -1 and last > start:
        return txt[start:last+1].strip()
    return None

def normalize_llm_json_text(raw_text: str) -> Tuple[str, Optional[dict]]:
    if not raw_text: return ("", None)
    blob = extract_json_candidate(raw_text)
    if not blob: return (raw_text, None)
    try:
        obj = json.loads(blob)
        return (json.dumps(obj, ensure_ascii=False), obj)
    except json.JSONDecodeError:
        # Attempt basic repairs: remove trailing commas before closing braces/brackets
        repaired_blob = re.sub(r',\s*([\]}])', r'\1', blob)
        try:
            obj = json.loads(repaired_blob)
            return (json.dumps(obj, ensure_ascii=False), obj)
        except Exception:
            pass
            
        # Attempt to append missing closing characters (often happens if LLM generation was truncated)
        for suffix in ["}", "]}", "}}", "}]}", "]}}", "}}}"]:
            try:
                obj = json.loads(repaired_blob + suffix)
                return (json.dumps(obj, ensure_ascii=False), obj)
            except Exception:
                pass
    except Exception:
        pass
    return (raw_text, None)

def _resp_to_parsed(resp):
    txt = _unwrap_llm_response(resp)
    if not isinstance(txt, str): return txt
    norm_text, parsed_obj = normalize_llm_json_text(txt)
    if parsed_obj is not None: return parsed_obj
    try:
        return extract_agents_from_response(norm_text)
    except Exception:
        return norm_text

async def call_llm_with_retries(messages: List[Dict], provider: str = "gpt-oss", temperature: float = 0.7) -> str:
    """
    Simplified LLM helper for raw text generation with basic retry logic.
    Reuses AlemClient.create_chat_completion.
    """
    from app.services.alem_client import alem_client
    
    # Simple retry loop
    for attempt in range(3):
        try:
            res = await alem_client.create_chat_completion(
                messages=messages,
                model=provider,
                temperature=temperature
            )
            if res.get("ok"):
                return res.get("output_text", "")
            
            logger.warning(f"call_llm_with_retries attempt {attempt+1} failed: {res.get('error')}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"call_llm_with_retries unexpected error: {e}")
            await asyncio.sleep(1)
            
    return "Error: LLM service unavailable after retries."
