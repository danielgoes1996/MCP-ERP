"""
LLM Configuration for ContaFlow
Hybrid approach: Use faster/cheaper models when possible, upgrade for complex cases
"""

import os
from enum import Enum
from typing import Optional

class ModelTier(Enum):
    """Available Claude models by tier"""
    HAIKU = "claude-3-haiku-20240307"      # Fast & cheap
    SONNET = "claude-3-5-sonnet-20241022"  # Balanced (latest)
    OPUS = "claude-3-opus-20240229"        # Maximum capability

class LLMConfig:
    """
    Smart model selection based on context and complexity
    """

    # Default model (from env or fallback)
    DEFAULT_MODEL = os.getenv('ANTHROPIC_MODEL', ModelTier.HAIKU.value)

    # Complexity thresholds
    SIMPLE_EXTRACTION_THRESHOLD = 5000   # Characters - use Haiku
    COMPLEX_EXTRACTION_THRESHOLD = 15000 # Characters - consider Sonnet

    @classmethod
    def select_model_for_task(
        cls,
        text_length: int,
        retry_count: int = 0,
        has_tables: bool = False,
        bank_name: Optional[str] = None
    ) -> str:
        """
        Intelligently select model based on task complexity

        Args:
            text_length: Length of text to process
            retry_count: Number of failed attempts (escalate on retry)
            has_tables: Whether the document has complex tables
            bank_name: Specific bank (some need better models)

        Returns:
            Model identifier string
        """

        # Escalation on retry
        if retry_count > 1:
            return ModelTier.SONNET.value  # Upgrade after 2 failures
        if retry_count > 2:
            return ModelTier.OPUS.value    # Maximum for persistent failures

        # Complex banks that need better models
        complex_banks = ['santander', 'hsbc', 'scotiabank']
        if bank_name and bank_name.lower() in complex_banks:
            return ModelTier.SONNET.value

        # Complex documents with tables
        if has_tables and text_length > cls.COMPLEX_EXTRACTION_THRESHOLD:
            return ModelTier.SONNET.value

        # Simple documents
        if text_length < cls.SIMPLE_EXTRACTION_THRESHOLD:
            return ModelTier.HAIKU.value

        # Default to configured model
        return cls.DEFAULT_MODEL

    @classmethod
    def get_model_info(cls, model: str) -> dict:
        """Get model characteristics for logging"""
        model_info = {
            ModelTier.HAIKU.value: {
                "name": "Claude 3 Haiku",
                "speed": "fast",
                "cost_per_1k_input": 0.00025,
                "cost_per_1k_output": 0.00125,
                "context_window": 200000,
                "recommended_for": "Simple extractions, structured data"
            },
            ModelTier.SONNET.value: {
                "name": "Claude 3.5 Sonnet",
                "speed": "medium",
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.015,
                "context_window": 200000,
                "recommended_for": "Complex formats, better reasoning"
            },
            ModelTier.OPUS.value: {
                "name": "Claude 3 Opus",
                "speed": "slow",
                "cost_per_1k_input": 0.015,
                "cost_per_1k_output": 0.075,
                "context_window": 200000,
                "recommended_for": "Maximum accuracy, complex cases"
            }
        }
        return model_info.get(model, model_info[ModelTier.HAIKU.value])

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given model and token count"""
        info = cls.get_model_info(model)
        input_cost = (input_tokens / 1000) * info["cost_per_1k_input"]
        output_cost = (output_tokens / 1000) * info["cost_per_1k_output"]
        return round(input_cost + output_cost, 4)