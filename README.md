# Telegram Backup Bot

A Telegram bot that backs up messages and media from channels and groups to a SQLite database and local storage. Runs as a Docker container with persistent volumes and includes a restore script to replay backups back into Telegram.

## Features

- Backs up text messages, captions, photos, videos, documents, voice messages, audio, animations, and stickers
- Stores message metadata (sender, timestamp, reply context) in a SQLite database
- Downloads and stores all media files to disk
- Whitelist-based access control — only backs up chats you authorize
- Restore script replays the full backup back to any channel or group
- Dry run mode to preview a restore before sending anything
- Runs 24/7 in Docker with automatic restart on crash or reboot

## Requirements

- Docker and Docker Compose
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Project Structure

```
Bkt.py              # Bot — listens and backs up incoming messages
restore.py          # Restore script — replays backup to a Telegram chat
Dockerfile          # Container image definition
docker-compose.yml  # Service, volumes, and restart policy
requirements.txt    # Python dependencies
.env.example        # Environment variable template
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Revstamper/Backup-telegram-with-bot-token.git
cd Backup-telegram-with-bot-token
```

### 2. Create your `.env` file

```bash
cp .env.example .env
nano .env
```

Fill in your values:

```
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=sqlite:////data/db/telegram_backup.db
MEDIA_BACKUP_DIR=/data/media
ALLOWED_CHAT_IDS=-123456789,-19541465165
```

See the [Configuration](#configuration) section below for details on each variable.

### 3. Build and start

```bash
docker compose up -d
```

### 4. Check the logs

```bash
docker compose logs -f
```

You should see:

```
Bot started, polling for messages...
```

### 5. Add the bot to your channel

1. Open your channel in Telegram → **Manage Channel** → **Administrators**
2. Add your bot as an administrator
3. It only needs **Read Messages** — all other permissions can be disabled

Post a test message and you should see `Backed up message ...` appear in the logs.

---

## Configuration

All configuration is done via the `.env` file.

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | Yes | — | Your bot token from @BotFather |
| `DATABASE_URL` | No | `sqlite:////data/db/telegram_backup.db` | SQLite database path |
| `MEDIA_BACKUP_DIR` | No | `/data/media` | Directory where media files are stored |
| `ALLOWED_CHAT_IDS` | No | *(empty — accepts all)* | Comma-separated list of chat IDs to back up |

---

## Whitelisting chats

To restrict the bot so it only backs up specific channels or groups, add their IDs to `ALLOWED_CHAT_IDS` in your `.env`:

```
ALLOWED_CHAT_IDS=-123456789,-19541465165
```

The chat ID is logged every time a message is backed up:

```
Backed up message 5 from chat -123456789
```

If `ALLOWED_CHAT_IDS` is left empty, the bot accepts messages from all chats.

After editing `.env`, restart the bot:

```bash
docker compose up -d
```

---

## Restoring a backup

The restore script reads the database and replays all messages — including media — back to a specified Telegram chat.

> **Note:** The bot must be an admin with **Post Messages** permission in the target channel before restoring.

### Dry run (preview without sending)

Always do a dry run first to verify what will be sent:

```bash
docker compose exec bot python restore.py --chat-id -1001234567890 --dry-run
```

Example output:

```
Found 4 messages to restore
DRY RUN — nothing will be sent

[1/4] [2026-05-04 16:25:28 UTC] Channel post — [photo] Testing
[2/4] [2026-05-04 18:39:07 UTC] Channel post — [text] Testing
[3/4] [2026-05-04 18:40:43 UTC] Channel post — [sticker]
[4/4] [2026-05-04 18:40:49 UTC] Channel post — [photo]

Done — restored 4 messages to -123456789
```

### Run the restore

```bash
docker compose exec bot python restore.py --chat-id -123456789
```

The script handles Telegram's rate limits automatically and waits if it gets throttled.

---

## Accessing the backup data

### Quick query via terminal

```bash
docker compose exec bot sqlite3 /data/db/telegram_backup.db
```

```sql
SELECT * FROM messages;
SELECT * FROM media;
.quit
```

### GUI — DB Browser for SQLite

Download the database file from the Docker volume:

```
/var/lib/docker/volumes/backup-telegram-with-bot-token_bot_db/_data/telegram_backup.db
```

Open it with [DB Browser for SQLite](https://sqlitebrowser.org/) for a spreadsheet-like view with filtering and CSV export.

Media files are stored in:

```
/var/lib/docker/volumes/backup-telegram-with-bot-token_bot_media/_data/
```

---

## Cleaning up the backup

Stop the bot before deleting any files to avoid database corruption:

```bash
docker compose stop bot

# Delete the database
rm /var/lib/docker/volumes/backup-telegram-with-bot-token_bot_db/_data/telegram_backup.db

# Delete all media files
rm -rf /var/lib/docker/volumes/backup-telegram-with-bot-token_bot_media/_data/*

# Restart — the bot recreates the database tables automatically
docker compose start bot
```

You can delete either the database or media independently.

---

## Logging

Logs are written to stdout and can be viewed with:

```bash
docker compose logs -f
```

Unauthorized chat access attempts are logged as warnings:

```
WARNING - Ignored message from unauthorized chat -1009999999999
```

---


Forked from https://github.com/AiGptCode/Backup-telegram-with-bot-token
