import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    tg_bot_token: str
    channel_id: int
    discussion_group_id: int
    teacher_tg_id: int
    gemini_api_key: str
    db_path: str
    tz: str
    log_level: str

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()

        def req(name: str) -> str:
            val = os.environ.get(name)
            if not val:
                raise RuntimeError(f"Missing required env var: {name}")
            return val

        return cls(
            tg_bot_token=req("TG_BOT_TOKEN"),
            channel_id=int(req("CHANNEL_ID")),
            discussion_group_id=int(req("DISCUSSION_GROUP_ID")),
            teacher_tg_id=int(req("TEACHER_TG_ID")),
            gemini_api_key=req("GEMINI_API_KEY"),
            db_path=os.environ.get("DB_PATH") or "data.db",
            tz=os.environ.get("TZ") or "Asia/Tashkent",
            log_level=os.environ.get("LOG_LEVEL") or "INFO",
        )
