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
async def test_check_sentence_calls_openrouter_with_right_params():
    fake_choice = MagicMock()
    fake_choice.message.content = (
        '{"is_correct": true, "used_target_word": true, '
        '"corrected": "I leverage my time.", "explanation_uz": ""}'
    )
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.usage.prompt_tokens = 350
    fake_response.usage.completion_tokens = 20

    with patch("bot.ai_client.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="sk-or-fake")
        result, cost = await client.check_sentence("leverage", "I leverage my time.")

        assert result.is_correct is True
        assert result.used_target_word is True
        assert cost > 0

        call_kwargs = instance.chat.completions.create.await_args.kwargs
        assert call_kwargs["model"] == "google/gemini-3.1-flash-lite"
        # user message contains the target word and the sentence
        user_msg = call_kwargs["messages"][1]["content"]
        assert "leverage" in user_msg
        assert "I leverage my time." in user_msg
        # json_schema structured output requested
        assert call_kwargs["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_custom_model_passed_through():
    fake_choice = MagicMock()
    fake_choice.message.content = (
        '{"is_correct": true, "used_target_word": true, "corrected": "x", "explanation_uz": ""}'
    )
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    fake_response.usage.prompt_tokens = 10
    fake_response.usage.completion_tokens = 5

    with patch("bot.ai_client.AsyncOpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create = AsyncMock(return_value=fake_response)

        client = GeminiClient(api_key="sk-or-fake", model="anthropic/claude-haiku-4.5")
        await client.check_sentence("word", "Sentence.")

        assert instance.chat.completions.create.await_args.kwargs["model"] == "anthropic/claude-haiku-4.5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openrouter_real_call_uzbek_explanation():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")

    client = GeminiClient(api_key=key)
    result, cost = await client.check_sentence("leverage", "I am leveraging the box.")

    assert result.is_correct is False
    assert result.used_target_word is True
    assert len(result.explanation_uz) > 10
    assert cost > 0
