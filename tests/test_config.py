from unittest.mock import patch
import pytest
from bot.config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "abc")
    monkeypatch.setenv("CHANNEL_ID", "-100111")
    monkeypatch.setenv("DISCUSSION_GROUP_ID", "-100222")
    monkeypatch.setenv("TEACHER_TG_ID", "333")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    cfg = Config.load()

    assert cfg.tg_bot_token == "abc"
    assert cfg.channel_id == -100111
    assert cfg.discussion_group_id == -100222
    assert cfg.teacher_tg_id == 333
    assert cfg.openrouter_api_key == "sk-or-test"
    assert cfg.ai_model == "google/gemini-3.1-flash-lite"
    assert cfg.db_path == "data.db"
    assert cfg.tz == "Asia/Tashkent"


def test_config_respects_custom_model(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "abc")
    monkeypatch.setenv("CHANNEL_ID", "-100111")
    monkeypatch.setenv("DISCUSSION_GROUP_ID", "-100222")
    monkeypatch.setenv("TEACHER_TG_ID", "333")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("AI_MODEL", "anthropic/claude-haiku-4.5")

    cfg = Config.load()
    assert cfg.ai_model == "anthropic/claude-haiku-4.5"


def test_config_fail_fast_if_missing(monkeypatch):
    for var in ("TG_BOT_TOKEN", "CHANNEL_ID", "DISCUSSION_GROUP_ID",
                "TEACHER_TG_ID", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    with patch("bot.config.load_dotenv", lambda *a, **kw: None):
        with pytest.raises(RuntimeError, match="TG_BOT_TOKEN"):
            Config.load()
