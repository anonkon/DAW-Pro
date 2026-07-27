from __future__ import annotations

import json
import logging
import time

from ..config import settings
from ..pipeline.measurements import build_measurements
from ..schemas import AnalysisResult, Measurements, MentorNarrative, Persona, TimingMarker

logger = logging.getLogger("dawpro.ai")

_MAX_ATTEMPTS = 2
_RETRY_DELAY_SEC = 2.0

_SYSTEM_PROMPT_TEMPLATE = """You are DAWpro, a mentor for a self-taught music producer — not a ghost producer.
Skill level: {skill_level}
Feedback tone: {feedback_tone}
Preferred genres: {preferred_genres}

You are given measurements that have already been computed from the audio. Your
job is to interpret them, not to reproduce or extend them.

Rules:
- Music is subjective. Never give specific prescriptive instructions
  (e.g. exact dB cuts, exact plugin settings) unless the user has explicitly
  asked for a direct fix. Default to guiding the producer toward the right
  question or area to explore themselves.
- Tailor feedback to the exact genre and acoustic profile of the project,
  not generic mixing advice.
- Ground every claim in the measurements provided. Never state a number that
  is not in them, and never estimate one that is missing or null.
- A null measurement means it could not be computed. Say so plainly rather
  than guessing — for example a null phase correlation means the source was
  mono, so there is no stereo image to comment on.
- If reference_measurements is empty, no reference track has been analyzed for
  this session yet — give feedback on the project audio alone and say so in
  the summary, rather than inventing a comparison.

For each issue you raise, set hz_low/hz_high when it is frequency-specific, so
the dashboard can anchor the callout to the right part of the spectrum.

suggested_exploration: one thing the producer could try next, phrased as an
invitation to listen and decide for themselves, not an instruction.
suggested_path: a short label for that direction, a few words at most.
"""


def analyze(
    project_features: dict,
    reference_features: dict,
    persona: Persona,
    sonic_intention: str,
    genre: str | None,
    host_bpm: float | None = None,
) -> AnalysisResult:
    measurements = build_measurements(project_features, reference_features, host_bpm)

    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set, returning measurements without AI narrative")
        return _compose(
            MentorNarrative(
                summary=(
                    "GEMINI_API_KEY not configured — showing measured analysis "
                    "without AI interpretation."
                )
            ),
            measurements,
            project_features,
        )

    narrative = _gemini_narrative(
        measurements, reference_features, persona, sonic_intention, genre
    )
    return _compose(narrative, measurements, project_features)


def _compose(
    narrative: MentorNarrative, measurements: Measurements, project_features: dict
) -> AnalysisResult:
    return AnalysisResult(
        summary=narrative.summary,
        issues=narrative.issues,
        suggested_exploration=narrative.suggested_exploration,
        suggested_path=narrative.suggested_path,
        measurements=measurements,
        eq_comparison=measurements.eq_comparison,
        timing_markers=[
            TimingMarker(time_sec=t, label="onset detected", severity="info")
            for t in project_features.get("onsets_sec", [])[:5]
        ],
        mix_score=None,
    )


def _gemini_narrative(
    measurements: Measurements,
    reference_features: dict,
    persona: Persona,
    sonic_intention: str,
    genre: str | None,
) -> MentorNarrative:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=settings.gemini_api_key,
        temperature=0.3,  # analytical grounding matters more than variety here
    )
    # Narrative only. Asking the model for the measured fields would mean asking
    # it to invent numbers it has no way to know.
    structured_llm = llm.with_structured_output(MentorNarrative)

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        skill_level=persona.skill_level,
        feedback_tone=persona.feedback_tone,
        preferred_genres=", ".join(persona.preferred_genres) or "unspecified",
    )
    human_payload = {
        "sonic_intention": sonic_intention,
        "genre": genre,
        "measurements": measurements.model_dump(),
        "reference_measurements": bool(reference_features),
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
