import asyncio
import json
import logging
import httpx
from typing import Any, Dict, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class AlemClient:
    def __init__(self):
        self.keys = {
            "alemllm": getattr(settings, "alem_api_key", None) or getattr(settings, "llm_api_key", None),
            "gemma": getattr(settings, "gemma_api_key", None),
            "gemma3": getattr(settings, "gemma_api_key", None),
            "qwen3": getattr(settings, "qwen_api_key", None),
            "gpt_oss": getattr(settings, "gpt_oss_api_key", None),
            "gpt-oss": getattr(settings, "gpt_oss_api_key", None),
            "gpt-oos": getattr(settings, "gpt_oss_api_key", None),
            "gpt-5.4": getattr(settings, "alem_api_key", None),
            "o4-mini": getattr(settings, "openai_api_key", None),
            "qwen-3-70b": getattr(settings, "qwen_api_key", None),
            "gpt-5-nano": getattr(settings, "openai_api_key", None) or getattr(settings, "alem_api_key", None),
        }
        self.api_base = "https://llm.alem.ai/v1/chat/completions"
        self.is_configured = any(self.keys.values())

    async def create_chat_completion(
        self,
        system_instruction: str = None,
        user_prompt: str = None,
        messages: list = None,
        model: str = "alemllm",
        temperature: float = 0.0,
        max_tokens: int = 8000,
        extra_body: Dict[str, Any] = None,
        request_timeout: Optional[float] = 300.0
    ) -> Dict[str, Any]:
        """
        Универсальный метод для вызова Alem Plus API.
        Поддерживает как упрощенный (sys/user), так и OpenAI-стиль (messages).
        """
        api_key = self.keys.get(model) or self.keys.get("alemllm")
        if not api_key:
            return {"ok": False, "error": f"API key not configured for model {model}"}
            
        if not messages:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            if user_prompt:
                messages.append({"role": "user", "content": user_prompt})
 
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Use local_llm_url if provided and model is local/
        api_url = self.api_base
        
        # PROVIDER-SPECIFIC MAPPING & ROUTING
        provider_model_name = model
        api_url = self.api_base

        # 1. Detect OpenAI Direct Routing
        is_openai_key = api_key.startswith("sk-") and (len(api_key) > 50 or "svcacct" in api_key)
        
        if is_openai_key and model in ["o4-mini", "gpt-5-nano"]:
            api_url = "https://api.openai.com/v1/chat/completions"
            if model in ["o4-mini", "gpt-5-nano"]:
                provider_model_name = "gpt-5-nano"
        else:
            # 2. Alem API Mapping
            # The user explicitly stated: alem uses only qwen3. gemma3, gpt-oos
            if model == "qwen-3-70b":
                provider_model_name = "qwen3"
            elif model == "gpt-oss":
                provider_model_name = "gpt-oss"
            elif model == "gemma3":
                provider_model_name = "gemma3"
            elif model == "alemllm" or model == "gpt-5.4":
                provider_model_name = "alemllm"

        if getattr(settings, "local_llm_url", None) and (model.startswith("local/") or model == "local"):
            api_url = settings.local_llm_url
            if not api_url.endswith("/chat/completions"):
                api_url = api_url.rstrip("/") + "/chat/completions"
        
        payload = {
            "model": provider_model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if extra_body:
            payload.update(extra_body)
        
        timeout_config = httpx.Timeout(request_timeout or 300.0, connect=20.0, pool=None)
        # Transient HTTP errors that are safe to retry
        RETRYABLE_STATUS = {429, 500, 502, 503, 504}
        MAX_RETRIES = 3
        last_error: dict = {}

        async with httpx.AsyncClient(timeout=timeout_config) as client:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = await client.post(api_url, json=payload, headers=headers)
                    if response.status_code == 400:
                        resp_data = response.json()
                        err_msg = resp_data.get("error", {}).get("message", "")
                        if "ContextWindowExceededError" in err_msg and payload["max_tokens"] > 1000:
                            new_max = payload["max_tokens"] // 2
                            logger.warning(f"Context window exceeded. Reducing max_tokens from {payload['max_tokens']} to {new_max} and retrying.")
                            payload["max_tokens"] = new_max
                            continue

                    response.raise_for_status()
                    data = response.json()

                    choices = data.get("choices", [])
                    if not choices:
                        return {"ok": False, "error": "No choices returned"}

                    choice = choices[0]
                    finish_reason = choice.get("finish_reason")
                    output_text = choice.get("message", {}).get("content", "")

                    if finish_reason == "length" and not output_text and attempt < MAX_RETRIES:
                        new_max = payload["max_tokens"] + 4000
                        logger.warning(f"Response cut off (length). Increasing max_tokens from {payload['max_tokens']} to {new_max} and retrying.")
                        payload["max_tokens"] = new_max
                        continue

                    if not output_text:
                        # Sometimes reasoning_content consumes all tokens, leaving content empty
                        reasoning = choice.get("message", {}).get("reasoning_content", "")
                        if reasoning and not output_text:
                            logger.warning(f"Alem returned reasoning but no content for model={model}. Finish reason={finish_reason}")
                        else:
                            logger.warning(f"Alem returned empty output_text! RAW: {data}")
                    
                    return {"ok": True, "output_text": output_text, "raw": data}

                except httpx.HTTPStatusError as e:
                    resp_text = ""
                    try:
                        resp_text = e.response.text
                    except: pass
                    status_code = e.response.status_code
                    if status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                        import random
                        # Exponential backoff with jitter: 2, 4, 8, 16, 32 + random(0-2)
                        wait = (2 ** (attempt + 1)) + random.uniform(0, 2)
                        logger.warning(
                            "[RETRY] Alem HTTP %s (attempt %d/%d), "
                            "retrying in %.2fs... model=%s",
                            status_code, attempt+1, MAX_RETRIES, wait, model
                        )
                        await asyncio.sleep(wait)
                        last_error = {"ok": False, "error": f"HTTP {status_code}: {e}", "raw": resp_text}
                        continue
                    logger.error(f"Alem API HTTP Error {status_code}: {e} | Body: {resp_text}")
                    return {"ok": False, "error": f"HTTP {status_code}: {e}", "raw": resp_text}

                except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadError,
                        httpx.WriteError, httpx.TimeoutException) as e:
                    err_msg = str(e) or f"{type(e).__name__} (no message)"
                    if attempt < MAX_RETRIES:
                        import random
                        wait = (2 ** (attempt + 1)) + random.uniform(0, 2)
                        logger.warning(
                            "[RETRY] Alem network error [%s] (attempt %d/%d), "
                            "retrying in %.2fs... model=%s: %s",
                            type(e).__name__, attempt+1, MAX_RETRIES, wait, model, err_msg
                        )
                        await asyncio.sleep(wait)
                        last_error = {"ok": False, "error": err_msg or type(e).__name__}
                        continue
                    logger.error(f"Alem API network error [{type(e).__name__}] for model={model}: {err_msg}")
                    return {"ok": False, "error": err_msg or type(e).__name__}

                except Exception as e:
                    err_msg = str(e) or f"{type(e).__name__} (no message)"
                    logger.error(f"Alem API unexpected error [{type(e).__name__}] for model={model}: {err_msg}")
                    return {"ok": False, "error": err_msg or type(e).__name__}

        # Exhausted all retries
        logger.error("[RETRY:FAIL] Alem gave up after %d retries for model=%s", MAX_RETRIES, model)
        return last_error or {"ok": False, "error": f"Exhausted {MAX_RETRIES} retries"}

    async def create_structured_completion(
        self,
        system_instruction: str,
        user_prompt: str,
        json_schema: Dict[str, Any],
        wrapper_name: str = "output",
        model: str = "alemllm",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Специализированный метод для получения строго структурированного JSON.
        """
        if model != "alemllm" and json_schema:
            schema_text = json.dumps(json_schema, ensure_ascii=False, indent=4)
            system = f"{system_instruction}\n\nYou are generating machine-consumable data.\n\nSTRICT RULES:\n- Output ONLY valid JSON\n- NO markdown\n- NO comments\n- NO trailing text\n- NO explanations\n\nThe JSON MUST strictly conform to the schema below.\n\nROOT OBJECT REQUIREMENT:\nThe top-level JSON MUST be:\n{{\n  \"{wrapper_name}\": <value matching schema>\n}}\n\nIf a field is optional and unknown — use null.\nIf a field is required — it MUST be present.\n\nJSON SCHEMA:\n{schema_text}".strip()
            res = await self.create_chat_completion(
                system_instruction=system,
                user_prompt=user_prompt,
                model=model,
                **kwargs
            )
        elif model != "alemllm" and not json_schema:
             # Traditional text-based call
            res = await self.create_chat_completion(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                model=model,
                **kwargs
            )
        else:
            extra_body = {
                "response_format": {"type": "json_object"},
                "json_schema": json_schema,
                "wrapper_name": wrapper_name
            }
            kwargs["extra_body"] = extra_body
            res = await self.create_chat_completion(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                model=model,
                **kwargs
            )

        # --- PROACTIVE FAILSAFE ---
        from app.services.utils import _resp_to_parsed
        parsed = _resp_to_parsed(res)
        
        # If parsing failed and we are NOT using the failsafe yet
        if (not isinstance(parsed, (dict, list))) and model != settings.structured_provider:
            logger.warning(f"Model {model} failed JSON structure for {wrapper_name}. Falling back to {settings.structured_provider}")
            return await self.create_structured_completion(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                json_schema=json_schema,
                wrapper_name=wrapper_name,
                model=settings.structured_provider,
                **kwargs
            )
        
        return res

alem_client = AlemClient()
