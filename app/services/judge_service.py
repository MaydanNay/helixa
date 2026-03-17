# app/services/judge_service.py
"""
Super Judge - параллельная генерация на 3 моделях + синтез лучшего ответа.

Схема работы:
  1. gpt-oss, gemma3, qwen3 генерируют этап одновременно (asyncio.gather)
  2. Судья (gpt-oss) получает все 3 варианта + строгую инструкцию
  3. Судья синтезирует финальный ответ, используя ТОЛЬКО данные из кандидатов
  4. Финальный ответ проходит schema validation
  5. Fallback: если судья провалил - берём лучший валидный кандидат из 3-х
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Tuple, Optional
from app.config import settings
from app.services.llm.client import call_responses_api
from app.services.validation.schema_utils import validate_and_parse_response
from app.services.utils import _normalize_response_for_field

logger = logging.getLogger(__name__)

# Три модели-генератора (порядок влияет на подачу судье: A, B, C)
JUDGE_MODELS = ["gpt-oss", "gemma3", "qwen3"]
JUDGE_MODEL = settings.judge_provider   # Кто принимает финальное решение
JUDGE_TIMEOUT = 180        # секунд на каждый вызов (3 минуты достаточно)


async def _call_model(
    model: str,
    sys_inst: str,
    prompt: str,
    wrapper_schema: Dict,
    field_name: str,
    temperature: float = 0.75,
) -> Tuple[str, Optional[Dict]]:
    """Вызывает одну модель и возвращает (model_name, raw_response | None)."""
    try:
        resp = await asyncio.wait_for(
            call_responses_api(
                system_instruction=sys_inst,
                user_prompt=prompt,
                wrapper_schema=wrapper_schema,
                wrapper_name=field_name,
                provider=model,
                request_timeout=JUDGE_TIMEOUT - 5,
                temperature=temperature,
            ),
            timeout=JUDGE_TIMEOUT,
        )
        if resp.get("ok"):
            return model, resp
    except Exception as exc:
        logger.warning("[JUDGE] Model %s failed for %s: %s", model, field_name, exc)
    return model, None


def _build_judge_prompt(
    field_name: str,
    candidates: List[Tuple[str, str]],   # [(model, json_text), ...]
    wrapper_schema: Dict,
) -> str:
    """Собирает промпт для судьи."""
    candidates_text = "\n\n".join(
        f"=== CANDIDATE {i+1} (model: {model}) ===\n{text}"
        for i, (model, text) in enumerate(candidates)
    )
    
    schema_block = ""
    if wrapper_schema:
        schema_text = json.dumps(wrapper_schema, ensure_ascii=False, indent=2)
        schema_block = f"""
STRICT JSON SCHEMA REQUIREMENT:
Your output MUST be a valid JSON object matching this schema:
{schema_text}
"""

    return f"""
Analyze the following candidate responses for the character attribute: {field_name}.
Synthesize the best, most coherent, and interesting details from all candidates into a single superior response.

CANDIDATES:
{candidates_text}

{schema_block}

STRICT RULES:
- Use ONLY information from the candidates (don't hallucinate).
- If candidates contradict each other, choose the most psychologically consistent option based on character summary.
- Your output must be ONLY a valid JSON object. No markdown, no explanations.
"""


async def generate_field_with_judge(
    sys_inst: str,
    prompt: str,
    schema: Dict,
    field_name: str,
    w_name: str,
    temperature: float = 0.75,  # stage-specific temperature for generators
    primary_model: str = settings.judge_provider, # model that acts as the synthesis judge
) -> Tuple[Dict, Any]:
    """
    Главная точка входа для Super Judge.
    
    1. Запускает JUDGE_MODELS параллельно (с per-stage temperature)
    2. Собирает валидные кандидаты
    3. Если < 2 кандидатов - fallback на обычный generate_field
    4. Судья (primary_model) синтезирует финальный результат (temperature=0.3 - always precise)
    5. Валидация → нормализация
    """
    from app.services.validation.schema_utils import wrap_schema_if_needed
    from app.services.stage_generators import generate_field
    from app.services.llm.retry import call_with_retries

    wrapper_schema = wrap_schema_if_needed(field_name, schema)

    # --- 1. Параллельная генерация (с per-stage temperature) ---
    logger.info("[JUDGE] Stage=%s - launching %d models in parallel (temp=%.2f)", field_name, len(JUDGE_MODELS), temperature)
    tasks = [
        _call_model(model, sys_inst, prompt, wrapper_schema, field_name, temperature=temperature)
        for model in JUDGE_MODELS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # --- 2. Собираем валидные кандидаты ---
    valid_candidates: List[Tuple[str, str, Dict]] = []  # (model, json_text, parsed)
    for i, res in enumerate(results):
        model = JUDGE_MODELS[i]
        if isinstance(res, Exception):
            logger.warning("[JUDGE] Model %s task raised unexpected exception: %s", model, res)
            continue
            
        model_name, resp = res # res is (model_name, resp)
        if resp is None:
            continue
        try:
            parsed = await validate_and_parse_response(resp, wrapper_schema, field_name)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
            valid_candidates.append((model_name, text, parsed))
            logger.info("[JUDGE] ✓ %s produced valid response for %s", model_name, field_name)
        except Exception as ve:
            logger.warning("[JUDGE] ✗ %s failed validation for %s: %s", model_name, field_name, ve)

    # --- 3. Fallback если меньше 2 кандидатов ---
    if len(valid_candidates) == 0:
        logger.warning("[JUDGE] No valid candidates for %s - falling back to single-model retry using %s", field_name, primary_model)
        async def _fallback_llm(sys, pmt, ws, wn, temperature=temperature):
            return await call_with_retries(sys, pmt, ws, wrapper_name=wn, attempts=5, timeout=600, provider=primary_model, temperature=temperature)
        return await generate_field(sys_inst, prompt, schema, field_name, w_name, _fallback_llm)

    if len(valid_candidates) == 1:
        logger.info("[JUDGE] Only 1 candidate - skipping synthesis, using as-is for %s", field_name)
        model, _, parsed = valid_candidates[0]
        obj, data = _normalize_response_for_field(parsed, field_name)
        if data is not None:
            return obj, data

    # --- 4. Судья синтезирует ---
    judge_to_use = primary_model if primary_model in JUDGE_MODELS else JUDGE_MODEL
    logger.info("[JUDGE] Synthesizing %d candidates for %s via %s", len(valid_candidates), field_name, judge_to_use)
    judge_prompt = _build_judge_prompt(
        field_name,
        [(m, txt) for m, txt, _ in valid_candidates],
        wrapper_schema,
    )
    judge_sys = (
        "You are an expert synthesis judge for AI character generation. "
        "Your task is to create the highest-quality, most coherent character data "
        "by synthesizing the best parts of multiple model outputs. "
        "Output ONLY valid JSON. Never hallucinate or invent information not present in the candidates."
    )

    try:
        judge_resp = await asyncio.wait_for(
            call_responses_api(
                system_instruction=judge_sys,
                user_prompt=judge_prompt,
                wrapper_schema=wrapper_schema,
                wrapper_name=field_name,
                provider=judge_to_use,
                request_timeout=JUDGE_TIMEOUT - 5,
                temperature=0.3,   # Низкая температура - судья должен быть точным
            ),
            timeout=JUDGE_TIMEOUT,
        )

        if judge_resp.get("ok"):
            parsed_judge = await validate_and_parse_response(judge_resp, wrapper_schema, field_name)
            obj, data = _normalize_response_for_field(parsed_judge, field_name)
            if data is not None:
                logger.info("[JUDGE] ✅ Synthesis successful for %s", field_name)
                return obj, data
    except Exception as je:
        logger.warning("[JUDGE] Judge synthesis failed for %s: %s - using best candidate", field_name, je)

    # --- 5. Fallback: лучший валидный кандидат (первый в списке = gpt-oss) ---
    logger.info("[JUDGE] Using best fallback candidate for %s (model=%s)", field_name, valid_candidates[0][0])
    best_model, _, best_parsed = valid_candidates[0]
    obj, data = _normalize_response_for_field(best_parsed, field_name)
    if data is None:
        raise ValueError(f"[JUDGE] All paths failed for {field_name}")
    return obj, data
