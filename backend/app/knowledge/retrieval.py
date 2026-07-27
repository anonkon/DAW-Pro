from __future__ import annotations

from typing import Callable

from ..schemas import Measurements
from .base import ALL_CHUNKS, KnowledgeChunk

KNOWLEDGE_TOP_K = 5

# Below this, a track's dynamic range reads as flat/over-compressed rather
# than punchy - see technique_crest_factor's source for the 6-10dB "healthy"
# range this threshold sits at the bottom of.
CREST_FACTOR_LOW_THRESHOLD_DB = 6.0

# Heuristic, not a cited industry number: how far a band's project energy can
# sit above the reference track's before it counts as "buildup" worth flagging.
# Requires an actual reference track - with none, reference_db defaults to
# 0.0 (see pipeline/measurements.py._eq_comparison), which this delta will
# essentially never clear, so mud detection is a no-op until a reference
# exists for the session.
LOW_MID_MUD_DELTA_DB = 3.0

# Heuristic: side energy within 6dB of mid energy in the low band is treated
# as meaningfully wide and worth a mono-compatibility mention.
WIDE_LOW_STEREO_THRESHOLD_DB = -6.0

# Heuristic, on the 0-100 rhythmic_cohesion scale from pipeline/features.py.
LOOSE_TIMING_COHESION_THRESHOLD = 60.0

_GENRE_ALIASES: list[tuple[str, list[str]]] = [
    # lo-fi checked before trap/hip-hop since "lo-fi hip hop" would otherwise
    # also match the hip-hop aliases below.
    ("genre_lofi_hiphop", ["lofi", "lo-fi", "lo fi", "chillhop"]),
    ("genre_trap_hiphop", ["trap", "hip hop", "hip-hop", "hiphop", "rap", "drill"]),
    ("genre_edm_electronic", ["edm", "electronic", "trance", "house", "techno", "dubstep"]),
]


def _crest_factor_low(m: Measurements) -> bool:
    value = m.loudness.project.crest_factor_db
    return value is not None and value < CREST_FACTOR_LOW_THRESHOLD_DB


def _low_mid_mud(m: Measurements) -> bool:
    band = next((b for b in m.eq_comparison if b.label == "low-mid"), None)
    return band is not None and (band.project_db - band.reference_db) > LOW_MID_MUD_DELTA_DB


def _wide_low_stereo(m: Measurements) -> bool:
    band = next((b for b in m.stereo_width if b.label == "low"), None)
    return band is not None and band.width_db > WIDE_LOW_STEREO_THRESHOLD_DB


def _loose_timing(m: Measurements) -> bool:
    value = m.timing.rhythmic_cohesion
    return value is not None and value < LOOSE_TIMING_COHESION_THRESHOLD


# (technique chunk id, trigger predicate, paired skill chunk id, skill level it applies to)
# The skill chunk is only included alongside its technique when the trigger
# fires AND the persona is at the matching skill tier - otherwise it's
# generic advice with nothing in this analysis to ground it.
_TECHNIQUE_TRIGGERS: list[tuple[str, Callable[[Measurements], bool], str | None, str | None]] = [
    ("technique_crest_factor", _crest_factor_low, "skill_beginner_overcompression", "beginner"),
    ("technique_low_mid_mud", _low_mid_mud, "skill_beginner_low_mid_stacking", "beginner"),
    ("technique_stereo_bass_mono", _wide_low_stereo, "skill_intermediate_mono_compat", "intermediate"),
    ("technique_timing_swing", _loose_timing, None, None),
]


def _match_genre(genre: str | None, preferred_genres: list[str] | None = None) -> KnowledgeChunk | None:
    """First genre-tagged chunk matching `genre`, falling back to persona's
    preferred_genres if `genre` itself doesn't match anything seeded."""
    candidates = [genre, *(preferred_genres or [])]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = candidate.lower()
        for chunk_id, aliases in _GENRE_ALIASES:
            if any(alias in normalized for alias in aliases):
                return ALL_CHUNKS[chunk_id]
    return None


def retrieve_knowledge(
    measurements: Measurements,
    genre: str | None,
    skill_level: str,
    preferred_genres: list[str] | None = None,
) -> list[KnowledgeChunk]:
    """Genre target + triggered technique/skill chunks, capped at KNOWLEDGE_TOP_K.

    Retrieval is deterministic tag/trigger matching against already-computed
    measurements and the genre string - not semantic search - so it's
    unit-testable with a synthetic Measurements object and never returns
    something ungrounded in what was actually detected.
    """
    results: list[KnowledgeChunk] = []

    genre_chunk = _match_genre(genre, preferred_genres)
    if genre_chunk:
        results.append(genre_chunk)

    for chunk_id, predicate, skill_chunk_id, paired_skill_level in _TECHNIQUE_TRIGGERS:
        if not predicate(measurements):
            continue

        results.append(ALL_CHUNKS[chunk_id])
        if len(results) >= KNOWLEDGE_TOP_K:
            return results[:KNOWLEDGE_TOP_K]

        if skill_chunk_id and skill_level == paired_skill_level:
            results.append(ALL_CHUNKS[skill_chunk_id])
            if len(results) >= KNOWLEDGE_TOP_K:
                return results[:KNOWLEDGE_TOP_K]

    return results
