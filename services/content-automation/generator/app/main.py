from __future__ import annotations
import os
import logging
from typing import Any
from anthropic import APIError, RateLimitError
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
import yaml
from pathlib import Path

from common.auth import verify_token
from common.dto import HealthResponse
from common.observability import configure_logging, setup_metrics

# Load brand voices at startup
BRAND_VOICES: dict[str, Any] = {}


def load_brand_voices():
    logger.info("brand_voice_load_start")
    brand_dir = Path("/app/brand-voice")
    if not brand_dir.exists():
        brand_dir = Path("brand-voice")

    for voice_file in brand_dir.glob("*.yaml"):
        with open(voice_file) as f:
            BRAND_VOICES[voice_file.stem] = yaml.safe_load(f)
    logger.info("brand_voice_load_complete", extra={"voices": list(BRAND_VOICES.keys())})


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_brand_voices()
    yield
    BRAND_VOICES.clear()


app = FastAPI(title="Content Generator", lifespan=lifespan)
if os.getenv("ENABLE_OBSERVABILITY", "1").lower() not in {"0", "false", "no"}:
    configure_logging("content-generator")
    setup_metrics(app, "content-generator")
logger = logging.getLogger(__name__)

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    platform: str = Field(..., pattern="^(instagram|facebook|twitter|tiktok)$")
    brand_voice: str = Field(default="professional")
    num_variants: int = Field(default=3, ge=1, le=5)

@app.get("/healthz", response_model=HealthResponse)
async def health():
    return HealthResponse(service="content-generator")

def get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


@app.post("/generate", dependencies=[Depends(verify_token)])
async def generate_caption(req: GenerateRequest, client=Depends(get_anthropic_client)):
    logger.info("generate_called", extra={"brand_voice": req.brand_voice, "platform": req.platform})
    # Validate brand voice exists
    if req.brand_voice not in BRAND_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown brand voice. Available: {list(BRAND_VOICES.keys())}"
        )

    voice = BRAND_VOICES[req.brand_voice]
    platform_config = voice.get("platforms", {}).get(req.platform, {})

    # Build prompt from brand voice configuration
    prompt = f"""Generate {req.num_variants} engaging social media captions for {req.platform}.

Topic: {req.topic}

Brand Voice Guidelines:
- Tone: {voice['tone']}
- Style: {', '.join(voice['style_elements'])}
- Word choice: {', '.join(voice['word_choice'])}

Platform-Specific:
- Character limit: {platform_config.get('character_limit', 'N/A')}
- Hashtag count: {platform_config.get('hashtag_count', '5-8')}
- Emoji usage: {platform_config.get('emoji_usage', 'moderate')}

Requirements:
- Each variant should be distinct
- Include {platform_config.get('hashtag_count', '5-8')} relevant hashtags
- Match the brand voice exactly

Return ONLY the captions, separated by "---"
"""

    # Call Anthropic API with correct model name
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",  # CORRECT model name
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text
    except RateLimitError:
        logger.warning("anthropic_rate_limit")
        raise HTTPException(status_code=429, detail="AI API rate limit exceeded")
    except APIError as e:
        logger.exception("anthropic_api_error")
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {e}")

    # Parse variants
    variants = [v.strip() for v in content.split("---") if v.strip()]

    return {
        "topic": req.topic,
        "platform": req.platform,
        "brand_voice": req.brand_voice,
        "variants": variants[:req.num_variants]
    }
