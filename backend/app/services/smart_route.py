"""SmartRoute — Pre-flight capacity validation and provider hardware sync.

Uses OGPU on-chain data + IPFS base_data to discover provider hardware
and validate that capacity exists before charging users.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider as DBProvider

logger = logging.getLogger(__name__)

# OGPU Environment enum values (on-chain bitmask)
ENV_CPU = 1
ENV_NVIDIA = 2
ENV_AMD = 4


class SmartRoute:
    """Async service for provider hardware sync and capacity checks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _fetch_provider_info(self, provider_address: str, source_address: str) -> dict:
        """Synchronous method that makes on-chain + IPFS calls.

        Runs in thread pool to avoid blocking the event loop.
        """
        from ogpu.protocol import Source, Provider
        from ogpu import fetch_ipfs_json

        result = {
            "environment": None,
            "gpu_model": None,
            "vram_gb": None,
            "cpu_model": None,
            "ram_gb": None,
            "base_data_url": None,
        }

        try:
            provider = Provider(provider_address)
            source = Source(source_address)

            # 1. Read environment on-chain
            environment = source.get_preferred_environment_of(provider_address)
            result["environment"] = int(environment)

            # 2. Read base_data URL
            base_data_url = provider.get_base_data()
            result["base_data_url"] = base_data_url if base_data_url else None

            # 3. Parse base_data JSON from IPFS
            if base_data_url:
                try:
                    data = fetch_ipfs_json(base_data_url)

                    gpu = data.get("gpu", {})
                    if gpu:
                        result["gpu_model"] = gpu.get("model")
                        vram_val = gpu.get("totalVRAM", {}).get("value")
                        if vram_val and vram_val != "N/A":
                            result["vram_gb"] = float(vram_val)

                    cpu = data.get("cpu", {})
                    if cpu:
                        result["cpu_model"] = cpu.get("model")

                    ram = data.get("ram", {})
                    if ram:
                        ram_val = ram.get("total", {}).get("value")
                        if ram_val and ram_val != "N/A":
                            result["ram_gb"] = float(ram_val)
                except Exception as e:
                    logger.warning("Failed to fetch base_data for %s: %s", provider_address, e)

        except Exception as e:
            logger.warning("Failed to fetch on-chain data for %s: %s", provider_address, e)

        return result

    async def sync_provider(self, provider_address: str, source_address: str) -> None:
        """Sync hardware info for a single provider from on-chain + IPFS."""
        info = await asyncio.to_thread(
            self._fetch_provider_info, provider_address, source_address
        )

        provider = await self.db.get(DBProvider, provider_address)
        if provider is None:
            provider = DBProvider(address=provider_address)
            self.db.add(provider)

        provider.environment = info["environment"]
        provider.gpu_model = info["gpu_model"]
        provider.vram_gb = info["vram_gb"]
        provider.cpu_model = info["cpu_model"]
        provider.ram_gb = info["ram_gb"]
        provider.base_data_url = info["base_data_url"]
        provider.last_sync = datetime.now(timezone.utc)
        provider.is_active = True  # If we can sync it, it's alive

    async def _get_source_registrants(self, source_address: str) -> list[str]:
        """Get all provider addresses registered to a source (on-chain)."""
        def _fetch():
            from ogpu.protocol import Source
            source = Source(source_address)
            contract = source._contract()
            count = contract.functions.getRegistrantCount().call()
            addresses = []
            for i in range(count):
                try:
                    addr = contract.functions.getRegistrantAt(i).call()
                    addresses.append(str(addr))
                except Exception:
                    pass
            return addresses

        return await asyncio.to_thread(_fetch)

    async def sync_all_providers(self, source_address: str) -> None:
        """Sync all providers registered to our source from on-chain."""
        registrants = await self._get_source_registrants(source_address)
        logger.info("Found %d registrants for source %s", len(registrants), source_address)

        for addr in registrants:
            try:
                await self.sync_provider(addr, source_address)
            except Exception as e:
                logger.warning("Failed to sync provider %s: %s", addr, e)

        await self.db.commit()

    async def check_capacity(self, source_address: str, min_vram_gb: int, adapter: str = "lora") -> bool:
        """Check if there's at least one active GPU provider with enough VRAM.

        Uses cached provider data from the local DB — does NOT sync from on-chain.
        For fresh sync, call sync_all_providers() separately (e.g. via Celery Beat).

        QLoRA is only routed to NVIDIA providers because bitsandbytes does not
        have stable ROCm binaries for all versions. AMD providers are excluded
        when adapter == "qlora".

        Returns True if capacity exists, False otherwise.
        Providers with unknown VRAM (vram_gb IS NULL) are included optimistically.
        """
        # QLoRA requires bitsandbytes which is only reliably available on NVIDIA
        # AMD ROCm support is version-dependent and fragile
        if adapter == "qlora":
            env_mask = ENV_NVIDIA  # 2 — NVIDIA only
        else:
            env_mask = ENV_NVIDIA | ENV_AMD  # 6 — NVIDIA + AMD

        query = select(func.count()).where(
            DBProvider.is_active == True,
            DBProvider.is_blocked == False,
            DBProvider.environment.op("&")(env_mask) != 0,  # bitwise AND check
            (DBProvider.vram_gb >= min_vram_gb) | (DBProvider.vram_gb == None),
        )

        count = await self.db.scalar(query)
        return (count or 0) > 0

    async def check_capacity_with_sync(self, source_address: str, min_vram_gb: int) -> bool:
        """Sync providers from on-chain THEN check capacity.

        SLOW — use only for initial setup or manual refresh.
        For normal confirm_job flow, use check_capacity() which reads cached DB data.
        """
        await self.sync_all_providers(source_address)
        return await self.check_capacity(source_address, min_vram_gb)

    async def mark_provider_inactive(self, provider_address: str) -> None:
        """Mark a provider as inactive (no recent heartbeat)."""
        provider = await self.db.get(DBProvider, provider_address)
        if provider:
            provider.is_active = False
            await self.db.commit()
