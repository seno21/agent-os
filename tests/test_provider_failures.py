from __future__ import annotations

from agentos.provider.failures import ProviderFailureKind, classify_provider_error


def test_provider_request_budget_exhausted_is_context_overflow() -> None:
    assert (
        classify_provider_error(
            provider_name="openrouter",
            status_code=None,
            raw_code="provider_request_budget_exhausted",
            message='{"fallback_reason":"provider_request_budget_exhausted"}',
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_gemini_input_token_count_message_is_context_overflow() -> None:
    """Gemini's real context-overflow error should be classified as CONTEXT_OVERFLOW."""
    assert (
        classify_provider_error(
            provider_name="gemini",
            status_code=400,
            message=(
                "the input token count (12345) exceeds the maximum number of tokens allowed (8192)."
            ),
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_anthropic_prompt_too_long_is_context_overflow() -> None:
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=400,
            raw_code="prompt_too_long",
            message="prompt_too_long: prompt is longer than the maximum allowed length",
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_gemini_input_token_count_message_is_context_overflow_different_counts() -> None:
    """Same message with different token counts must still match."""
    assert (
        classify_provider_error(
            provider_name="gemini",
            status_code=400,
            message=(
                "the input token count (512) exceeds the maximum number of tokens allowed (4096)."
            ),
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_anthropic_exceed_context_limit_is_context_overflow() -> None:
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=400,
            raw_code="invalid_request_error",
            message="input length and max_tokens exceed context limit: 200000 > 199999",
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_anthropic_request_too_large_is_context_overflow() -> None:
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=413,
            raw_code="request_too_large",
            message="request_too_large: request body is too large",
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


def test_anthropic_request_size_exceeds_is_context_overflow() -> None:
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=413,
            raw_code="invalid_request_error",
            message="request size exceeds the 131072 byte limit",
        )
        is ProviderFailureKind.CONTEXT_OVERFLOW
    )


# ── INSUFFICIENT_CREDITS regressions ─────────────────────────────────


def test_openai_insufficient_quota_429_is_credits() -> None:
    """OpenAI returns insufficient_quota with HTTP 429.

    Before this fix the 429 status code was caught by the rate-limit check
    first, misclassifying the error as RATE_LIMITED.  RATE_LIMITED is a
    circuit-breaker-tripping kind; INSUFFICIENT_CREDITS is not, so the
    misclassification could park a healthy provider for a billing fault
    that a cooldown can never heal.
    """
    assert (
        classify_provider_error(
            provider_name="openai",
            status_code=429,
            raw_code="insufficient_quota",
            message=(
                "You exceeded your current quota, please check your plan and billing details."
            ),
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


def test_openai_exceeded_quota_message_is_credits() -> None:
    """Quota message without the raw code should still be caught."""
    assert (
        classify_provider_error(
            provider_name="openai",
            status_code=429,
            message="You exceeded your current quota.",
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


def test_anthropic_billing_error_402_is_credits() -> None:
    """Anthropic billing_error with HTTP 402 was previously UNKNOWN."""
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=402,
            raw_code="billing_error",
            message="Your credit balance is too low to access the Anthropic API.",
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


def test_anthropic_credit_balance_too_low_is_credits() -> None:
    """Anthropic credit balance message without status code should match."""
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=None,
            message="Your credit balance is too low to access the Anthropic API.",
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


def test_openrouter_insufficient_quota_is_credits() -> None:
    """Same insufficient_quota pattern routed through OpenRouter."""
    assert (
        classify_provider_error(
            provider_name="openrouter",
            status_code=429,
            raw_code="insufficient_quota",
            message="You exceeded your current quota.",
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


def test_deepseek_insufficient_quota_is_credits() -> None:
    """DeepSeek quota exhaustion should not be classified as RATE_LIMITED."""
    assert (
        classify_provider_error(
            provider_name="deepseek",
            status_code=429,
            raw_code="insufficient_quota",
            message="Insufficient quota to complete the request.",
        )
        is ProviderFailureKind.INSUFFICIENT_CREDITS
    )


# ── MODEL_NOT_FOUND regressions ──────────────────────────────────────


def test_openai_404_model_not_found_is_model_not_found() -> None:
    """OpenAI returns HTTP 404 with raw_code model_not_found or does not exist."""
    assert (
        classify_provider_error(
            provider_name="openai",
            status_code=404,
            raw_code="model_not_found",
            message="The model 'gpt-5-turbo' does not exist or you do not have access to it.",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )


def test_openai_model_does_not_exist_without_status_code_is_model_not_found() -> None:
    """OpenAI does-not-exist error message without status code should match."""
    assert (
        classify_provider_error(
            provider_name="openai",
            status_code=None,
            message="The model 'gpt-4o-custom' does not exist.",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )


def test_anthropic_404_not_found_error_is_model_not_found() -> None:
    """Anthropic not_found_error with HTTP 404 was previously UNKNOWN."""
    assert (
        classify_provider_error(
            provider_name="anthropic",
            status_code=404,
            raw_code="not_found_error",
            message="model: claude-3-5-sonnet-20240620-nonexistent not found",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )


def test_openrouter_404_no_endpoints_is_model_not_found() -> None:
    """OpenRouter 404 when no provider endpoints exist for the requested model."""
    assert (
        classify_provider_error(
            provider_name="openrouter",
            status_code=404,
            message="No endpoints found for model 'meta-llama/llama-3-unknown'",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )


def test_gemini_404_is_model_not_found() -> None:
    """Gemini 404 for non-existent model ID should be classified as MODEL_NOT_FOUND."""
    assert (
        classify_provider_error(
            provider_name="gemini",
            status_code=404,
            message="models/gemini-2.0-flash-fake is not found for API version v1beta",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )


def test_generic_provider_404_is_model_not_found() -> None:
    """Any unlisted provider returning HTTP 404 should fall back gracefully."""
    assert (
        classify_provider_error(
            provider_name="custom_llm",
            status_code=404,
            message="404 Not Found",
        )
        is ProviderFailureKind.MODEL_NOT_FOUND
    )
