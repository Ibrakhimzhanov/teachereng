# teachereng — Telegram AI-bot для проверки предложений учеников

**Дата:** 2026-04-18
**Статус:** Design approved, готов к /superpower-write-plan

---

## 1. Постановка задачи

Учитель английского ведёт Telegram-канал "Ingliz tili kanal". Публикует образовательные посты с целевым словом (например `leverage`), где объясняет значение на узбекском, даёт примеры, и просит учеников в комментариях составить собственные предложения с этим словом.

Ученики отвечают в discussion-группе канала. Сейчас учитель проверяет комментарии вручную — не успевает.

**Нужен AI-бот**, который:
- Автоматически определяет, на какое слово проверять
- Проверяет каждый комментарий: правильна ли грамматика + правильно ли использовано целевое слово
- Отвечает reply'ем в том же потоке: похвала за правильное, исправление + объяснение для ошибочного
- Объяснения — на узбекском, корректное предложение — на английском

---

## 2. Принятые решения (brainstorming Q&A)

| # | Решение | Вариант |
|---|---|---|
| 1 | Триггер для определения целевого слова | Хэштег `#word_<слово>` в посте учителя (например `#word_leverage`) |
| 2 | Язык объяснений | Узбекский (объяснение) + английский (корректное предложение) |
| 3 | Когда отвечать | На каждый коммент. Правильный → короткий ✅. С ошибкой → полное объяснение. |
| 4 | Что проверять | Грамматика + использование целевого слова в правильном значении |
| 5.1 | Коммент не на английском | Игнор (бот молчит) |
| 5.2 | Спам (20+ комментов одного юзера) | Отвечаем на все без rate-limit |
| 5.3 | Токсичные комменты | Игнор (не забота бота) |
| 6 | Модерация ответов бота | Full auto + еженедельная сводка учителю в ЛС |
| 7 | AI-модель | Gemini 3.1 Flash Lite ($0.25/$1.50 per 1M) |
| 8 | Архитектура | Polling (один процесс aiogram), не webhook |
| 9 | Масштаб | До 100 комментов на пост |
| 10 | Хостинг | dev-сервер `164.92.199.126`, systemd, деплой через `git pull` |

**Оценка стоимости AI:** ~$0.0003 на коммент → 100 комментов = $0.03. При 30 постах/мес ≈ $1/мес.

---

## 3. Архитектура

Один Python-процесс на dev-сервере. aiogram polling'ом читает обновления из Telegram, при коммьменте зовёт Gemini, публикует reply, пишет в SQLite. APScheduler раз в неделю отправляет сводку учителю.

```
Telegram Channel (посты)  ──┐
Telegram Group (комменты) ──┴──► teachereng-bot (Python)
                                 ├── aiogram 3 (polling)
                                 ├── Gemini API (3.1 Flash Lite)
                                 ├── SQLite (data.db)
                                 └── APScheduler (weekly)
```

**Важно:** бот должен быть добавлен админом в discussion-группу канала (без этого не читает комменты и не может отвечать).

---

## 4. Структура проекта

```
teachereng/
├── bot/
│   ├── __init__.py
│   ├── main.py              # entrypoint, запуск polling
│   ├── config.py            # .env, настройки
│   ├── handlers.py          # aiogram router
│   ├── post_parser.py       # парсинг #word_X
│   ├── comment_checker.py   # orchestration
│   ├── ai_client.py         # Gemini wrapper
│   ├── reply_sender.py      # шаблоны ответов
│   ├── reporter.py          # еженедельная сводка
│   └── storage.py           # SQLite
├── tests/
├── systemd/
│   └── teachereng.service
├── .env.example
├── requirements.txt
└── README.md
```

---

## 5. Компоненты

### 5.1 `post_parser.py`
- Вход: текст channel_post
- Regex (case-insensitive): `r"#word_([a-zA-Z]+)"`
- Первое совпадение → сохранить `(post_id, channel_id, word, posted_at)` в `posts`
- Нет совпадений → игнор (fail-safe)

### 5.2 `comment_checker.py` — оркестратор
1. Пришёл коммент из discussion group
2. Через `reply_to_message.forward_from_message_id` находим `channel_post_id`
3. SELECT из `posts` по `post_id` → если нет слова, выход
4. Эвристика языка (доля латиницы > 70%) → если не англ, выход (case 5.1-A)
5. `INSERT OR IGNORE` в `checked_comments` (дедупликация по `comment_id`)
6. `ai_client.check_sentence(word, text)` → `CheckResult`
7. `reply_sender.send(...)` → получаем `bot_reply_message_id`
8. UPDATE `checked_comments` — заполняем результаты

### 5.3 `ai_client.py`
**System prompt (узбекский):**
```
Siz ingliz tilini o'rgatuvchi AI yordamchisiz. Sizning vazifangiz —
talabaning ingliz tilidagi gapini tekshirish va jo'natuvchiga mehribon,
rag'batlantiruvchi fikr bildirish.

TEKSHIRUV MEZONLARI:
1. Grammatika (zamonlar, artikl, gap tuzilishi)
2. Maqsadli so'z ("{word}") ishlatilganmi va TO'G'RI ma'noda ishlatilganmi

JAVOB FORMATI — faqat JSON:
{
  "is_correct": boolean,
  "used_target_word": boolean,
  "corrected": "to'g'rilangan ingliz gap (is_correct=true bo'lsa, originalni qaytaring)",
  "explanation_uz": "xato bo'lsa — O'ZBEK tilida qisqa tushuntirish (2-3 jumla). Xato yo'q bo'lsa — bo'sh string."
}

QOIDALAR:
- Mehribon ohang. Hech qachon "siz xato qildingiz" demang.
- Agar maqsadli so'z yo'q bo'lsa → is_correct=false, eslatib qo'ying.
- Grammatik to'g'ri, ammo so'z noto'g'ri ma'noda → is_correct=false, ma'noni ko'rsating.
```

**User message:**
```
Maqsadli so'z: {word}
Talaba gapi: {sentence}
```

**Параметры:** `temperature=0.2`, `max_output_tokens=400`, `thinking_budget=0`, structured output через `response_schema` (Pydantic `CheckResult`).

**Retry:** 3 попытки с exponential backoff (2s, 4s, 8s). После — пропускаем коммент молча, логируем WARNING.

### 5.4 `reply_sender.py`
Два шаблона:
```
CORRECT:
✅ Zo'r! To'g'ri gap tuzibsiz. 👏

WITH_ERROR:
📝 Yaxshi urinish!

✅ To'g'ri varianti: "{corrected}"

💡 Tushuntirish: {explanation_uz}
```
Отправка через `bot.send_message(chat_id=discussion_group_id, reply_to_message_id=comment_id, text=...)`.

### 5.5 `reporter.py`
APScheduler cron job: каждое воскресенье 20:00 Tashkent time.
- Читает `checked_comments` за последние 7 дней
- Агрегация: total, correct/incorrect %, топ-3 слов, топ-3 типов ошибок (простая эвристика по `explanation_uz`)
- Шлёт в `TEACHER_TG_ID` (из `.env`)

### 5.6 `handlers.py`
- `@router.channel_post()` → `post_parser.parse_and_store(msg)`
- `@router.message(F.chat.type == "supergroup")` → `comment_checker.check(msg)`
- `@router.message(Command("stats"), F.from_user.id == TEACHER_ID)` → ad-hoc отчёт

---

## 6. Схема БД (SQLite, WAL mode)

```sql
CREATE TABLE posts (
    post_id       INTEGER PRIMARY KEY,
    channel_id    INTEGER NOT NULL,
    word          TEXT NOT NULL,
    posted_at     INTEGER NOT NULL
);
CREATE INDEX idx_posts_word ON posts(word);

CREATE TABLE checked_comments (
    comment_id            INTEGER PRIMARY KEY,
    discussion_group_id   INTEGER NOT NULL,
    post_id               INTEGER NOT NULL,
    user_id               INTEGER NOT NULL,
    username              TEXT,
    user_sentence         TEXT NOT NULL,
    is_correct            INTEGER NOT NULL,
    used_target_word      INTEGER NOT NULL,
    corrected             TEXT,
    explanation_uz        TEXT,
    bot_reply_id          INTEGER,
    checked_at            INTEGER NOT NULL,
    ai_cost_usd           REAL
);
CREATE INDEX idx_checked_post ON checked_comments(post_id);
CREATE INDEX idx_checked_at ON checked_comments(checked_at);
CREATE INDEX idx_checked_user ON checked_comments(user_id);

CREATE TABLE flagged_replies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id      INTEGER NOT NULL,
    reported_by     INTEGER NOT NULL,
    reported_at     INTEGER NOT NULL,
    reviewed        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE kv_store (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
```

---

## 7. Обработка ошибок

| Сценарий | Поведение |
|---|---|
| Gemini timeout/down | 3 retry, затем skip + WARNING log |
| Невалидный JSON от AI | Невозможно при structured output; если всё же — skip |
| Telegram 429 rate limit | aiogram backoff + self-limit 20 msg/sec |
| Бот не админ discussion group | При старте `getChatMember(bot_id)` → если не админ, лог ERROR + ЛС учителю |
| Пост без `#word_X` | Игнор (норма) |
| Коммент без reply_chain к каналу | Игнор |
| SQLite locked | WAL mode решает |
| Нет `.env` / ключей | Fail-fast при старте |
| Бот упал | systemd Restart=always |
| Дубль update | `INSERT OR IGNORE` на comment_id |

Логирование: stdout → systemd journal, `journalctl -u teachereng -f`.

---

## 8. Тестирование

**Unit (pytest):**
- `test_post_parser.py` — regex корректно парсит/не парсит
- `test_comment_checker.py` — оркестрация с mock'нутым AI
- `test_reply_sender.py` — правильные шаблоны
- `test_reporter.py` — агрегация на тестовой БД

**Integration (опционально, `@pytest.mark.integration`):**
- `test_ai_client.py` — 1 реальный вызов Gemini

**Acceptance (ручной, при первом деплое):**
1. Пост с `#word_leverage` → запись в `posts`
2. Правильный коммент → reply `✅ Zo'r!`
3. Коммент с ошибкой → reply с корректом + узбекским объяснением
4. Коммент без целевого слова → reply с напоминанием
5. Коммент на русском → молчание
6. Воскресенье 20:00 → сводка учителю

---

## 9. Деплой

**Первичная установка:**
```bash
ssh root@164.92.199.126
cd /opt && git clone https://github.com/Ibrakhimzhanov/teachereng.git
cd teachereng
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
cp systemd/teachereng.service /etc/systemd/system/
systemctl enable --now teachereng
journalctl -u teachereng -f
```

**Переменные в `.env`:**
- `TG_BOT_TOKEN` — токен бота от @BotFather
- `GEMINI_API_KEY` — от Google AI Studio
- `CHANNEL_ID` — ID канала учителя
- `DISCUSSION_GROUP_ID` — ID discussion-группы канала
- `TEACHER_TG_ID` — user_id учителя для ЛС-отчётов
- `TZ=Asia/Tashkent`

**Обновления:**
```bash
# локально
git push origin main
# на сервере
cd /opt/teachereng && git pull && systemctl restart teachereng
```

---

## 10. Out of scope (намеренно не делаем сейчас)

- Webhook (оставляем polling до роста нагрузки)
- Queue/worker архитектура (не нужно при 100 комментов/пост)
- Multi-channel support (один учитель — один канал; потом можно расширить)
- Rate-limiting пользователей (решение было: отвечаем на все)
- Распознавание токсичности (явно out of scope по решению 5.3)
- `🚩 Report` кнопка под reply (таблица `flagged_replies` заготовлена, фича на v2)
- Перевод reply на английский по запросу продвинутого ученика (v2)
- Дашборд/веб-админка (journalctl + sqlite CLI хватит)

---

## Следующий шаг

`/superpower-write-plan` для создания пошагового плана имплементации по этому дизайну.
