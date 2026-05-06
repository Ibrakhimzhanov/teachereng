# Migration Runbook

Перенос рабочего бота `teachereng` с одного Linux-сервера на другой (например, с dev на клиентский DigitalOcean droplet).

## Pre-flight check (на новом сервере)

```bash
# Linux + Python + git
uname -a
python3 --version    # должно быть >= 3.10
which git || apt update && apt install -y git python3-venv python3-pip

# Проверка интернета
curl -sI https://api.telegram.org | head -1   # 200/301
curl -sI https://openrouter.ai | head -1
```

## Шаг 1 — Подготовка нового сервера (всё кроме запуска)

```bash
ssh root@<new-server-ip>

# Каталог + код
mkdir -p /opt && cd /opt
git clone https://github.com/Ibrakhimzhanov/teachereng.git
cd teachereng

# Виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Проверь, что импорт работает:
```bash
python -c "from bot.ai_client import GeminiClient; print('ok')"
```

## Шаг 2 — Создать `.env`

```bash
nano /opt/teachereng/.env
```

Скопировать содержимое — **значения берутся с dev-сервера** (`cat /opt/teachereng/.env` под рукой, или попроси Ислама):

```
TG_BOT_TOKEN=<bot-token-from-BotFather>
CHANNEL_ID=<channel-id>
DISCUSSION_GROUP_ID=<discussion-group-id>
TEACHER_TG_ID=<teacher-user-id>

OPENROUTER_API_KEY=<openrouter-key>
AI_MODEL=google/gemini-3.1-flash-lite-preview

TZ=Asia/Tashkent
DB_PATH=/opt/teachereng/data.db
LOG_LEVEL=INFO
```

Реальные значения — в `.env` на dev-сервере (`164.92.199.126:/opt/teachereng/.env`). Можно скопировать `scp` ом, не вписывая руками:
```bash
scp root@164.92.199.126:/opt/teachereng/.env root@<new-server-ip>:/opt/teachereng/.env
ssh root@<new-server-ip> "chmod 600 /opt/teachereng/.env"
```

Защитить файл:
```bash
chmod 600 /opt/teachereng/.env
```

## Шаг 3 — (Опция) перенести `data.db`

Если хочешь сохранить историю проверок и недельную статистику — на **локальной машине**:

```bash
scp root@164.92.199.126:/opt/teachereng/data.db ./data.db
scp ./data.db root@<new-server-ip>:/opt/teachereng/data.db
ssh root@<new-server-ip> "chown root:root /opt/teachereng/data.db && chmod 644 /opt/teachereng/data.db"
```

Если не хочешь — пропусти этот шаг, бот сам создаст пустую базу при старте.

## Шаг 4 — systemd

```bash
ssh root@<new-server-ip>

cp /opt/teachereng/systemd/teachereng.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable teachereng     # автозапуск при ребуте, ещё НЕ запускаем
```

## Шаг 5 — Переключение трафика (cutover)

В терминале **dev-сервера**:
```bash
ssh root@164.92.199.126
systemctl stop teachereng
```

Сразу же в терминале **нового сервера**:
```bash
ssh root@<new-server-ip>
systemctl start teachereng
sleep 5
systemctl is-active teachereng
journalctl -u teachereng -f --since '30 seconds ago'
```

Должно быть видно:
```
[INFO] aiogram.dispatcher: Run polling for bot @ustozationai_bot
```

Если бот пишет `409 Conflict` — старый ещё запущен, остановить его и подождать 30-60 секунд.

## Шаг 6 — Проверка боевого трафика

1. В Telegram-канале клиент пишет тестовый пост: `#test\n\nUshbu so'zga gap tuzing`.
2. В чате коммент: `I will test the bot.`.
3. На сервере: `journalctl -u teachereng -f` — должны увидеть `RAW_UPDATE` → `CHANNEL_POST` → `Saved word 'test'` → `GROUP_MSG` → `OpenRouter HTTP 200`.
4. Бот в Telegram должен ответить reply'ем на коммент.

## Шаг 7 — Финализация на dev-сервере

После того как клиентский сервер проработал 24 часа без сбоев:
```bash
ssh root@164.92.199.126
systemctl disable teachereng       # отключить автостарт
# stop уже сделан на шаге 5
# код можно оставить — пригодится для следующих обновлений или резервной копии
```

## Обновления в будущем

Все изменения через git:
```bash
# Локально
git push origin main

# На клиентском сервере
ssh root@<new-server-ip> "cd /opt/teachereng && git pull && systemctl restart teachereng"
```

## Если что-то пошло не так

| Симптом | Решение |
|---|---|
| `Conflict: terminated by other getUpdates request` | Старый бот ещё работает → `systemctl stop teachereng` на dev |
| `RuntimeError: Missing required env var` | `.env` не загрузился → проверь путь в `EnvironmentFile` в systemd |
| Бот не отвечает на комменты | `getMe`-проверка: `curl https://api.telegram.org/bot<TOKEN>/getMe` → `can_read_all_group_messages: true`. Если `false` — в @BotFather: `/setprivacy` → Disable |
| `journalctl: No entries` | Сервис не запущен. `systemctl status teachereng` |
| `pip install` падает на pydantic-core | Питон <3.10 — обнови до 3.11+ |

## Связанные файлы

- [DEPLOY.md](DEPLOY.md) — изначальный гайд деплоя
- [docs/plans/2026-04-18-teachereng-bot-design.md](docs/plans/2026-04-18-teachereng-bot-design.md) — архитектура
- [docs/TEACHER_GUIDE.md](docs/TEACHER_GUIDE.md) — руководство для учителя
