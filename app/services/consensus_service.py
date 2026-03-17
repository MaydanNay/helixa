import json
import logging
import asyncio
from typing import Dict, Any, Optional
from app.config import settings

from app.services.alem_client import alem_client as alem_plus_client
from app.services.stage_generators import generate_field
from app.services.qdrant_client import memory_service

LOG = logging.getLogger("consensus_service")

# DOMAIN -> CRITIC MAPPING
# Which model is best for critiquing each domain.
# Currently all use alemllm (single provider). Extend when more models are added.
CRITIC_MAPPING = {
    "psychology":  settings.generator_provider,
    "behavioral":  settings.generator_provider,
    "family":      settings.generator_provider,
    "sociology":   settings.generator_provider,
    "financial":   settings.generator_provider,
    "planning":    settings.generator_provider,
    "biography":   settings.generator_provider,
    "voice_dna":   settings.generator_provider,
    "experience":  settings.generator_provider,
    "health":      settings.generator_provider,
    "private":     settings.generator_provider,
    "default":     settings.generator_provider,
}


class ConsensusService:
    """
    'Council of Agents' — Multi-step consensus review.

    Flow per stage:
      1. CRITIQUE  — Critic reads the generated data and finds issues.
      2. FIX       — Critic rewrites the data to fix issues.
      3. VERIFY    — Critic confirms the fix resolved the problems.

    If critique says OK → return original immediately (skip FIX + VERIFY).
    If fix fails → return original.
    If verify fails non-fatally → still return the fix (best effort).
    """

    @classmethod
    async def review_and_refine(
        cls,
        content: Dict[str, Any],
        domain: str,
        schema: Dict[str, Any],
        system_instruction: str = "",
        agent_id: str = None,
        profile_context: str = None
    ) -> Dict[str, Any]:

        critic_client = alem_plus_client
        critic_name = CRITIC_MAPPING.get(domain, settings.generator_provider)

        if not critic_client or not getattr(critic_client, "is_configured", False):
            LOG.warning("Consensus skipped for [%s]: client not configured", domain)
            return content

        LOG.info("Consensus Review START [%s] critic=%s", domain, critic_name)

        # ── STEP 0: RAG GROUNDING ────────────────────────────────────────────
        rag_context = ""
        if agent_id:
            try:
                col_name = f"agent_memory_{agent_id}"
                results = await memory_service.search_memory(
                    col_name,
                    f"Core traits and facts relevant to {domain}",
                    limit=4
                )
                if results:
                    rag_context = "\n\n=== AGENT MEMORY CONTEXT ===\n" + \
                        "\n".join([r.get("text", "") for r in results])
            except Exception as re:
                LOG.warning("RAG grounding failed for consensus [%s]: %s", domain, re)

        # ── STEP 1: CRITIQUE ─────────────────────────────────────────────────
        try:
            critique_prompt = (
                f"You are a Senior Expert Reviewer specialized in {domain}.\n"
            )
            if profile_context:
                critique_prompt += f"AGENT CORE IDENTITY (Primary Truth):\n{profile_context}\n\n"
            if rag_context:
                critique_prompt += f"{rag_context}\n\n"

            critique_prompt += (
                f"Analyze the following JSON data for an AI agent.\n\n"
                f"DATA:\n{json.dumps(content, ensure_ascii=False, indent=2)}\n\n"
                "Your task: Find logical contradictions, inconsistencies, impossibilities, or poor quality details.\n"
                "- Psychology: incompatible traits, unrealistic combinations\n"
                "- Finance/Planning: math errors, unrealistic budgets\n"
                "- Biography: timeline anomalies, age conflicts\n"
                "- Experience: skills that don't match stated profession\n"
                "- Voice DNA: unnaturalness, inconsistency with personality\n\n"
                "CRITICAL: Data MUST be consistent with AGENT CORE IDENTITY.\n"
                "If high quality and consistent, start with 'OK'.\n"
                "If there are issues, list them clearly and concisely."
            )

            critique_resp = await critic_client.create_chat_completion(
                system_instruction="You are a strict QA Critic. Be critical but concise.",
                user_prompt=critique_prompt,
                temperature=0.3
            )
            critique_text = critique_resp.get("output_text", "").strip()
            LOG.info("[%s] Critique result: %s", critic_name, critique_text[:120].replace("\n", " "))

            # If OK → skip fix and verify
            if critique_text.upper().startswith("OK") or "NO ISSUES" in critique_text.upper():
                LOG.info("[%s] [%s] approved — no issues found", critic_name, domain)
                return content

        except Exception as e:
            LOG.exception("Consensus CRITIQUE failed for %s: %s", domain, e)
            return content

        # ── STEP 2: FIX ──────────────────────────────────────────────────────
        LOG.info("Consensus FIX [%s]: inconsistencies found, applying fixes...", domain)
        try:
            fix_prompt = (
                f"You identified the following issues:\n{critique_text}\n\n"
            )
            if profile_context:
                fix_prompt += f"AGENT CORE IDENTITY:\n{profile_context}\n\n"

            fix_prompt += (
                f"ORIGINAL DATA:\n{json.dumps(content, ensure_ascii=False, indent=2)}\n\n"
                "Task: Rewrite the JSON to fix ALL identified issues.\n"
                "THE REVISED DATA MUST ALIGN PERFECTLY WITH THE AGENT CORE IDENTITY.\n"
                f"Return ONLY the corrected JSON wrapped in the root key '{domain}'.\n"
                "Match the original schema structure exactly."
            )

            async def critic_llm_call(sys, u_prompt, w_schema, w_name):
                return await critic_client.create_structured_completion(
                    system_instruction=sys,
                    user_prompt=u_prompt,
                    json_schema=w_schema,
                    wrapper_name=w_name
                )

            # Extract the correct wrapper key for this schema to avoid double wrapping
            wrapper_name = domain
            if isinstance(schema, dict) and "properties" in schema and schema["properties"]:
                # The first property key in the schema is usually the expected root wrapper
                wrapper_name = list(schema["properties"].keys())[0]

            fixed_obj, _ = await generate_field(
                sys_inst=system_instruction or "You are a Fixer Agent. Fix all identified issues.",
                prompt=fix_prompt,
                schema=schema,
                field_name=wrapper_name,
                w_name=f"{domain}_fix",
                llm_call_fn=critic_llm_call
            )

            if not fixed_obj:
                LOG.warning("[%s] Fix returned empty, reverting to original for [%s]", critic_name, domain)
                return content

            LOG.info("[%s] Fix applied successfully for [%s]", critic_name, domain)

        except Exception as e:
            LOG.exception("Consensus FIX failed for %s: %s", domain, e)
            return content

        # ── STEP 3: VERIFY ───────────────────────────────────────────────────
        LOG.info("Consensus VERIFY [%s]: running second-pass verification...", domain)
        try:
            verify_prompt = (
                f"You previously identified these issues:\n{critique_text}\n\n"
                f"REVISED DATA:\n{json.dumps(fixed_obj, ensure_ascii=False, indent=2)}\n\n"
                "Task: Does this revised JSON correctly fix all the identified issues?\n"
                "Start with 'OK' if fixed. Otherwise describe remaining problems briefly."
            )
            verify_resp = await critic_client.create_chat_completion(
                system_instruction="You are a final QA Auditor. Be brief and decisive.",
                user_prompt=verify_prompt,
                temperature=0.1
            )
            verify_text = verify_resp.get("output_text", "").strip()
            LOG.info("[%s] Verify result for [%s]: %s", critic_name, domain, verify_text[:100].replace("\n", " "))

            if verify_text.upper().startswith("OK"):
                LOG.info("[%s] [%s] fix VERIFIED ✓", critic_name, domain)
            else:
                LOG.warning("[%s] [%s] fix not fully verified: %s", critic_name, domain, verify_text[:100])
                # Still return fixed_obj — best effort, verification is advisory

        except Exception as ve:
            LOG.warning("Consensus VERIFY failed (non-fatal) for %s: %s", domain, ve)

        return fixed_obj
