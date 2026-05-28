"""Shared pricing, timeout, and preset constants.

Source of truth for preset parameters. All files that need preset config
must import from this module to avoid silent drift.

Used by:
- job_service.py (cost estimation)
- training.py (timeout calculation)
- jobs.py (progress/ETA estimation)
- models.py (API display of preset details)
- ogpu_adapter.py (Axolotl training parameters)
"""

# --- Preset definitions (canonical) ---
# Hours per preset (rough estimate for LoRA fine-tuning)
PRESET_HOURS = {
    "fast": 1,
    "balanced": 2,
    "quality": 4,
}

# 2x buffer for slow/hung providers
TIMEOUT_MULTIPLIER = 2

# Axolotl training parameters per preset (canonical — used by OGPU adapter)
PRESET_PARAMS = {
    "fast": {"num_epochs": 1, "learning_rate": 2e-4, "batch_size": 4},
    "balanced": {"num_epochs": 2, "learning_rate": 1e-4, "batch_size": 4},
    "quality": {"num_epochs": 3, "learning_rate": 5e-5, "batch_size": 8},
}

# Display metadata for frontend
PRESET_DISPLAY = {
    "fast": {"label": "Fast", "description": "Quick training, fewer epochs. Good for testing.", "epochs": 1, "learning_rate": 2e-4},
    "balanced": {"label": "Balanced", "description": "Good quality/price ratio.", "epochs": 2, "learning_rate": 1e-4},
    "quality": {"label": "Quality", "description": "More epochs, best results.", "epochs": 3, "learning_rate": 5e-5},
}

# Provider requeue limit (used by training.py and providers.py)
MAX_REQUEUE = 2
