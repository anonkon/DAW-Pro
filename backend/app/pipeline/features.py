from __future__ import annotations

import numpy as np

FREQ_BANDS = [
    ("low", 20.0, 250.0),
    ("low-mid", 250.0, 500.0),
    ("mid", 500.0, 2000.0),
    ("high-mid", 2000.0, 6000.0),
    ("high", 6000.0, 20000.0),
]

# Resolution of the spectrum curve handed to the dashboard. The five semantic
# bands above stay as-is for the AI's reasoning; this is purely for drawing a
# continuous curve rather than five steps.
SPECTRUM_POINTS = 64
SPECTRUM_HZ_MIN = 20.0
SPECTRUM_HZ_MAX = 20000.0

# 2048 gives ~21Hz bins at 44.1kHz, which cannot resolve a 50-70Hz problem in
# the sub-bass at all. 8192 gets us to ~5Hz.
N_FFT = 8192
HOP_LENGTH = 2048

# Onsets are scored against a 16th-note grid, not the quarter-note beat grid -
# otherwise every hat on an 8th reads as maximally off-time.
GRID_SUBDIVISION = 4


def extract_features(audio_path: str, host_bpm: float | None = None) -> dict:
    import librosa

    # mono=False so L/R phase correlation stays computable. Mono sources come
    # back 1-D, stereo as (2, n) - _as_mono collapses whichever we get.
    y_raw, sr = librosa.load(audio_path, sr=None, mono=False)
    y = _as_mono(y_raw)

    rms = librosa.feature.rms(y=y)[0]

    # Raw STFT magnitude scales with n_fft and the window, so converting it
    # straight to dB gives numbers with no reference - a full-scale sine reads
    # +66dB rather than 0. Dividing by the window's coherent gain puts band and
    # spectrum dB on the same dBFS scale as peak_db and rms_db, so every dB
    # figure in the UI means the same thing.
    window_gain = float(librosa.filters.get_window("hann", N_FFT, fftbins=True).sum()) / 2.0
    stft_mag = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)) / window_gain
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

    band_energy_db: dict[str, float] = {}
    for label, lo, hi in FREQ_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            band_energy_db[label] = -120.0
            continue
        # Total power in the band, not mean magnitude across its bins. Averaging
        # magnitude makes a band read quieter simply for being wider, since most
        # bins in a wide band are near-empty - the 6-20kHz band spans ~2600 bins
        # and would score low on width alone.
        power = np.sum(stft_mag[mask] ** 2, axis=0).mean()
        band_energy_db[label] = float(10.0 * np.log10(max(power, 1e-12)))

    # backtrack=True walks each detection back to the preceding energy minimum,
    # i.e. where the attack actually begins. Without it every onset lands ~20ms
    # late and the whole track reads as behind the beat.
    onsets_sec = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=True)
    tempo, beat_times = _beats(y, sr)

    return {
        "duration_sec": float(librosa.get_duration(y=y, sr=sr)),
        "rms_mean_db": float(librosa.amplitude_to_db(np.array([rms.mean()]))[0]),
        "peak_db": _peak_db(y),
        "band_energy_db": band_energy_db,
        "spectrum_curve": _spectrum_curve(stft_mag, freqs),
        "onsets_sec": [float(t) for t in onsets_sec],
        "tempo_bpm": tempo,
        "beat_times_sec": beat_times,
        **_timing(onsets_sec, beat_times, host_bpm),
        "phase_correlation": _phase_correlation(y_raw),
        "is_stereo": bool(np.ndim(y_raw) == 2 and y_raw.shape[0] >= 2),
    }


def _as_mono(y_raw: np.ndarray) -> np.ndarray:
    return y_raw.mean(axis=0) if np.ndim(y_raw) == 2 else y_raw


def _peak_db(y: np.ndarray) -> float:
    import librosa

    peak = float(np.max(np.abs(y))) if y.size else 0.0
    # Silence would be -inf dB; floor it so the value stays JSON-serialisable.
    return float(librosa.amplitude_to_db(np.array([max(peak, 1e-10)]))[0])


def _spectrum_curve(stft_mag: np.ndarray, freqs: np.ndarray) -> list[dict]:
    """Time-averaged spectrum on log-spaced points, as {hz, db} in dBFS.

    Each point is the loudest bin in its bucket, the way a spectrum analyser
    display works. Interpolating between bin values instead would erase narrow
    peaks: near 1kHz the 64 log points sit ~110Hz apart while a bin is ~5Hz
    wide, so a pure tone falls between samples and reads ~48dB low.

    Buckets below roughly 40Hz are narrower than a single bin and contain none,
    so those fall back to interpolation - there is no finer detail to preserve
    down there anyway.
    """
    import librosa

    frame_mean = stft_mag.mean(axis=1)  # average across time
    db_per_bin = librosa.amplitude_to_db(np.maximum(frame_mean, 1e-10))

    usable = freqs > 0
    centres = np.geomspace(SPECTRUM_HZ_MIN, SPECTRUM_HZ_MAX, SPECTRUM_POINTS)
    edges = np.sqrt(centres[:-1] * centres[1:])  # geometric midpoints
    edges = np.concatenate([[SPECTRUM_HZ_MIN], edges, [SPECTRUM_HZ_MAX]])

    interpolated = np.interp(np.log10(centres), np.log10(freqs[usable]), db_per_bin[usable])

    points: list[dict] = []
    for i, hz in enumerate(centres):
        mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
        db = float(db_per_bin[mask].max()) if mask.any() else float(interpolated[i])
        points.append({"hz": float(hz), "db": db})
    return points


def _beats(y: np.ndarray, sr: float) -> tuple[float | None, list[float]]:
    import librosa

    try:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    except Exception:  # noqa: BLE001 - short or silent input defeats beat tracking
        return None, []

    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    return float(np.atleast_1d(tempo)[0]), [float(t) for t in beat_times]


def _grid(beat_times: list[float]) -> np.ndarray:
    """Beat times subdivided into a 16th-note grid."""
    beats = np.asarray(beat_times, dtype=float)
    steps = np.arange(GRID_SUBDIVISION) / GRID_SUBDIVISION
    intervals = np.diff(beats, append=beats[-1] + np.median(np.diff(beats)))
    return np.sort((beats[:, None] + intervals[:, None] * steps[None, :]).ravel())


def _timing(onsets_sec: np.ndarray, beat_times: list[float], host_bpm: float | None) -> dict:
    """Timing of onsets against the 16th-note grid, via circular statistics.

    Each onset is reduced to its phase within one grid step, so the measurement
    needs no grid origin - only the step size. The mean resultant length R of
    those phases is the tightness: 1.0 is perfectly locked, 0.0 is uniformly
    scattered. The mean angle is the systematic offset, i.e. consistently
    playing behind or ahead of the grid.

    Separating the two matters musically. A part sitting 20ms behind the beat
    every single time is tight and intentional; random +/-20ms is sloppy. One
    deviation figure cannot tell those apart, and onset detection reports
    transients slightly late anyway, which the offset absorbs.

    host_bpm is the DAW's own tempo, forwarded by the plugin. Prefer it: a grid
    estimated by beat_track is derived from the very audio being measured, so
    it drifts along with any timing error and the result is circular. Falling
    back to it is better than nothing but the offset is not meaningful, since
    an estimated grid shifts with the track.
    """
    empty = {
        "timing_offset_ms": None,
        "timing_scatter_ms": None,
        "rhythmic_cohesion": None,
        "timing_grid_source": None,
    }
    if len(onsets_sec) == 0:
        return empty

    if host_bpm and host_bpm > 0:
        step = 60.0 / host_bpm / GRID_SUBDIVISION
        source = "host_bpm"
    elif len(beat_times) >= 2:
        step = float(np.median(np.diff(np.asarray(beat_times, dtype=float)))) / GRID_SUBDIVISION
        source = "estimated"
    else:
        return empty

    if step <= 0:
        return empty

    phases = 2.0 * np.pi * (np.asarray(onsets_sec, dtype=float) / step % 1.0)
    resultant = np.mean(np.exp(1j * phases))
    concentration = float(np.abs(resultant))  # 1.0 locked, 0.0 uniform

    # Mean angle back to seconds, wrapped into [-step/2, +step/2].
    offset = float(np.angle(resultant)) / (2.0 * np.pi) * step
    if offset > step / 2:
        offset -= step

    # Circular standard deviation, valid while onsets stay reasonably clustered.
    scatter = float(np.sqrt(-2.0 * np.log(concentration))) / (2.0 * np.pi) * step if concentration > 0 else step

    return {
        "timing_offset_ms": round(offset * 1000.0, 1),
        "timing_scatter_ms": round(min(scatter, step) * 1000.0, 1),
        "rhythmic_cohesion": round(concentration * 100.0, 1),
        "timing_grid_source": source,
    }


def _phase_correlation(y_raw: np.ndarray) -> float | None:
    """Pearson correlation between L and R. +1 in phase, 0 wide, -1 inverted.

    None for mono sources, where the measurement is meaningless rather than zero.
    """
    if np.ndim(y_raw) != 2 or y_raw.shape[0] < 2:
        return None

    left, right = y_raw[0], y_raw[1]
    if not np.any(left) or not np.any(right):
        return None

    correlation = float(np.corrcoef(left, right)[0, 1])
    return None if np.isnan(correlation) else round(correlation, 3)
