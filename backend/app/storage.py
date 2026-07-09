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
    _maybe_upload_to_r2(session_id, filename, local_path)
    return local_path


def _maybe_upload_to_r2(session_id: str, filename: str, local_path: Path) -> None:
    if not (settings.r2_account_id and settings.r2_access_key_id
            and settings.r2_secret_access_key and settings.r2_bucket_name):
        return

    import boto3

    # R2 speaks the S3 API, so boto3's "s3" client works unchanged - it just
    # needs pointing at R2's account-specific endpoint instead of AWS's.
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    key = f"{session_id}/{filename}"
    try:
        client.upload_file(str(local_path), settings.r2_bucket_name, key)
    except Exception:  # noqa: BLE001
        logger.exception("R2 upload failed for %s, continuing with local copy only", key)
