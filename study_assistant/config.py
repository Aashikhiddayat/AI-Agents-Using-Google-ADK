"""Runtime configuration for NVIDIA NIM through LiteLLM."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
APP_NAME = "study_assistant"

load_dotenv(PROJECT_ROOT / ".env")

MODEL_TIMEOUT_SECONDS = max(10, min(45, int(os.getenv("STUDY_ASSISTANT_MODEL_TIMEOUT_SECONDS", "30"))))
REQUEST_TIMEOUT_SECONDS = max(30, min(180, int(os.getenv("STUDY_ASSISTANT_REQUEST_TIMEOUT_SECONDS", "150"))))
MODEL_CONFIG = types.GenerateContentConfig(
    max_output_tokens=1200,
    http_options=types.HttpOptions(timeout=MODEL_TIMEOUT_SECONDS * 1000),
)


def build_model() -> LiteLlm:
    return LiteLlm(
        model=os.getenv("STUDY_ASSISTANT_MODEL", "openai/nvidia/nemotron-3.5-lightning-30b-a3b"),
        api_base=os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1"),
        api_key=os.getenv("NVIDIA_API_KEY"),
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
