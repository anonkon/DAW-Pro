from __future__ import annotations

import logging
from pathlib import Path

from .config import settings

logger = logging.getLogger("dawpro.storage")

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def workspace_dir(session_id: str) -> Path:
    path = DATA_ROOT / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_audio(session_id: str, filename: str, data: bytes) -> Path:
    local_path = workspace_dir(session_id) / filename
    local_path.write_bytes(data)
    _maybe_upload_to_s3(session_id, filename, local_path)
    return local_path


def _maybe_upload_to_s3(session_id: str, filename: str, local_path: Path) -> None:
    if not (settings.aws_access_key_id and settings.aws_secret_access_key and settings.s3_bucket_name):
        return

    import boto3

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    key = f"{session_id}/{filename}"
    try:
        client.upload_file(str(local_path), settings.s3_bucket_name, key)
    except Exception:  # noqa: BLE001
        logger.exception("S3 upload failed for %s, continuing with local copy only", key)
