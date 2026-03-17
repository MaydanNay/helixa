# app.services.llm/client.py

import logging
from time import perf_counter
from typing import Any, Dict, Optional

from app.services.alem_client import alem_client as alem_plus_client


async def call_responses_api(
    system_instruction: str, 
    user_prompt: str, 
    wrapper_schema: Any, 
    wrapper_name: str = "core", 
    provider: str = "alemllm",
    request_timeout: Optional[float] = None,
    temperature: float = 0.7,
    **kwargs
) -> Dict[str, Any]:
    """Унифицированная обёртка использования провайдера LLM 
    с логированием и таймингом.
    """
    start = perf_counter()
    
    actual_model = "gpt-oss" if provider in ("gpt", "gpt_oss") else provider
    
    if not alem_plus_client or not getattr(alem_plus_client, "is_configured", False):
        logging.warning("call_responses_api: alem client not configured")
        return {"ok": False, "error": "Alem client not configured"}

    logging.info("LLM call start: provider=%s wrapper=%s", actual_model, wrapper_name)
    try:
        res = await alem_plus_client.create_structured_completion(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            json_schema=wrapper_schema,
            wrapper_name=wrapper_name,
            model=actual_model,
            request_timeout=request_timeout,
            temperature=temperature,
            **kwargs
        )
        
        dur = perf_counter() - start
        if res.get("ok"):
            logging.info("LLM call finished: provider=%s wrapper=%s dur=%.3fs", actual_model, wrapper_name, dur)
        else:
            logging.warning("LLM call returned ok=False: provider=%s err=%s", actual_model, res.get("error"))
            
        return res
    except Exception as e:
        dur = perf_counter() - start
        logging.exception("call_responses_api wrapper failed after %.3fs: %s", dur, e)
        return {"ok": False, "error": str(e)}

