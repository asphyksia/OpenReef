"""OGPU adapter factory — returns mock or real based on env var."""

import os

from app.services.ogpu_adapter import OGPUAdapter

_ADAPTER = os.environ.get("OGPU_ADAPTER", "mock").lower()


def get_adapter() -> OGPUAdapter:
    """Return the configured OGPU adapter.

    OGPU_ADAPTER=mock  → MockOGPUAdapter (local dev, simulates lifecycle)
    OGPU_ADAPTER=real  → RealOGPUAdapter (production, uses OGPU SDK)
    """
    if _ADAPTER == "real":
        from app.services.ogpu_real import RealOGPUAdapter
        return RealOGPUAdapter()
    else:
        from app.services.ogpu_mock import MockOGPUAdapter
        return MockOGPUAdapter()
