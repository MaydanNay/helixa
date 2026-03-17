# app.services.services/stage_generators.py

from jsonschema import ValidationError, SchemaError
import logging

from app.services.utils import _normalize_response_for_field, _unwrap_llm_response
from app.services.validation.schema_utils import wrap_schema_if_needed, validate_and_parse_response


async def generate_field(
    sys_inst, 
    prompt, 
    schema, 
    field_name,
    w_name, 
    llm_call_fn
):
    """LLM call -> strict validate -> return normalized (obj, data) or raise.
    """
    wrapper_schema = wrap_schema_if_needed(field_name, schema)
    resp = await llm_call_fn(sys_inst, prompt, wrapper_schema, field_name)
    
    import asyncio
    
    MAX_VALIDATION_RETRIES = 3
    parsed = None
    
    for attempt in range(MAX_VALIDATION_RETRIES + 1):
        try:
            parsed = await validate_and_parse_response(resp, wrapper_schema, field_name)
            break
        except (ValidationError, ValueError) as e:
            if attempt == MAX_VALIDATION_RETRIES:
                raise  # Final attempt failed
            
            prev = _unwrap_llm_response(resp)
            validation_msg = str(e)
            
            logging.warning(" - [AUTOFIX] Schema validation failed for %s: %s; instance_preview=%s",
                            field_name, e.message if hasattr(e, "message") else str(e),
                            str(parsed)[:200] if parsed else None)
            logging.warning(" - [AUTOFIX] LLM failed validation for %s on attempt %d. Error: %s", field_name, attempt + 1, validation_msg)

            
            # Give the LLM breathing room
            await asyncio.sleep(2 ** attempt)
            
            corr_prompt = (
                f"Attempt {attempt + 1} failed. Предыдущий ответ не прошёл валидацию. Используй предыдущий вывод и верни СТРОГО валидный JSON по схеме (без пояснений).\n\n"
                f"ERROR: {validation_msg}\n\n"
                "Пожалуйста, добавь недостающие поля или исправь структуру. Return ONLY corrected JSON. Do NOT add extra commentary.\n\n"
                "Используй предыдущий вывод как источник, исправь структуру/форматирование так, чтобы JSON полностью валидировалcя по схеме."
            )
            # Re-call the LLM to fix its own output
            resp = await llm_call_fn(sys_inst, corr_prompt + "\n\n" + prev, wrapper_schema, field_name)

    obj, data = _normalize_response_for_field(parsed, field_name)
    if data is None:
        raise ValueError(f"{field_name} not found after validation")
    return obj, data
