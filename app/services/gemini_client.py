from google import genai
from google.genai import types
import json
import httpx
import base64
import logging
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_IMAGE_MODEL = "gemini-3-pro-image-preview"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiClient:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

        self.openai_api_key = settings.openai_api_key
        if self.openai_api_key:
            safe_api_key = self.openai_api_key.encode("ascii", "ignore").decode("ascii")
            self.openai_client = AsyncOpenAI(api_key=safe_api_key)
        else:
            self.openai_client = None

    async def generate_json(self, prompt: str, schema_description: str) -> dict:
        """
        Generates structured JSON data using Gemini.
        """
        if not self.client:
            logger.warning("GEMINI_API_KEY not set. Using mock JSON.")
            return {"mock": True, "reason": "No API Key"}

        full_prompt = f"{prompt}\n\nStrictly return only a JSON object matching this description: {schema_description}"

        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-1.5-pro",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return {}

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generates a 1536-dimensional embedding vector for the given text using OpenAI.
        Compatible with Mimora memory format (text-embedding-3-small).
        """
        if not self.openai_client:
            logger.warning("OPENAI_API_KEY not set — RAG is DISABLED, returning zero embedding. Memory context will not work.")
            return [0.0] * 1536

        try:
            resp = await self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI Embedding failed — RAG context unavailable: {e}")
            return [0.0] * 1536

    async def classify_post(self, description: str) -> str:
        """
        Classifies if a post should be Tier 1 (Face) or Tier 3 (Filler).
        """
        prompt = f"Description: {description}\nIs this a 'face' (closeup of model) or 'filler' (aesthetic background, objects)?"
        result = await self.generate_json(prompt, "{ 'category': 'face' | 'filler' }")
        return result.get('category', 'face')

    # ─────────────────────────────────────────────────────────────────
    # Image generation via gemini-3-pro-image-preview
    # ─────────────────────────────────────────────────────────────────

    async def _call_image_api(self, parts: list) -> str | None:
        """Low-level call to Gemini image generation endpoint."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Returning mock URL.")
            return "https://placehold.co/768x1024?text=Gemini+Image"

        endpoint = f"{GEMINI_API_BASE}/{GEMINI_IMAGE_MODEL}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"]
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint, json=payload, timeout=120.0)
                if response.status_code != 200:
                    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = body.get("error", {}).get("message", response.text[:200])
                    logger.error(f"Gemini API error {response.status_code}: {err_msg}")
                    raise RuntimeError(f"Gemini {response.status_code}: {err_msg}")

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.error(f"Gemini returned no candidates. Response: {data}")
                    return None

                for part in candidates[0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        b64 = part["inlineData"]["data"]
                        mime = part["inlineData"].get("mimeType", "image/jpeg")
                        return f"data:{mime};base64,{b64}"
                    if "fileData" in part:
                        return part["fileData"].get("fileUri")

                logger.error(f"Gemini: no image in response parts: {candidates[0]}")
                return None
            except Exception as e:
                logger.error(f"Gemini image API exception: {e}")
                return None

    async def generate_portrait(self, prompt: str) -> str | None:
        """
        Generates a portrait using gemini-3-pro-image-preview.
        """
        full_prompt = f"{prompt}, portrait closeup, highly detailed face, photorealistic"
        return await self._call_image_api([{"text": full_prompt}])

    async def generate_body_with_face(self, prompt: str, face_image_url: str) -> str | None:
        """
        Generates a full body image using face as reference image.
        """
        full_prompt = (
            f"{prompt}, full body shot, maintain exact face identity from the reference image, "
            "photorealistic, plain white background, neutral studio lighting"
        )
        parts = [{"text": full_prompt}]

        # Fetch face image and include as inlineData
        try:
            async with httpx.AsyncClient() as fetcher:
                if face_image_url.startswith("data:"):
                    header, b64data = face_image_url.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                else:
                    img_resp = await fetcher.get(face_image_url, timeout=20.0)
                    img_resp.raise_for_status()
                    b64data = base64.b64encode(img_resp.content).decode()
                    mime = img_resp.headers.get("content-type", "image/jpeg").split(";")[0]

                parts.insert(0, {"inlineData": {"mimeType": mime, "data": b64data}})
        except Exception as e:
            logger.warning(f"Could not attach face image for Gemini body: {e}")

        return await self._call_image_api(parts)


gemini_client = GeminiClient()
