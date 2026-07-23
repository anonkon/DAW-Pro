"""Generates short synthetic test tracks for exercising the DAWpro pipeline
end-to-end (Demucs stem separation + Librosa feature extraction + Gemini
analysis) without depending on an external audio download.

Not for production use -- just enough spectral/rhythmic content (kick,
bass, pad, hats) to give Demucs something to separate and Librosa something
to measure.
"""
import numpy as np
import soundfile as sf

SR = 44100


def kick(t_len=0.15, freq=60.0):
    t = np.linspace(0, t_len, int(SR * t_len), endpoint=False)
    env = np.exp(-t * 18)
    pitch_env = freq * np.exp(-t * 25) + 40
    phase = 2 * np.pi * np.cumsum(pitch_env) / SR
    return (np.sin(phase) * env * 0.9).astype(np.float64)


def hat(t_len=0.05):
    n = int(SR * t_len)
    env = np.exp(-np.linspace(0, t_len, n) * 40)
    noise = np.random.default_rng(0).standard_normal(n)
    return (noise * env * 0.25).astype(np.float64)


def bass_note(freq, t_len):
    t = np.linspace(0, t_len, int(SR * t_len), endpoint=False)
    env = np.clip(np.minimum(t * 30, (t_len - t) * 15), 0, 1)
    tone = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)
    return (tone * env * 0.5).astype(np.float64)


def pad_chord(freqs, t_len):
    t = np.linspace(0, t_len, int(SR * t_len), endpoint=False)
    env = np.clip(np.minimum(t * 4, (t_len - t) * 4), 0, 1)
    tone = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    return (tone * env * 0.3).astype(np.float64)


def build_track(duration_sec, bpm, bass_root=55.0, seed=0):
    n = int(SR * duration_sec)
    out = np.zeros(n)
    beat = 60.0 / bpm

    # drums: kick on 1 and 3, hats on every 8th
    t = 0.0
    while t < duration_sec:
        beat_in_bar = (t / beat) % 4
        k = kick()
        if beat_in_bar < 1e-6 or abs(beat_in_bar - 2) < 1e-6:
            s = int(t * SR)
            e = min(n, s + len(k))
            out[s:e] += k[: e - s]
        t += beat

    t = 0.0
    while t < duration_sec:
        h = hat()
        s = int(t * SR)
        e = min(n, s + len(h))
        out[s:e] += h[: e - s]
        t += beat / 2

    # bassline: root, root, fifth, root pattern per bar
    bar = beat * 4
    ratios = [1.0, 1.0, 1.5, 1.0]
    b = 0.0
    i = 0
    while b < duration_sec:
        note_len = bar / 4
        freq = bass_root * ratios[i % len(ratios)]
        bn = bass_note(freq, note_len * 0.9)
        s = int(b * SR)
        e = min(n, s + len(bn))
        out[s:e] += bn[: e - s]
        b += note_len
        i += 1

    # pad chord underneath, changes every 2 bars
    root = bass_root * 4
    chords = [[root, root * 1.25, root * 1.5], [root * 0.9, root * 1.125, root * 1.5]]
    c = 0.0
    j = 0
    while c < duration_sec:
        clen = min(bar * 2, duration_sec - c)
        pc = pad_chord(chords[j % len(chords)], clen)
        s = int(c * SR)
        e = min(n, s + len(pc))
        out[s:e] += pc[: e - s]
        c += bar * 2
        j += 1

    out = out / (np.max(np.abs(out)) + 1e-9) * 0.85
    stereo = np.stack([out, out * 0.98], axis=1)
    return stereo.astype(np.float32)


if __name__ == "__main__":
    reference = build_track(duration_sec=14, bpm=120, bass_root=55.0)
    sf.write("reference_track.wav", reference, SR)

    capture = build_track(duration_sec=10, bpm=120, bass_root=55.0)
    sf.write("capture_track.wav", capture, SR)

    print("wrote reference_track.wav and capture_track.wav")
