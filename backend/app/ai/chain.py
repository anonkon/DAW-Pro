from __future__ import annotations

import json
import logging
import time

from ..config import settings
from ..schemas import AnalysisResult, FrequencyBand, Persona, TimingMarker

logger = logging.getLogger("dawpro.ai")

_MAX_ATTEMPTS = 2
_RETRY_DELAY_SEC = 2.0

_BANDS = [
    ("low", 20.0, 250.0),
    ("low-mid", 250.0, 500.0),
    ("mid", 500.0, 2000.0),
    ("high-mid", 2000.0, 6000.0),
    ("high", 6000.0, 20000.0),
]

_SYSTEM_PROMPT_TEMPLATE = """You are DAWpro, a mentor for a self-taught music producer — not a ghost producer.
Skill level: {skill_level}
Feedback tone: {feedback_tone}
Preferred genres: {preferred_genres}

Rules:
- Music is subjective. Never give specific prescriptive instructions
  (e.g. exact dB cuts, exact plugin settings) unless the user has explicitly
  asked for a direct fix. Default to guiding the producer toward the right
  question or area to explore themselves.
- Tailor feedback to the exact genre and acoustic profile of the project,
  not generic mixing advice.
- Ground every claim in the provided audio feature data — do not invent
  measurements you weren't given.
- If reference_features is empty, no reference track has been analyzed for
  this session yet — give feedback on the project audio alone and say so in
  the summary, rather than inventing a comparison.
"""


def analyze(
    project_features: dict,
    reference_features: dict,
    persona: Persona,
    sonic_intention: str,
    genre: str | None,
) -> AnalysisResult:
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set, returning stub analysis")
        return _stub_result(project_features, reference_features)

    return _gemini_result(project_features, reference_features, persona, sonic_intention, genre)


def _gemini_result(
    project_features: dict,
    reference_features: dict,
    persona: Persona,
    sonic_intention: str,
    genre: str | None,
) -> AnalysisResult:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=settings.gemini_api_key,
        temperature=0.3,  # analytical grounding matters more than variety here
    )
    structured_llm = llm.with_structured_output(AnalysisResult)

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        skill_level=persona.skill_level,
        feedback_tone=persona.feedback_tone,
        preferred_genres=", ".join(persona.preferred_genres) or "unspecified",
    )
    human_payload = {
        "sonic_intention": sonic_intention,
        "genre": genre,
        "project_features": project_features,
        "reference_features": reference_features,
    }
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(human_payload, default=str)),
    ]

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return structured_llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - transient API errors, retried once
            last_error = exc
            logger.warning("Gemini call failed (attempt %d/%d): %s", attempt, _MAX_ATTEMPTS, exc)
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SEC)
    raise last_error  # type: ignore[misc]


def _stub_result(project_features: dict, reference_features: dict) -> AnalysisResult:
    project_bands = project_features.get("band_energy_db", {})
    reference_bands = reference_features.get("band_energy_db", {})
    eq_comparison = [
        FrequencyBand(
            label=label,
            hz_low=lo,
            hz_high=hi,
            project_db=project_bands.get(label, 0.0),
            reference_db=reference_bands.get(label, 0.0),
        )
        for label, lo, hi in _BANDS
    ]
    timing_markers = [
        TimingMarker(time_sec=t, label="onset detected", severity="info")
        for t in project_features.get("onsets_sec", [])[:5]
    ]
    return AnalysisResult(
        summary="GEMINI_API_KEY not configured — showing raw feature comparison instead of AI analysis.",
        eq_comparison=eq_comparison,
        timing_markers=timing_markers,
        issues=[],
        mix_score=None,
    )
