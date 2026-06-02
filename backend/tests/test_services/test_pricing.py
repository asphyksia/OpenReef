"""Tests for pricing module."""
from app.services.pricing import PRESET_HOURS, PRESET_PARAMS, PRESET_DISPLAY, TIMEOUT_MULTIPLIER, MAX_REQUEUE


class TestPricingConstants:
    def test_preset_hours(self):
        assert PRESET_HOURS["fast"] == 1
        assert PRESET_HOURS["balanced"] == 2
        assert PRESET_HOURS["quality"] == 4

    def test_preset_params(self):
        assert PRESET_PARAMS["fast"]["num_epochs"] == 1
        assert PRESET_PARAMS["balanced"]["num_epochs"] == 2
        assert PRESET_PARAMS["quality"]["num_epochs"] == 3

    def test_preset_display(self):
        assert PRESET_DISPLAY["fast"]["label"] == "Fast"
        assert PRESET_DISPLAY["balanced"]["label"] == "Balanced"
        assert PRESET_DISPLAY["quality"]["label"] == "Quality"

    def test_timeout_multiplier(self):
        assert TIMEOUT_MULTIPLIER == 2

    def test_max_requeue(self):
        assert MAX_REQUEUE == 2


class TestTimeoutCalculation:
    """Test timeout calculation logic from jobs.py."""

    def _estimate_timeout(self, preset, token_count=0):
        """Replicate the timeout calculation from jobs.py."""
        est_hours = PRESET_HOURS.get(preset, 2)
        base_timeout = int(est_hours * 3600 * TIMEOUT_MULTIPLIER)
        if token_count > 0:
            token_factor = min(token_count / 100_000, 1.0)
            timeout = int(base_timeout * (0.3 + 0.7 * token_factor))
        else:
            timeout = base_timeout
        return timeout

    def test_fast_no_tokens(self):
        timeout = self._estimate_timeout("fast", 0)
        # 1hr * 3600 * 2 = 7200s
        assert timeout == 7200

    def test_balanced_no_tokens(self):
        timeout = self._estimate_timeout("balanced", 0)
        # 2hr * 3600 * 2 = 14400s
        assert timeout == 14400

    def test_quality_no_tokens(self):
        timeout = self._estimate_timeout("quality", 0)
        # 4hr * 3600 * 2 = 28800s
        assert timeout == 28800

    def test_small_dataset_reduces_timeout(self):
        timeout_full = self._estimate_timeout("fast", 0)
        timeout_small = self._estimate_timeout("fast", 10000)
        # Small dataset should have reduced timeout (min 30%)
        assert timeout_small < timeout_full
        assert timeout_small >= int(timeout_full * 0.3)

    def test_large_dataset_full_timeout(self):
        timeout_full = self._estimate_timeout("fast", 0)
        timeout_large = self._estimate_timeout("fast", 100000)
        # 100k tokens = full timeout
        assert timeout_large == timeout_full

    def test_min_timeout_30_percent(self):
        timeout_full = self._estimate_timeout("quality", 0)
        timeout_tiny = self._estimate_timeout("quality", 1)
        min_timeout = int(timeout_full * 0.3)
        assert timeout_tiny >= min_timeout
