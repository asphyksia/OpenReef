"""Tests for local_training module — YAML config generation."""
import yaml
import pytest

from app.services.local_training import build_axolotl_yaml_config


class TestBuildAxolotlYamlConfig:
    """Test the YAML config builder for correctness and security."""

    def _default_params(self):
        return {
            "batch_size": 4,
            "param_count": 3,
            "num_epochs": 2,
            "learning_rate": 2e-4,
        }

    def test_generates_valid_yaml_for_nvidia(self):
        result = build_axolotl_yaml_config(
            base_model="meta-llama/Llama-3.2-3B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir="/workspace/output",
            optimizer="paged_adamw_8bit",
        )
        config = yaml.safe_load(result)
        assert config["base_model"] == "meta-llama/Llama-3.2-3B"
        assert config["bf16"] is True
        assert config["fp16"] is False
        assert config["flash_attention"] is True
        assert config["sdp_attention"] is False

    def test_generates_valid_yaml_for_amd(self):
        result = build_axolotl_yaml_config(
            base_model="meta-llama/Llama-3.2-3B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="amd_rocm",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        assert config["bf16"] is False
        assert config["fp16"] is True
        assert config["flash_attention"] is False
        assert config["sdp_attention"] is True
        assert config["optimizer"] == "adamw_torch"

    def test_generates_valid_yaml_for_cpu(self):
        result = build_axolotl_yaml_config(
            base_model="Qwen/Qwen2.5-1.5B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="cpu",
            preset_params=self._default_params(),
            adapter_type="qlora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        assert config["bf16"] is False
        assert config["fp16"] is False
        assert config["adapter"] == "qlora"

    def test_gradient_checkpointing_for_large_models(self):
        params = self._default_params()
        params["param_count"] = 8
        result = build_axolotl_yaml_config(
            base_model="meta-llama/Llama-3.1-8B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=params,
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        assert config["gradient_checkpointing"] is True
        assert config["gradient_checkpointing_kwargs"] == {"use_reentrant": True}

    def test_no_gradient_checkpointing_for_small_models(self):
        params = self._default_params()
        params["param_count"] = 3
        result = build_axolotl_yaml_config(
            base_model="Qwen/Qwen2.5-1.5B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=params,
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        assert config["gradient_checkpointing"] is False
        assert "gradient_checkpointing_kwargs" not in config

    def test_rejects_invalid_adapter_type(self):
        with pytest.raises(ValueError, match="Unsupported adapter type"):
            build_axolotl_yaml_config(
                base_model="Qwen/Qwen2.5-1.5B",
                dataset_path="/workspace/dataset.jsonl",
                device_type="nvidia_cuda",
                preset_params=self._default_params(),
                adapter_type="full_finetune",
                output_dir="/workspace/output",
            )

    def test_rejects_invalid_device_type(self):
        with pytest.raises(ValueError, match="Unsupported device type"):
            build_axolotl_yaml_config(
                base_model="Qwen/Qwen2.5-1.5B",
                dataset_path="/workspace/dataset.jsonl",
                device_type="tpu",
                preset_params=self._default_params(),
                adapter_type="lora",
                output_dir="/workspace/output",
            )

    def test_rejects_base_model_with_newlines(self):
        with pytest.raises(ValueError, match="must not contain newlines"):
            build_axolotl_yaml_config(
                base_model="Qwen/model\nmalicious: injected",
                dataset_path="/workspace/dataset.jsonl",
                device_type="nvidia_cuda",
                preset_params=self._default_params(),
                adapter_type="lora",
                output_dir="/workspace/output",
            )


class TestYamlInjectionPrevention:
    """Test that YAML injection attacks are prevented."""

    def _default_params(self):
        return {
            "batch_size": 4,
            "param_count": 3,
            "num_epochs": 2,
            "learning_rate": 2e-4,
        }

    def test_malicious_base_model_is_string_not_injected(self):
        """A base_model with YAML-like characters should be serialized as a string."""
        # No newlines (those are rejected by validation), but YAML-like chars
        malicious = "Qwen/model: bar"
        result = build_axolotl_yaml_config(
            base_model=malicious,
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        # The entire malicious string should be the value of base_model
        assert config["base_model"] == malicious
        assert "bar" not in config

    def test_malicious_dataset_path_is_string_not_injected(self):
        """A dataset_path with YAML-like characters should be serialized as a string."""
        malicious = "/workspace/dataset.jsonl\nmalicious_key: injected_value"
        result = build_axolotl_yaml_config(
            base_model="Qwen/Qwen2.5-1.5B",
            dataset_path=malicious,
            device_type="nvidia_cuda",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        config = yaml.safe_load(result)
        assert config["datasets"][0]["path"] == malicious
        assert "malicious_key" not in config

    def test_malicious_output_dir_is_string_not_injected(self):
        """An output_dir with YAML-like characters should be serialized as a string."""
        malicious = "/workspace/output\ninjected: true"
        result = build_axolotl_yaml_config(
            base_model="Qwen/Qwen2.5-1.5B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir=malicious,
        )
        config = yaml.safe_load(result)
        assert config["output_dir"] == malicious
        assert "injected" not in config

    def test_yaml_output_is_valid_yaml(self):
        """The generated output should always be parseable by yaml.safe_load."""
        result = build_axolotl_yaml_config(
            base_model="meta-llama/Llama-3.2-3B",
            dataset_path="/workspace/dataset.jsonl",
            device_type="nvidia_cuda",
            preset_params=self._default_params(),
            adapter_type="lora",
            output_dir="/workspace/output",
        )
        # Should not raise
        config = yaml.safe_load(result)
        assert isinstance(config, dict)
        assert "base_model" in config
        assert "datasets" in config
