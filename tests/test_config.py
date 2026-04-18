import pytest
from bot.config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "abc")
    monkeypatch.setenv("CHANNEL_ID", "-100111")
    monkeypatch.setenv("DISCUSSION_GROUP_ID", "-100222")
    monkeypatch.setenv("TEACHER_TG_ID", "333")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("TZ", raising=False)

    cfg = Config.load()

    assert cfg.tg_bot_token == "abc"
    assert cfg.channel_id == -100111
    assert cfg.discussion_group_id == -100222
    assert cfg.teacher_tg_id == 333
    assert cfg.gemini_api_key == "key"
    assert cfg.db_path == "data.db"
    assert cfg.tz == "Asia/Tashkent"


def test_config_fail_fast_if_missing(monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TG_BOT_TOKEN"):
        Config.load()
