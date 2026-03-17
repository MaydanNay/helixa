# app.services.llm/retry.py

import random
import asyncio
import logging

from app.services.utils import _truncate
from app.services.llm.client import call_responses_api


# Fallback chains — on retry, rotate through all available models
# Pattern: after every 2 failed attempts on current model, switch to next
PROVIDER_FALLBACKS = {
    # Primary: gpt-oss → gemma3 → qwen3 (default chain for LLM_PROVIDER=gpt-oss)
    "gpt-oss": ["gpt-oss", "gemma3", "qwen3"],
    "gpt_oss": ["gpt-oss", "gemma3", "qwen3"],  # underscore alias
    "gpt":     ["gpt-oss", "gemma3", "qwen3"],  # short alias

    # Starting from gemma3 → qwen3 → gpt-oss
    "gemma3":  ["gemma3", "qwen3", "gpt-oss"],
    "gemma":   ["gemma3", "qwen3", "gpt-oss"],  # old name alias

    # Starting from qwen3 → gpt-oss → gemma3
    "qwen3":   ["qwen3", "gpt-oss", "gemma3"],

    # Legacy single-model (kept for compatibility)
    "alemllm": ["gpt-oss", "gemma3", "qwen3"],
}

async def call_with_retries(
    sys_inst, 
    u_prompt, 
    w_schema, 
    wrapper_name = "core", 
    attempts = 5, 
    timeout = 500, 
    base_backoff = 1.0, 
    provider: str = "alemllm",
    temperature: float = 0.7,
    **kwargs
):
    """- attempts: number of total attempts
    - timeout: per-attempt timeout seconds
    - base_backoff: base seconds
    - provider: initial provider
    """
    last_err = None
    
    # Determine the sequence of providers to try
    provider_chain = PROVIDER_FALLBACKS.get(provider, [provider])
    
    # We will distribute 'attempts' across the chain. 
    # Usually we want to try the primary a couple of times, then move on.
    # But for simplicity, we can just rotate provider on each attempt if we want, 
    # or try each provider in chain until success.
    
    current_provider_idx = 0
    
    for i in range(1, attempts+1):
        active_provider = provider_chain[current_provider_idx % len(provider_chain)]
        
        try:
            per_call_timeout = max(10, timeout - 5)
            coro = call_responses_api(
                sys_inst, 
                u_prompt, 
                w_schema, 
                wrapper_name = wrapper_name,
                provider = active_provider,
                request_timeout = per_call_timeout,
                temperature = temperature,
                **kwargs
            )
            resp = await asyncio.wait_for(coro, timeout=timeout)
            
            if not resp.get("ok"):
                err = resp.get("error") or "unknown_error"
                logging.warning(
                    "- [RETRY] LLM %s (attempt=%d, provider=%s) failed: %s",
                    wrapper_name, i, active_provider, _truncate(err)
                )
                last_err = RuntimeError(err)
                
                # Switch to next provider in chain only after 2 attempts on same provider
                if i % 2 == 0:
                    current_provider_idx += 1
                
                delay = base_backoff * (1.5 ** (i-1)) + random.uniform(0.5, 2.5)
                await asyncio.sleep(min(delay, 20)) # Cap delay
                continue
                
            return resp
            
        except asyncio.TimeoutError:
            logging.warning("- [RETRY] LLM %s (attempt=%d, provider=%s) timed out", wrapper_name, i, active_provider)
            last_err = asyncio.TimeoutError()
            
            if i % 2 == 0:
                current_provider_idx += 1
            
            delay = base_backoff * (1.5 ** (i-1)) + random.uniform(0.5, 2.5)
            await asyncio.sleep(min(delay, 20))
            continue
        except Exception as e:
            logging.exception("[RETRY] LLM %s (attempt=%d, provider=%s) failed: %s", wrapper_name, i, active_provider, e)
            last_err = e
            
            if i % 2 == 0:
                current_provider_idx += 1
                
            delay = base_backoff * (1.5 ** (i-1)) + random.uniform(0.5, 2.5)
            await asyncio.sleep(min(delay, 20))
            continue

    if last_err is None:
        raise RuntimeError("call_with_retries: unknown failure")
    raise RuntimeError(f"call_with_retries failed after {attempts} attempts; last_err={repr(last_err)}")

