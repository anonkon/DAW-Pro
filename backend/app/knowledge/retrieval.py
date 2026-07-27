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

# Heuristic, symmetric with LOW_MID_MUD_DELTA_DB: how far a band's project
# energy can sit BELOW the reference's before it reads as thin rather than
# just quieter. Same reference-track requirement/limitation as the mud gate.
THIN_LOW_END_DELTA_DB = -3.0

# Heuristic - no cited numeric attack-time thresholds were found in the
# sourced material (Pro Techniques for Sound Design discusses attack
# character qualitatively, not in milliseconds). 30ms is a soft-to-slow 10-90%
# envelope rise time by ear-training convention for percussive material; a
# mean well above that across a track's detected onsets is worth surfacing.
SOFT_TRANSIENT_MEAN_MS = 30.0

_GENRE_ALIASES: list[tuple[str, list[str]]] = [
    # lo-fi checked before trap/hip-hop since "lo-fi hip hop" would otherwise
    # also match the hip-hop aliases below.
    ("genre_lofi_hiphop", ["lofi", "lo-fi", "lo fi", "chillhop"]),
    ("genre_trap_hiphop", ["trap", "hip hop", "hip-hop", "hiphop", "rap", "drill"]),
    ("genre_edm_electronic", ["edm", "electronic", "trance", "house", "techno", "dubstep"]),
    ("genre_metal", ["metal", "metalcore", "djent", "deathcore"]),
]


def _crest_factor_low(m: Measurements, has_reference: bool) -> bool:  # noqa: ARG001 - uniform predicate signature
    value = m.loudness.project.crest_factor_db
    return value is not None and value < CREST_FACTOR_LOW_THRESHOLD_DB


def _low_mid_mud(m: Measurements, has_reference: bool) -> bool:
    # Without a reference, reference_db defaults to 0.0 (see
    # pipeline/measurements.py._eq_comparison), which would make this delta
    # spuriously fire on almost any project band - require a real reference.
    if not has_reference:
        return False
    band = next((b for b in m.eq_comparison if b.label == "low-mid"), None)
    return band is not None and (band.project_db - band.reference_db) > LOW_MID_MUD_DELTA_DB


def _wide_low_stereo(m: Measurements, has_reference: bool) -> bool:  # noqa: ARG001
    band = next((b for b in m.stereo_width if b.label == "low"), None)
    return band is not None and band.width_db > WIDE_LOW_STEREO_THRESHOLD_DB


def _loose_timing(m: Measurements, has_reference: bool) -> bool:  # noqa: ARG001
    value = m.timing.rhythmic_cohesion
    return value is not None and value < LOOSE_TIMING_COHESION_THRESHOLD


def _thin_low_end(m: Measurements, has_reference: bool) -> bool:
    # Same reference requirement as _low_mid_mud, and for the same reason:
    # the 0.0 reference_db default would make this delta spuriously fire on
    # almost every project band (project_db is virtually always < -3dBFS) -
    # the mud trigger's polarity happens to be guarded by that default by
    # accident, this one's polarity is not, so both need the explicit check.
    if not has_reference:
        return False
    band = next((b for b in m.eq_comparison if b.label == "low"), None)
    return band is not None and (band.project_db - band.reference_db) < THIN_LOW_END_DELTA_DB


def _soft_transients(m: Measurements, has_reference: bool) -> bool:  # noqa: ARG001
    if not m.transients:
        return False
    mean_attack = sum(t.attack_ms for t in m.transients) / len(m.transients)
    return mean_attack > SOFT_TRANSIENT_MEAN_MS


# (technique chunk id, trigger predicate, paired skill chunk id, skill level it applies to)
# The skill chunk is only included alongside its technique when the trigger
# fires AND the persona is at the matching skill tier - otherwise it's
# generic advice with nothing in this analysis to ground it.
_TECHNIQUE_TRIGGERS: list[tuple[str, Callable[[Measurements, bool], bool], str | None, str | None]] = [
    ("technique_crest_factor", _crest_factor_low, "skill_beginner_overcompression", "beginner"),
    ("technique_low_mid_mud", _low_mid_mud, "skill_beginner_low_mid_stacking", "beginner"),
    ("technique_stereo_bass_mono", _wide_low_stereo, "skill_intermediate_mono_compat", "intermediate"),
    ("technique_timing_swing", _loose_timing, None, None),
    ("technique_thin_low_end", _thin_low_end, "skill_beginner_hpf_default", "beginner"),
    ("technique_transient_attack", _soft_transients, None, None),
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
    has_reference: bool = False,
) -> list[KnowledgeChunk]:
    """Genre target + triggered technique/skill chunks, capped at KNOWLEDGE_TOP_K.

    Retrieval is deterministic tag/trigger matching against already-computed
    measurements and the genre string - not semantic search - so it's
    unit-testable with a synthetic Measurements object and never returns
    something ungrounded in what was actually detected. `has_reference` gates
    the two triggers that compare project vs. reference band energy - without
    it, `reference_db` is a 0.0 default rather than a real measurement (see
    pipeline/measurements.py._eq_comparison), so those comparisons would be
    meaningless. Defaults to False (the safer assumption) rather than True,
    so a caller that forgets to pass it doesn't get spurious triggers.
    """
    results: list[KnowledgeChunk] = []

    genre_chunk = _match_genre(genre, preferred_genres)
    if genre_chunk:
        results.append(genre_chunk)

    for chunk_id, predicate, skill_chunk_id, paired_skill_level in _TECHNIQUE_TRIGGERS:
        if not predicate(measurements, has_reference):
            continue

        results.append(ALL_CHUNKS[chunk_id])
        if len(results) >= KNOWLEDGE_TOP_K:
            return results[:KNOWLEDGE_TOP_K]

        if skill_chunk_id and skill_level == paired_skill_level:
            results.append(ALL_CHUNKS[skill_chunk_id])
            if len(results) >= KNOWLEDGE_TOP_K:
                return results[:KNOWLEDGE_TOP_K]

    return results
