from __future__ import annotations

import numpy as np

from ..schemas import (
    FrequencyBand,
    Loudness,
    LoudnessComparison,
    Measurements,
    PhaseAnalysis,
    SpectrumComparison,
    SpectrumPoint,
    StemSummary,
    StereoWidthBand,
    TimingAnalysis,
    TimingEvent,
    TransientEvent,
)
from .features import FREQ_BANDS, MAX_TRANSIENT_EVENTS

# How far apart two tempos can be before bar-relative onset pairing stops
# meaning anything.
TEMPO_MATCH_TOLERANCE = 0.02  # 2%

# Pairing window, as a fraction of one bar.
PAIR_WINDOW = 0.125  # half a beat in 4/4

MAX_TIMING_EVENTS = 32


def build_measurements(project: dict, reference: dict, host_bpm: float | None) -> Measurements:
    """Assemble every computed value the dashboard renders.

    Nothing here goes near the LLM - these are measurements, and the model is
    given them as context rather than asked to produce them.
    """
    return Measurements(
        eq_comparison=_eq_comparison(project, reference),
        spectrum=SpectrumComparison(
            project=_spectrum(project),
            reference=_spectrum(reference),
        ),
        timing=_timing(project, reference, host_bpm),
        phase=_phase(project),
        loudness=LoudnessComparison(
            project=_loudness(project),
            reference=_loudness(reference),
        ),
        stereo_width=_stereo_width(project),
        transients=_transients(project),
        key=project.get("key"),
        key_confidence=project.get("key_confidence"),
        reference_key=reference.get("key"),
        reference_key_confidence=reference.get("key_confidence"),
        tempo_bpm=host_bpm or project.get("tempo_bpm"),
        stems=_stems(project),
    )


def _eq_comparison(project: dict, reference: dict) -> list[FrequencyBand]:
    project_bands = project.get("band_energy_db", {})
    reference_bands = reference.get("band_energy_db", {})
    return [
        FrequencyBand(
            label=label,
            hz_low=lo,
            hz_high=hi,
            project_db=float(project_bands.get(label, 0.0)),
            reference_db=float(reference_bands.get(label, 0.0)),
        )
        for label, lo, hi in FREQ_BANDS
    ]


def _spectrum(features: dict) -> list[SpectrumPoint]:
    return [SpectrumPoint(hz=p["hz"], db=p["db"]) for p in features.get("spectrum_curve", [])]


def _loudness(features: dict) -> Loudness:
    return Loudness(
        peak_db=features.get("peak_db"),
        rms_db=features.get("rms_mean_db"),
        crest_factor_db=features.get("crest_factor_db"),
        integrated_lufs=features.get("integrated_lufs"),
        short_term_lufs=features.get("short_term_lufs"),
        true_peak_dbtp=features.get("true_peak_dbtp"),
        loudness_range_lu=features.get("loudness_range_lu"),
    )


def _stereo_width(project: dict) -> list[StereoWidthBand]:
    width_db = project.get("stereo_width_db")
    if not width_db:
        return []
    return [
        StereoWidthBand(label=label, hz_low=lo, hz_high=hi, width_db=width_db[label])
        for label, lo, hi in FREQ_BANDS
        if label in width_db
    ]


def _transients(project: dict) -> list[TransientEvent]:
    events = project.get("attack_events", [])[:MAX_TRANSIENT_EVENTS]
    return [TransientEvent(onset_sec=e["onset_sec"], attack_ms=e["attack_ms"]) for e in events]


def _stems(project: dict) -> dict[str, StemSummary]:
    """Per-instrument breakdown from the Demucs stems already extracted in
    jobs.py - the same feature dict shape as the full mix, just narrower."""
    stems = project.get("stems", {})
    return {
        name: StemSummary(band_energy_db=features.get("band_energy_db", {}), loudness=_loudness(features))
        for name, features in stems.items()
    }


def _phase(features: dict) -> PhaseAnalysis:
    correlation = features.get("phase_correlation")
    if correlation is None:
        # Distinguishes "mono source, nothing to measure" from "measured 0.0",
        # which would mean a fully decorrelated stereo field.
        return PhaseAnalysis(correlation=None, verdict="mono" if not features else None)

    if correlation < 0.0:
        verdict = "problematic"  # partial cancellation when summed to mono
    elif correlation < 0.5:
        verdict = "wide"
    else:
        verdict = "in_phase"
    return PhaseAnalysis(correlation=correlation, verdict=verdict)


def _timing(project: dict, reference: dict, host_bpm: float | None) -> TimingAnalysis:
    analysis = TimingAnalysis(
        rhythmic_cohesion=project.get("rhythmic_cohesion"),
        timing_offset_ms=project.get("timing_offset_ms"),
        timing_scatter_ms=project.get("timing_scatter_ms"),
        grid_source=project.get("timing_grid_source"),
        events=_pair_onsets(project, reference, host_bpm),
    )
    return analysis


def _pair_onsets(project: dict, reference: dict, host_bpm: float | None) -> list[TimingEvent]:
    """Pair reference onsets with project onsets by position within the bar.

    Absolute timestamps are useless here - the reference is a different record
    that starts at its own point in its own arrangement. What survives the
    comparison is where each hit sits inside a bar, so both sets are folded into
    one bar and matched there.

    Returns nothing unless the two tempos agree: at different tempos, bar
    positions describe different musical instants and any pairing would be
    invented.
    """
    project_bpm = host_bpm or project.get("tempo_bpm")
    reference_bpm = reference.get("tempo_bpm")
    if not project_bpm or not reference_bpm:
        return []

    if abs(project_bpm - reference_bpm) / reference_bpm > TEMPO_MATCH_TOLERANCE:
        return []

    project_onsets = np.asarray(project.get("onsets_sec", []), dtype=float)
    reference_onsets = np.asarray(reference.get("onsets_sec", []), dtype=float)
    if project_onsets.size == 0 or reference_onsets.size == 0:
        return []

    bar = 60.0 / float(project_bpm) * 4.0  # 4/4 assumed; see time_signature TODO
    window = bar * PAIR_WINDOW

    project_phase = project_onsets % bar
    events: list[TimingEvent] = []

    for reference_sec in sorted(reference_onsets)[:MAX_TIMING_EVENTS]:
        reference_phase = reference_sec % bar
        # Circular distance within the bar, so a hit just before the barline
        # matches one just after it.
        raw = project_phase - reference_phase
        delta = (raw + bar / 2) % bar - bar / 2

        closest = int(np.abs(delta).argmin())
        if abs(delta[closest]) > window:
            events.append(TimingEvent(reference_sec=float(reference_sec), severity="warning"))
            continue

        delta_ms = float(delta[closest]) * 1000.0
        events.append(
            TimingEvent(
                reference_sec=float(reference_sec),
                project_sec=float(project_onsets[closest]),
                delta_ms=round(delta_ms, 1),
                severity=_severity(abs(delta_ms)),
            )
        )
    return events


def _severity(abs_delta_ms: float) -> str:
    if abs_delta_ms > 40.0:
        return "critical"
    if abs_delta_ms > 20.0:
        return "warning"
    return "info"
