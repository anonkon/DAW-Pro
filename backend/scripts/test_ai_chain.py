"""Standalone smoke test for the Gemini/LangChain analysis chain.

Exercises app.ai.chain.analyze() directly with synthetic feature data, so it
doesn't need Demucs/Librosa or an uploaded audio file - just a GEMINI_API_KEY
in backend/.env. Run from the backend/ directory:

    python -m scripts.test_ai_chain
"""

from __future__ import annotations

import json

from app.ai.chain import analyze
from app.schemas import Persona

PROJECT_FEATURES = {
    "duration_sec": 32.0,
    "rms_mean_db": -14.2,
    "band_energy_db": {
        "low": -6.0,
        "low-mid": -10.5,
        "mid": -12.0,
        "high-mid": -18.0,
        "high": -24.0,
    },
    "onsets_sec": [0.5, 1.0, 1.5, 2.0, 2.5],
    "stems": {},
}

REFERENCE_FEATURES = {
    "duration_sec": 30.0,
    "rms_mean_db": -11.0,
    "band_energy_db": {
        "low": -8.0,
        "low-mid": -9.0,
        "mid": -11.0,
        "high-mid": -14.0,
        "high": -19.0,
    },
    "onsets_sec": [0.5, 1.0, 1.5, 2.0],
    "stems": {},
}

PERSONA = Persona(id="test", skill_level="beginner", preferred_genres=["trap"], feedback_tone="guided")


def main() -> None:
    result = analyze(
        project_features=PROJECT_FEATURES,
        reference_features=REFERENCE_FEATURES,
        persona=PERSONA,
        sonic_intention="I want my low end to hit as hard as the reference without muddying the mids",
        genre="trap",
    )
    print(json.dumps(result.model_dump(), indent=2))

    print("\n--- with no reference track (empty reference_features) ---\n")
    result_no_ref = analyze(
        project_features=PROJECT_FEATURES,
        reference_features={},
        persona=PERSONA,
        sonic_intention="Just want a general read on the mix so far",
        genre="trap",
    )
    print(json.dumps(result_no_ref.model_dump(), indent=2))


if __name__ == "__main__":
    main()
