"""OGPU adapter factory — returns mock, real, or local based on config."""

from app.services.ogpu_adapter import OGPUAdapter


def get_adapter() -> OGPUAdapter:
    """Return the configured OGPU adapter.

    OGPU_ADAPTER=mock   → MockOGPUAdapter (local dev, simulates lifecycle)
    OGPU_ADAPTER=real   → RealOGPUAdapter (production, uses OGPU SDK)
    OGPU_ADAPTER=local  → LocalOGPUAdapter (local machine, runs Axolotl)
    """
    from app.config import settings

    adapter_type = settings.ogpu_adapter
    if adapter_type == "real":
        from app.services.ogpu_real import RealOGPUAdapter
        return RealOGPUAdapter()
    elif adapter_type == "local":
        from app.services.ogpu_local import LocalOGPUAdapter
        return LocalOGPUAdapter()
    else:
        from app.services.ogpu_mock import MockOGPUAdapter
        return MockOGPUAdapter()
