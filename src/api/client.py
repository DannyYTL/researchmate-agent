"""
Unified LLM client with DeepSeek (via OpenRouter) and Claude fallback.

This module provides a single interface for LLM calls with automatic fallback
and structured output support.
"""

import os
import json
from typing import Optional, Union, Any, Dict
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    """
    Unified LLM client with automatic fallback.

    Primary: DeepSeek R1 (free via OpenRouter)
    Fallback: Anthropic Claude Sonnet 4.5

    Features:
    - Automatic retry with fallback
    - Structured output support (JSON mode)
    - Token usage tracking
    - Error handling
    """

    def __init__(
        self,
        primary_model: str = "deepseek/deepseek-r1",
        fallback_model: str = "anthropic/claude-sonnet-4-5",
        max_tokens: int = 2000,
    ):
        """
        Initialize LLM client with primary and fallback models.

        Args:
            primary_model: Primary model to use (OpenRouter format)
            fallback_model: Fallback model if primary fails
            max_tokens: Maximum tokens to generate
        """
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens

        # Track usage statistics
        self.stats = {
            "primary_calls": 0,
            "fallback_calls": 0,
            "total_tokens": 0,
            "errors": 0,
        }

        # Initialize OpenRouter client (uses OpenAI SDK)
        self.openrouter = None
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            try:
                from openai import OpenAI

                self.openrouter = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_key,
                )
                logger.info("✓ OpenRouter client initialized (DeepSeek R1)")
            except ImportError:
                logger.warning("openai package not installed. Install with: pip install openai")
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter client: {e}")
        else:
            logger.warning("OPENROUTER_API_KEY not found in environment")

        # Initialize Anthropic client (fallback)
        self.anthropic = None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                from anthropic import Anthropic

                self.anthropic = Anthropic(api_key=anthropic_key)
                logger.info("✓ Anthropic client initialized (Claude Sonnet 4.5)")
            except ImportError:
                logger.warning("anthropic package not installed. Install with: pip install anthropic")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
        else:
            logger.warning("ANTHROPIC_API_KEY not found in environment")

        # Validate at least one client is available
        if not self.openrouter and not self.anthropic:
            raise RuntimeError(
                "No LLM client available. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY"
            )

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate text completion with automatic fallback.

        Args:
            prompt: User prompt
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt

        Returns:
            Generated text

        Raises:
            RuntimeError: If both primary and fallback fail
        """
        # Try primary model (DeepSeek via OpenRouter)
        if self.openrouter:
            try:
                logger.debug(f"Calling primary model: {self.primary_model}")

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = self.openrouter.chat.completions.create(
                    model=self.primary_model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=temperature,
                )

                content = response.choices[0].message.content
                self.stats["primary_calls"] += 1

                # Track tokens if available
                if hasattr(response, "usage") and response.usage:
                    tokens = response.usage.total_tokens
                    self.stats["total_tokens"] += tokens
                    logger.debug(f"✓ Primary model response ({tokens} tokens)")

                return content

            except Exception as e:
                logger.warning(f"Primary model failed: {e}")
                self.stats["errors"] += 1

        # Fallback to Claude
        if self.anthropic:
            try:
                logger.info("→ Falling back to Claude Sonnet 4.5")

                # Anthropic uses different API format
                messages = [{"role": "user", "content": prompt}]

                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=self.max_tokens,
                    temperature=temperature,
                    system=system_prompt if system_prompt else "",
                    messages=messages,
                )

                content = response.content[0].text
                self.stats["fallback_calls"] += 1

                # Track tokens
                if hasattr(response, "usage") and response.usage:
                    tokens = response.usage.input_tokens + response.usage.output_tokens
                    self.stats["total_tokens"] += tokens
                    logger.debug(f"✓ Fallback model response ({tokens} tokens)")

                return content

            except Exception as e:
                logger.error(f"Fallback model failed: {e}")
                self.stats["errors"] += 1
                raise RuntimeError(f"Both primary and fallback models failed. Last error: {e}")

        raise RuntimeError("No LLM client available")

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[BaseModel],
        temperature: float = 0.3,
        max_retries: int = 3,
    ) -> BaseModel:
        """
        Generate structured output matching a Pydantic schema.

        Uses JSON mode to ensure parseable output.

        Args:
            prompt: User prompt
            output_schema: Pydantic model class defining expected structure
            temperature: Lower temperature for more deterministic output
            max_retries: Number of parsing retries

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If output doesn't match schema after retries
        """
        # Get JSON schema from Pydantic model
        schema_dict = output_schema.model_json_schema()
        schema_str = json.dumps(schema_dict, indent=2)

        # Enhanced prompt with schema
        enhanced_prompt = f"""{prompt}

IMPORTANT: Respond with ONLY valid JSON matching this exact schema:

{schema_str}

Requirements:
- Return pure JSON with no markdown code blocks
- All required fields must be present
- Types must match exactly
- No additional fields beyond the schema
"""

        system_prompt = "You are a precise assistant that generates structured JSON output."

        # Retry loop for parsing
        for attempt in range(max_retries):
            try:
                logger.debug(f"Structured generation attempt {attempt + 1}/{max_retries}")

                # Generate response
                response_text = self.generate(
                    prompt=enhanced_prompt,
                    temperature=temperature,
                    system_prompt=system_prompt,
                )

                # Clean response (remove markdown code blocks if present)
                cleaned = response_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                # Parse and validate
                parsed = output_schema.model_validate_json(cleaned)
                logger.debug("✓ Successfully parsed structured output")
                return parsed

            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Parse attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All parsing attempts exhausted. Response: {response_text[:200]}")
                    raise ValidationError(f"Failed to parse after {max_retries} attempts: {e}")

        # Should never reach here
        raise RuntimeError("Unexpected error in structured generation")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.

        Returns:
            Dictionary with call counts and token usage
        """
        return {
            **self.stats,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "total_calls": self.stats["primary_calls"] + self.stats["fallback_calls"],
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.stats = {
            "primary_calls": 0,
            "fallback_calls": 0,
            "total_tokens": 0,
            "errors": 0,
        }
        logger.info("Statistics reset")


# Global singleton instance
llm_client = LLMClient()
