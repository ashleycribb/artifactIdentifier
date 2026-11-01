"""Privacy-gated structured LLM client for ambiguous artifact classification."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from src.config import LLMConfig


class ClassificationPrediction(BaseModel):
    assigned_class: str
    confidence: float
    rationale: str


class PrivacyGateError(Exception):
    """Raised when an LLM call is attempted without explicit remote authorization."""


class LLMClient:
    """Safely interfaces with LLMs using strict token caps and privacy gates."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

    def classify_snippet(
        self,
        file_name: str,
        text_snippet: str,
        candidate_classes: List[str],
    ) -> Optional[ClassificationPrediction]:
        """Classifies text snippet using LLM if remote calls are authorized."""
        if not self.config.allow_remote:
            # Privacy gate active: reject outbound remote network transmission
            return None

        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            return None

        # Truncate text to max tokens (~4 chars per token)
        char_cap = self.config.max_tokens * 4
        capped_snippet = text_snippet[:char_cap]

        prompt = (
            f"You are a strict research artifact classifier.\n"
            f"File: {file_name}\n"
            f"Allowed classes: {', '.join(candidate_classes)}\n\n"
            f"Document snippet:\n{capped_snippet}\n\n"
            f"Output JSON with keys: 'assigned_class', 'confidence' (0.0 to 1.0), 'rationale'."
        )

        try:
            # Mock or actual API invocation depending on environment
            if self.config.provider == "openai":
                return self._call_openai(prompt, candidate_classes, api_key)
            return None
        except Exception:
            return None

    def _call_openai(
        self, prompt: str, candidate_classes: List[str], api_key: str
    ) -> Optional[ClassificationPrediction]:
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=self.config.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=256,
            )
            content = response.choices[0].message.content
            if content:
                data = json.loads(content)
                assigned = data.get("assigned_class", "NeedsReview")
                if assigned not in candidate_classes:
                    assigned = "NeedsReview"
                return ClassificationPrediction(
                    assigned_class=assigned,
                    confidence=float(data.get("confidence", 0.5)),
                    rationale=str(data.get("rationale", "LLM fallback inference")),
                )
        except Exception:
            pass
        return None
