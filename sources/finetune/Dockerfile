# OpenReef Fine-Tune Worker — NVIDIA CUDA
# Based on official NVIDIA CUDA runtime image.

FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-venv python3-pip git \
    && rm -rf /var/lib/apt/lists/*

RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Axolotl with flash-attention support
RUN pip install --no-cache-dir \
    "axolotl[flash-attn]==0.6.0" \
    transformers accelerate peft bitsandbytes \
    trl datasets tokenizers \
    s3fs fsspec

# Install OGPU service SDK for provider-side handling
RUN pip install --no-cache-dir "ogpu>=0.2.1"

WORKDIR /workspace

COPY worker.py /workspace/worker.py
ENTRYPOINT ["python", "/workspace/worker.py"]
