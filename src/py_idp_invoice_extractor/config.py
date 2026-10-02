from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    input_dir: str = os.getenv("IDP_INPUT_DIR", "./data/input")
    output_dir: str = os.getenv("IDP_OUTPUT_DIR", "./output")
    model_name: str = os.getenv("IDP_MODEL_NAME", "gpt-4o-mini")
    temperature: float = float(os.getenv("IDP_TEMPERATURE", "0.1"))


settings = Settings()
