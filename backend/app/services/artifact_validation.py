"""Artifact validation for completed OGPU jobs.

Before marking a job as completed, validates that the output artifact
in R2/MinIO exists, has a reasonable size, and optionally checks format.
"""

import logging

from app.services import storage_service

logger = logging.getLogger(__name__)

# Minimum size for a valid LoRA adapter artifact (1 KB)
MIN_ARTIFACT_SIZE = 1024


def validate_artifact(output_r2_key: str) -> tuple[bool, str]:
    """Validate a job output artifact in storage.

    Returns:
        (is_valid, reason) — reason is empty if valid, descriptive if invalid.
    """
    meta = storage_service.head_object(output_r2_key)
    if meta is None:
        return False, "output_not_found"

    size = meta["content_length"]
    if size == 0:
        return False, "output_empty"

    if size < MIN_ARTIFACT_SIZE:
        return False, f"output_too_small ({size} bytes < {MIN_ARTIFACT_SIZE})"

    return True, ""
