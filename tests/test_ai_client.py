from unittest.mock import MagicMock, patch, AsyncMock
import os
import pytest
from bot.ai_client import CheckResult, GeminiClient


def test_check_result_schema():
    r = CheckResult(
        is_correct=False,
        used_target_word=True,
        corrected="I leverage my English skills.",
        explanation_uz="'leveraging' noto'g'ri — 'can' dan keyin infinitiv keladi.",
    )
    assert r.is_correct is False
    assert r.used_target_word is True
    assert r.corrected.startswith("I leverage")
    assert "noto'g'ri" in r.explanation_uz


def test_check_result_json_roundtrip():
    r = CheckResult(is_correct=True, used_target_word=True, corrected="x", explanation_uz="")
    data = r.model_dump()
    r2 = CheckResult(**data)
    assert r2 == r


@pytest.mark.asyncio
async def test_check_sentence_calls_gemini_with_right_params():
    fake_result = CheckResult(
        is_correct=True, used_target_word=True,
        corrected="I leverage my time.", explanation_uz="",
    )
    fake_response = MagicMock()
    fake_response.parsed = fake_result
    fake_response.usage_metadata.prompt_token_count = 350
    fake_response.usage_metadata.candidates_token_count = 20

    with patch("bot.ai_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.aio.models.generate_content = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="fake")
        result, cost = await client.check_sentence("leverage", "I leverage my time.")

        assert result.is_correct is True
        assert cost > 0

        call_kwargs = instance.aio.models.generate_content.await_args.kwargs
        assert "leverage" in str(call_kwargs["contents"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gemini_real_call_uzbek_explanation():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")

    client = GeminiClient(api_key=key)
    result, cost = await client.check_sentence("leverage", "I am leveraging the box.")

    assert result.is_correct is False
    assert result.used_target_word is True
    assert len(result.explanation_uz) > 10
    assert cost > 0
