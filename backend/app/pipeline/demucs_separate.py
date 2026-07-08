from __future__ import annotations

from pathlib import Path

_MODEL_NAME = "htdemucs"
_model = None


def _load_model():
    # Imported lazily so the backend can boot (and every other route can
    # serve) even before `pip install demucs` has been run - consistent
    # with storage/personas/ai.chain degrading gracefully without their
    # respective dependencies configured.
    global _model
    if _model is None:
        from demucs.pretrained import get_model

        _model = get_model(_MODEL_NAME)
        _model.eval()
    return _model


def separate_stems(audio_path: Path, out_dir: Path) -> dict[str, Path]:
    import soundfile as sf
    from demucs.apply import apply_model
    from demucs.audio import AudioFile

    model = _load_model()

    wav = AudioFile(str(audio_path)).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    ref = wav.mean(0)
    normalized = (wav - ref.mean()) / ref.std()

    sources = apply_model(model, normalized[None], device="cpu", progress=False)[0]
    sources = sources * ref.std() + ref.mean()

    out_dir.mkdir(parents=True, exist_ok=True)
    stem_paths: dict[str, Path] = {}
    for source, name in zip(sources, model.sources):
        path = out_dir / f"{name}.wav"
        # demucs.audio.save_audio requires torchcodec in newer torchaudio
        # versions - write directly with soundfile (already a dependency)
        # instead of pulling in another version-fragile package.
        sf.write(str(path), source.cpu().numpy().T, model.samplerate)
        stem_paths[name] = path
    return stem_paths
