from __future__ import annotations

import librosa
import numpy as np

FREQ_BANDS = [
    ("low", 20.0, 250.0),
    ("low-mid", 250.0, 500.0),
    ("mid", 500.0, 2000.0),
    ("high-mid", 2000.0, 6000.0),
    ("high", 6000.0, 20000.0),
]


def extract_features(audio_path: str) -> dict:
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    stft_mag = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    band_energy_db: dict[str, float] = {}
    for label, lo, hi in FREQ_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        band_mag = stft_mag[mask].mean(axis=0) if mask.any() else np.zeros_like(stft_mag[0])
        band_energy_db[label] = float(np.mean(librosa.amplitude_to_db(band_mag)))

    onsets_sec = librosa.onset.onset_detect(y=y, sr=sr, units="time")

    return {
        "duration_sec": float(librosa.get_duration(y=y, sr=sr)),
        "rms_mean_db": float(librosa.amplitude_to_db(np.array([rms.mean()]))[0]),
        "band_energy_db": band_energy_db,
        "onsets_sec": [float(t) for t in onsets_sec],
    }
