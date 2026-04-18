# teachereng

AI-bot for Telegram English-learning channel. Auto-checks student sentences in comments, replies with praise or correction + Uzbek explanation.

See [docs/plans/2026-04-18-teachereng-bot-design.md](docs/plans/2026-04-18-teachereng-bot-design.md) for design and [docs/plans/2026-04-18-teachereng-bot-implementation.md](docs/plans/2026-04-18-teachereng-bot-implementation.md) for the implementation plan.

## Quick start (local)

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows bash
# or: source .venv/bin/activate # Linux/macOS

pip install -r requirements.txt
cp .env.example .env
# edit .env with real tokens
python -m bot.main
```

## Deploy

See [DEPLOY.md](DEPLOY.md).
