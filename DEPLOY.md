# Deployment to dev server

Server: `164.92.199.126` (root user)

## First-time setup

```bash
ssh root@164.92.199.126

apt update && apt install -y python3.11 python3.11-venv python3-pip git

cd /opt
git clone https://github.com/Ibrakhimzhanov/teachereng.git
cd teachereng

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env
# Fill in: TG_BOT_TOKEN, GEMINI_API_KEY, CHANNEL_ID, DISCUSSION_GROUP_ID, TEACHER_TG_ID

cp systemd/teachereng.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now teachereng

journalctl -u teachereng -f
```

## Updates

Never edit code on the server. Workflow:

```bash
# Locally
git push origin main

# On server
ssh root@164.92.199.126 "cd /opt/teachereng && git pull && systemctl restart teachereng"
```

## Check status

```bash
systemctl status teachereng
journalctl -u teachereng -f
sqlite3 /opt/teachereng/data.db 'SELECT COUNT(*) FROM checked_comments'
sqlite3 /opt/teachereng/data.db 'SELECT word, COUNT(*) FROM posts GROUP BY word'
```

## Telegram setup (one-time)

1. Create a bot via [@BotFather](https://t.me/BotFather), save the token.
2. Disable privacy: `/setprivacy` in BotFather → select your bot → `Disable` (so the bot sees all group messages, not just direct replies).
3. Add the bot as **admin** in:
   - The channel (to receive `channel_post` updates).
   - The **discussion group** linked to the channel (to read comments and reply).
4. Get `CHANNEL_ID` and `DISCUSSION_GROUP_ID`: forward one message from each to [@userinfobot](https://t.me/userinfobot), or use `getUpdates` API.
5. Get `TEACHER_TG_ID`: the teacher messages [@userinfobot](https://t.me/userinfobot) and copies the numeric ID.
6. Get `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/app/apikey).

## Acceptance test (run after first deploy)

1. Teacher posts in the channel:
   ```
   Word of the day

   #word_leverage

   Make sentences in comments!
   ```
   Verify: `sqlite3 /opt/teachereng/data.db "SELECT * FROM posts"` — one row with `word='leverage'`.

2. A student writes `I leverage my time.` in the comments. Bot replies `✅ Zo'r! To'g'ri gap tuzibsiz. 👏`.

3. A student writes `I am leveraging the box.` (wrong meaning of "leverage"). Bot replies with a correction + Uzbek explanation.

4. A student writes `I like apples.` (no target word). Bot replies reminding them to use `leverage`.

5. A student writes `Men leverage ishlataman` (Uzbek). Bot does not reply.

6. On Sunday at 20:00 Tashkent time, the teacher receives a weekly report DM from the bot.

## Troubleshooting

| Symptom | Check |
|---|---|
| Bot not reacting to posts | Is the bot an admin in the channel? Is `CHANNEL_ID` correct? |
| Bot not reacting to comments | Is the bot an admin in the **discussion group** (not the channel)? Is privacy disabled in BotFather? |
| `RuntimeError: Missing required env var` | `.env` not loaded — check `EnvironmentFile` path in systemd unit |
| No weekly report on Sunday | Check `journalctl -u teachereng | grep scheduler`, verify `TZ=Asia/Tashkent` |
| AI returns errors | `journalctl -u teachereng | grep Gemini`, verify `GEMINI_API_KEY` is valid |
