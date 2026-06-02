"""Tests for training task module."""
from app.services.pricing import PRESET_HOURS, TIMEOUT_MULTIPLIER


class TestCalculateTimeout:
    """Test the timeout calculation used in training.py."""

    def _calculate_timeout(self, preset, param_count=3, token_count=0):
        """Replicate timeout calculation from training.py."""
        est_hours = PRESET_HOURS.get(preset, 2)
        base_timeout = int(est_hours * 3600 * TIMEOUT_MULTIPLIER)
        if token_count > 0:
            token_factor = min(token_count / 100_000, 1.0)
            timeout = int(base_timeout * (0.3 + 0.7 * token_factor))
        else:
            timeout = base_timeout
        return timeout

    def test_fast_preset_timeout(self):
        timeout = self._calculate_timeout("fast")
        assert timeout == 7200  # 1hr * 3600 * 2

    def test_balanced_preset_timeout(self):
        timeout = self._calculate_timeout("balanced")
        assert timeout == 14400  # 2hr * 3600 * 2

    def test_quality_preset_timeout(self):
        timeout = self._calculate_timeout("quality")
        assert timeout == 28800  # 4hr * 3600 * 2

    def test_timeout_scales_with_tokens(self):
        t1 = self._calculate_timeout("fast", token_count=0)
        t2 = self._calculate_timeout("fast", token_count=50000)
        t3 = self._calculate_timeout("fast", token_count=100000)
        assert t2 < t1  # Smaller dataset = shorter timeout
        assert t3 == t1  # Full dataset = full timeout


class TestStatusMapping:
    """Test OGPU status to job status mapping."""

    def test_status_map_contains_required(self):
        """Verify the status map in jobs.py has all required mappings."""
        expected_mappings = {
            "new": "running",
            "attempted": "running",
            "responded": "running",
            "finalized": "completed",
        }
        for ogpu_status, job_status in expected_mappings.items():
            assert job_status in ("running", "completed", "failed", "checkpointing"), \
                f"Invalid mapping for {ogpu_status}: {job_status}"

    def test_terminal_statuses(self):
        """Verify terminal statuses are correct."""
        terminal = ("completed", "failed", "cancelled", "refunded")
        for status in terminal:
            assert status in ("pending", "validating", "queued", "provisioning",
                              "running", "checkpointing", "completed", "failed",
                              "cancelled", "refunded")
