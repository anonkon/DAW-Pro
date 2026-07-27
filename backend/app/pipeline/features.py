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

# ITU-R BS.1770-5 Annex 1: K-weighting is a two-stage IIR filter (stage 1
# models the acoustic effect of the head, stage 2 is a high-pass "RLB"
# curve), coefficients specified at 48kHz (Tables 1-2). We resample to 48kHz
# before filtering rather than re-deriving coefficients for the source rate,
# which the spec doesn't give in closed form - it explicitly allows this
# ("implementations at other sampling rates will require different
# coefficient values... tests have shown the algorithm is not sensitive to
# small variations").
K_WEIGHT_SR = 48000
_K_STAGE1_B = (1.53512485958697, -2.69169618940638, 1.19839281085285)
_K_STAGE1_A = (1.0, -1.69065929318241, 0.73248077421585)
_K_STAGE2_B = (1.0, -2.0, 1.0)
_K_STAGE2_A = (1.0, -1.99004745483398, 0.99007225036621)

# BS.1770-5 Annex 1 eq. (3): 400ms gating blocks, 75% overlap.
GATING_BLOCK_SEC = 0.4
GATING_OVERLAP = 0.75
# BS.1770-5 eq. (6)-(7): absolute gate at -70 LUFS, relative gate 10 LU below
# the absolute-gated mean loudness. Two-stage energy-domain gating, not a
# simple threshold on individual blocks - see _gated_mean_loudness.
ABSOLUTE_GATE_LUFS = -70.0
INTEGRATED_RELATIVE_GATE_LU = 10.0

# EBU R128: Loudness Range (LRA) is built from short-term loudness values on
# a 3-second window. R128 itself doesn't specify the hop or LRA's own gating
# in closed form (that's EBU Tech 3342, not fetched here) - 100ms hop and a
# stricter -20LU relative gate (vs. integrated loudness's -10LU) before
# taking the 10th-95th percentile spread are the values used by the de facto
# reference implementation (libebur128), adopted here rather than the -10LU
# integrated-loudness gate, since LRA is specifically trying to exclude
# near-silence, not just find "foreground" content.
LRA_BLOCK_SEC = 3.0
LRA_HOP_SEC = 0.1
LRA_RELATIVE_GATE_LU = 20.0
LRA_LOW_PCT = 10.0
LRA_HIGH_PCT = 95.0

# ITU-R BS.1770-5 Annex 2: 4x oversampling (at least 192kHz total) is the
# summary-step guidance for estimating true-peak level between samples. The
# spec's own reference filter is a specific 48-tap/4-phase FIR; we use
# scipy's polyphase resampler instead, which oversamples and low-pass
# filters in one step - the spec permits any filter that "gives similar or
# superior results" to its reference implementation, and also notes the
# 12.04dB attenuation step it describes is "not necessary if the
# calculations are performed in floating point," which we do.
TRUE_PEAK_OVERSAMPLE = 4

# Long enough to catch a slow pad's attack, short enough that the next onset
# rarely intrudes into the window.
ATTACK_WINDOW_SEC = 0.05
ATTACK_LOW_PCT = 0.1
ATTACK_HIGH_PCT = 0.9
# Mirrors MAX_TIMING_EVENTS in measurements.py - keeps the payload bounded on
# dense material instead of emitting one entry per onset in a whole track.
MAX_TRANSIENT_EVENTS = 32

# Krumhansl-Schmuckler key profiles (Krumhansl & Kessler 1982), correlated
# against a track's mean chroma vector to pick the best-fitting key.
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KEY_CONFIDENCE_FLOOR = 0.3  # below this the best-fit correlation is too weak to call a key


def extract_features(audio_path: str, host_bpm: float | None = None) -> dict:
    import librosa

    # mono=False so L/R phase correlation stays computable. Mono sources come
    # back 1-D, stereo as (2, n) - _as_mono collapses whichever we get.
    y_raw, sr = librosa.load(audio_path, sr=None, mono=False)
    y = _as_mono(y_raw)

    rms = librosa.feature.rms(y=y)[0]
    rms_mean_db = float(librosa.amplitude_to_db(np.array([rms.mean()]))[0])
    peak_db = _peak_db(y)

    # Raw STFT magnitude scales with n_fft and the window, so converting it
    # straight to dB gives numbers with no reference - a full-scale sine reads
    # +66dB rather than 0. Dividing by the window's coherent gain puts band and
    # spectrum dB on the same dBFS scale as peak_db and rms_db, so every dB
    # figure in the UI means the same thing.
    window_gain = float(librosa.filters.get_window("hann", N_FFT, fftbins=True).sum()) / 2.0
    stft_mag = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH)) / window_gain
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    band_energy_db = _band_energy_db(stft_mag, freqs)

    # backtrack=True walks each detection back to the preceding energy minimum,
    # i.e. where the attack actually begins. Without it every onset lands ~20ms
    # late and the whole track reads as behind the beat.
    onsets_sec = librosa.onset.onset_detect(y=y, sr=sr, units="time", backtrack=True)
    tempo, beat_times = _beats(y, sr)

    return {
        "duration_sec": float(librosa.get_duration(y=y, sr=sr)),
        "rms_mean_db": rms_mean_db,
        "peak_db": peak_db,
        "crest_factor_db": round(peak_db - rms_mean_db, 2),
        "band_energy_db": band_energy_db,
        "spectrum_curve": _spectrum_curve(stft_mag, freqs),
        "onsets_sec": [float(t) for t in onsets_sec],
        "tempo_bpm": tempo,
        "beat_times_sec": beat_times,
        **_timing(onsets_sec, beat_times, host_bpm),
        "phase_correlation": _phase_correlation(y_raw),
        "is_stereo": bool(np.ndim(y_raw) == 2 and y_raw.shape[0] >= 2),
        **_loudness_lufs(y_raw, sr),
        "true_peak_dbtp": _true_peak_dbtp(y),
        "stereo_width_db": _stereo_width_db(y_raw, band_energy_db, freqs, window_gain),
        "attack_events": _attack_times_ms(y, sr, onsets_sec),
        **_estimate_key(y, sr),
    }


def _as_mono(y_raw: np.ndarray) -> np.ndarray:
    return y_raw.mean(axis=0) if np.ndim(y_raw) == 2 else y_raw


def _peak_db(y: np.ndarray) -> float:
    import librosa

    peak = float(np.max(np.abs(y))) if y.size else 0.0
    # Silence would be -inf dB; floor it so the value stays JSON-serialisable.
    return float(librosa.amplitude_to_db(np.array([max(peak, 1e-10)]))[0])


def _band_energy_db(stft_mag: np.ndarray, freqs: np.ndarray) -> dict[str, float]:
    """Per-band power in dBFS, using the five semantic FREQ_BANDS.

    Total power in the band, not mean magnitude across its bins. Averaging
    magnitude makes a band read quieter simply for being wider, since most
    bins in a wide band are near-empty - the 6-20kHz band spans ~2600 bins
    and would score low on width alone.
    """
    band_energy_db: dict[str, float] = {}
    for label, lo, hi in FREQ_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            band_energy_db[label] = -120.0
            continue
        power = np.sum(stft_mag[mask] ** 2, axis=0).mean()
        band_energy_db[label] = float(10.0 * np.log10(max(power, 1e-12)))
    return band_energy_db


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


def _k_weighted_power(y_raw: np.ndarray, sr: float) -> np.ndarray:
    """Per-sample K-weighted power, summed across channels.

    ITU-R BS.1770-5 Annex 1 eq. (1)-(2): each channel is K-weighted then
    squared, and channels are summed with weight G_i before the log. We only
    ever have L/R/mono (G_i = 1.0 for all of L/R/C - no surround/LFE inputs),
    so the weighted sum is just a plain sum of per-channel power.
    """
    import scipy.signal as signal

    channels = y_raw if np.ndim(y_raw) == 2 else y_raw[np.newaxis, :]
    if int(round(sr)) != K_WEIGHT_SR:
        channels = np.stack([signal.resample_poly(ch, K_WEIGHT_SR, int(round(sr))) for ch in channels])

    power = np.zeros(channels.shape[1])
    for channel in channels:
        stage1 = signal.lfilter(_K_STAGE1_B, _K_STAGE1_A, channel)
        weighted = signal.lfilter(_K_STAGE2_B, _K_STAGE2_A, stage1)
        power += weighted**2
    return power


def _block_loudness(power: np.ndarray, block_sec: float, hop_sec: float) -> np.ndarray:
    """Ungated block loudness (BS.1770-5 eq. (3)-(4)) at K_WEIGHT_SR, in LKFS."""
    block = int(round(block_sec * K_WEIGHT_SR))
    hop = int(round(hop_sec * K_WEIGHT_SR))
    if block <= 0 or power.size < block:
        return np.array([])

    starts = np.arange(0, power.size - block + 1, hop)
    block_mean_power = np.array([power[s : s + block].mean() for s in starts])
    with np.errstate(divide="ignore"):
        return -0.691 + 10.0 * np.log10(np.maximum(block_mean_power, 1e-12))


def _energy_mean_db(values_db: np.ndarray) -> float:
    """Mean of dB values in the linear (power) domain, not the log domain -
    matches BS.1770-5's own sum-then-log structure (eq. (5))."""
    linear = 10.0 ** (values_db / 10.0)
    return float(10.0 * np.log10(linear.mean()))


def _gated_mean_loudness(block_loudness: np.ndarray, relative_gate_lu: float) -> tuple[float | None, np.ndarray]:
    """Two-stage energy-domain gating (BS.1770-5 eq. (5)-(7)): drop blocks
    below the absolute gate, take the energy mean of what's left, then drop
    blocks below (that mean - relative_gate_lu) and take the mean again."""
    absolute_gated = block_loudness[block_loudness > ABSOLUTE_GATE_LUFS]
    if absolute_gated.size == 0:
        return None, absolute_gated

    absolute_mean = _energy_mean_db(absolute_gated)
    relative_gated = absolute_gated[absolute_gated > (absolute_mean - relative_gate_lu)]
    if relative_gated.size == 0:
        return absolute_mean, absolute_gated
    return _energy_mean_db(relative_gated), relative_gated


def _loudness_lufs(y_raw: np.ndarray, sr: float) -> dict:
    """Integrated LUFS (ITU-R BS.1770-5), a representative short-term LUFS,
    and Loudness Range (EBU R128) - implemented directly from the K-weighting
    filter and gating equations in the published specs (see the constants
    above) rather than approximated against a library's black-box output.
    """
    power = _k_weighted_power(y_raw, sr)
    if power.size == 0:
        return {"integrated_lufs": None, "short_term_lufs": None, "loudness_range_lu": None}

    integrated_blocks = _block_loudness(power, GATING_BLOCK_SEC, GATING_BLOCK_SEC * (1.0 - GATING_OVERLAP))
    integrated_lufs, _ = _gated_mean_loudness(integrated_blocks, INTEGRATED_RELATIVE_GATE_LU)

    short_term_blocks = _block_loudness(power, LRA_BLOCK_SEC, LRA_HOP_SEC)
    short_term_lufs = None
    lra = None
    if short_term_blocks.size:
        short_term_lufs, lra_blocks = _gated_mean_loudness(short_term_blocks, LRA_RELATIVE_GATE_LU)
        if lra_blocks.size >= 2:
            lra = round(float(np.percentile(lra_blocks, LRA_HIGH_PCT) - np.percentile(lra_blocks, LRA_LOW_PCT)), 2)

    return {
        "integrated_lufs": round(integrated_lufs, 2) if integrated_lufs is not None else None,
        "short_term_lufs": round(short_term_lufs, 2) if short_term_lufs is not None else None,
        "loudness_range_lu": lra,
    }


def _true_peak_dbtp(y: np.ndarray) -> float | None:
    """Oversampled peak level in dBTP (true peak), per ITU-R BS.1770-5 Annex 2.

    Sample-peak metering misses inter-sample peaks that a real D/A
    reconstruction filter would produce - a signal sitting right at 0dBFS on
    consecutive samples can reconstruct several tenths of a dB higher.
    Oversampling by TRUE_PEAK_OVERSAMPLE approximates that reconstructed
    peak - see the constant's definition above for how this maps onto the
    spec's 5-stage reference algorithm.
    """
    import librosa
    import scipy.signal as signal

    if y.size == 0:
        return None
    upsampled = signal.resample_poly(y, TRUE_PEAK_OVERSAMPLE, 1)
    peak = float(np.max(np.abs(upsampled))) if upsampled.size else 0.0
    return round(float(librosa.amplitude_to_db(np.array([max(peak, 1e-10)]))[0]), 2)


def _stereo_width_db(
    y_raw: np.ndarray, mid_band_energy_db: dict[str, float], freqs: np.ndarray, window_gain: float
) -> dict[str, float] | None:
    """Per-band side-energy relative to mid-energy, in dB.

    Positive means that band is wider than centred; strongly positive in the
    low bands is the classic "wide bass" problem, since summing to mono
    partially cancels it. Reuses the mid-signal spectrum already computed for
    _as_mono(y_raw) - mid is exactly (L+R)/2, the same average _as_mono takes
    - so only the side signal (L-R)/2 needs a fresh STFT here.

    None for mono sources - there's no stereo image to measure.
    """
    import librosa

    if np.ndim(y_raw) != 2 or y_raw.shape[0] < 2:
        return None

    left, right = y_raw[0], y_raw[1]
    side = (left - right) / 2.0
    side_mag = np.abs(librosa.stft(side, n_fft=N_FFT, hop_length=HOP_LENGTH)) / window_gain
    side_band_energy_db = _band_energy_db(side_mag, freqs)

    return {
        label: round(side_band_energy_db[label] - mid_band_energy_db[label], 2) for label in mid_band_energy_db
    }


def _attack_times_ms(y: np.ndarray, sr: float, onsets_sec: np.ndarray) -> list[dict]:
    """10%-90% rise time of the amplitude envelope after each onset, in ms.

    Envelope via the Hilbert transform's analytic-signal magnitude - cheap
    and standard for attack-time estimation, and needs no separate filter
    design the way an RMS envelope with a chosen window would. Onsets whose
    window runs off the end of the file, or whose envelope never clearly
    rises from 10% to 90% of its local peak (e.g. a sustained swell with no
    real transient), are skipped rather than given a fabricated value.
    """
    import scipy.signal as signal

    if len(onsets_sec) == 0:
        return []

    window = int(ATTACK_WINDOW_SEC * sr)
    events: list[dict] = []
    for onset in onsets_sec[:MAX_TRANSIENT_EVENTS]:
        start = int(onset * sr)
        end = start + window
        if window <= 0 or end > y.size:
            continue
        envelope = np.abs(signal.hilbert(y[start:end]))
        peak = float(envelope.max())
        if peak <= 1e-8:
            continue

        low_thresh = peak * ATTACK_LOW_PCT
        high_thresh = peak * ATTACK_HIGH_PCT
        if not np.any(envelope >= high_thresh) or not np.any(envelope >= low_thresh):
            continue
        above_low = int(np.argmax(envelope >= low_thresh))
        above_high = int(np.argmax(envelope >= high_thresh))
        if above_high <= above_low:
            continue

        events.append(
            {
                "onset_sec": float(onset),
                "attack_ms": round((above_high - above_low) / sr * 1000.0, 1),
            }
        )
    return events


def _estimate_key(y: np.ndarray, sr: float) -> dict:
    """Best-fit key via Krumhansl-Schmuckler profile correlation on chroma.

    Correlates the track's mean chroma vector against all 24 major/minor key
    profiles and reports the best match plus its correlation as a confidence
    score - a poor best-fit score (ambiguous or atonal material, or a drum
    stem with no clear pitch content) is reported as low confidence rather
    than a false-confident guess.
    """
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mean_chroma = chroma.mean(axis=1)
    if not np.any(mean_chroma):
        return {"key": None, "key_confidence": None}

    best_label: str | None = None
    best_score = -2.0
    for tonic in range(12):
        for mode, profile in (("major", _MAJOR_PROFILE), ("minor", _MINOR_PROFILE)):
            rotated = np.roll(profile, tonic)
            score = float(np.corrcoef(mean_chroma, rotated)[0, 1])
            if np.isfinite(score) and score > best_score:
                best_score = score
                best_label = f"{_PITCH_CLASSES[tonic]} {mode}"

    if best_label is None or best_score < KEY_CONFIDENCE_FLOOR:
        return {"key": None, "key_confidence": round(best_score, 3) if best_label else None}
    return {"key": best_label, "key_confidence": round(best_score, 3)}
