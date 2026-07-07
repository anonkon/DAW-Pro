from __future__ import annotations

import logging

from .config import settings
from .schemas import Persona

logger = logging.getLogger("dawpro.personas")

_DEFAULT_PERSONA = Persona(
    id="default",
    skill_level="beginner",
    preferred_genres=[],
    feedback_tone="guided",
)


def get_persona(persona_id: str) -> Persona:
    if not (settings.supabase_url and settings.supabase_service_key):
        return _DEFAULT_PERSONA.model_copy(update={"id": persona_id})

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_key)
        response = client.table("personas").select("*").eq("id", persona_id).single().execute()
        row = response.data
        return Persona(
            id=row["id"],
            skill_level=row["skill_level"],
            preferred_genres=row.get("preferred_genres", []),
            feedback_tone=row.get("feedback_tone", "guided"),
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to fetch persona %s from Supabase, using default", persona_id)
        return _DEFAULT_PERSONA.model_copy(update={"id": persona_id})
