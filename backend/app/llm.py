"""Azure OpenAI LLM integration for intelligence analysis."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("agus.llm")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

SYSTEM_PROMPT = """You are a military intelligence analyst at a global OSINT monitoring center.
Provide structured intelligence briefings based on the data provided.
Be concise, factual, and focus on actionable intelligence.
Use military-style formatting with clear sections.
Do NOT speculate beyond what the data supports.
Rate threat levels as: LOW, MEDIUM, HIGH, CRITICAL.
Include confidence levels for predictions: HIGH CONFIDENCE, MODERATE CONFIDENCE, LOW CONFIDENCE."""


def is_configured() -> bool:
    """Check if Azure OpenAI is configured."""
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY)


async def analyze(context: dict, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Send structured OSINT prompt to Azure OpenAI and return analysis."""
    if not is_configured():
        return {
            "briefing": "LLM analysis unavailable. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY.",
            "threat_level": "",
            "predictions": [],
            "sources": [],
        }

    region = context.get("region", "Global")
    entity = context.get("entity", {})
    layers = context.get("layers", [])
    events_summary = context.get("events_summary", "")
    satellite_data = context.get("satellite_data", "")

    user_prompt = f"""INTELLIGENCE ANALYSIS REQUEST
Region: {region}
Active Layers: {', '.join(layers)}

CURRENT SITUATION DATA:
{events_summary}

ENTITY OF INTEREST:
{_format_entity(entity)}

SATELLITE OVERPASSES:
{satellite_data or 'No satellite correlation data available.'}

PROVIDE:
1. SITUATION REPORT: Summary of current state (2-3 paragraphs)
2. THREAT ASSESSMENT: Overall threat level (LOW/MEDIUM/HIGH/CRITICAL) with justification
3. KEY OBSERVATIONS: 3-5 bullet points of significant findings
4. PREDICTIONS: 2-3 likely developments in next 24-72 hours with confidence levels
5. RECOMMENDED ACTIONS: Intelligence priorities and monitoring focus areas"""

    api_url = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version=2024-02-01"

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    try:
        use_client = client or httpx.AsyncClient(timeout=60.0)
        try:
            resp = await use_client.post(
                api_url,
                json=payload,
                headers={
                    "api-key": AZURE_OPENAI_KEY,
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        finally:
            if not client:
                await use_client.aclose()

        # Parse the response into structured sections
        return _parse_analysis(content, region)

    except Exception as exc:
        logger.error("LLM analysis failed: %s", exc)
        return {
            "briefing": f"Analysis failed: {exc}",
            "threat_level": "",
            "predictions": [],
            "sources": [],
        }


def _format_entity(entity: dict) -> str:
    if not entity:
        return "No specific entity selected."
    parts = []
    for k, v in entity.items():
        if v and k not in ("_id",):
            parts.append(f"  {k}: {v}")
    return "\n".join(parts) if parts else "No specific entity selected."


def _parse_analysis(content: str, region: str) -> dict:
    """Parse LLM response into structured briefing data."""
    # Determine threat level from content
    threat_level = "MEDIUM"
    content_upper = content.upper()
    if "CRITICAL" in content_upper and ("THREAT" in content_upper or "LEVEL" in content_upper):
        threat_level = "CRITICAL"
    elif "HIGH" in content_upper and ("THREAT" in content_upper or "LEVEL" in content_upper):
        threat_level = "HIGH"
    elif "LOW" in content_upper and ("THREAT" in content_upper or "LEVEL" in content_upper):
        threat_level = "LOW"

    # Extract predictions (lines starting with numbers or bullets)
    predictions = []
    for line in content.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
            if any(kw in line.lower() for kw in ["predict", "likely", "expect", "probable", "forecast"]):
                predictions.append({"text": line.lstrip("0123456789.-* "), "confidence": "MODERATE"})

    return {
        "briefing": content,
        "threat_level": threat_level,
        "predictions": predictions[:5],
        "sources": [f"OSINT Analysis for {region}", "Azure OpenAI Intelligence Assessment"],
    }
