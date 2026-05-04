import asyncio
import os
import argparse
from datetime import datetime
from telegram import Bot
from telegram.error import RetryAfter, TelegramError
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///telegram_backup.db')

SEND_DELAY = 1.5  # seconds between messages — safe for channels


def format_header(msg) -> str:
    raw = msg.date
    if not raw:
        timestamp = '?'
    elif isinstance(raw, str):
        timestamp = raw.split('.')[0] + ' UTC'
    else:
        timestamp = raw.strftime('%Y-%m-%d %H:%M:%S UTC')
    parts = []
    if msg.full_name:
        parts.append(msg.full_name)
    if msg.username:
        parts.append(f'@{msg.username}')
    sender = ' '.join(parts) if parts else 'Channel post'
    return f'[{timestamp}] {sender}'


async def send_with_retry(coro):
    while True:
        try:
            return await coro
        except RetryAfter as e:
            print(f"  Rate limited — waiting {e.retry_after + 1}s...")
            await asyncio.sleep(e.retry_after + 1)
        except TelegramError as e:
            print(f"  Telegram error: {e}")
            return None


async def restore(chat_id: str, dry_run: bool) -> None:
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        messages = conn.execute(
            text("SELECT * FROM messages ORDER BY date ASC")
        ).fetchall()
        media_map = {
            row.message_id: row
            for row in conn.execute(text("SELECT * FROM media")).fetchall()
        }

    total = len(messages)
    print(f"Found {total} messages to restore")
    if dry_run:
        print("DRY RUN — nothing will be sent\n")

    async with Bot(token=BOT_TOKEN) as bot:
        for i, msg in enumerate(messages, 1):
            header = format_header(msg)
            body = msg._mapping.get('text') or ''
            caption = body
            media = media_map.get(msg.message_id)

            print(f"[{i}/{total}] {header}", end=' — ')

            if dry_run:
                tag = f'[{media.media_type}]' if media else '[text]'
                print(f"{tag} {body[:60]}")
                continue

            if media and media.file_path and os.path.exists(media.file_path):
                cap = caption[:1024]
                with open(media.file_path, 'rb') as f:
                    mtype = media.media_type
                    if mtype == 'photo':
                        await send_with_retry(bot.send_photo(chat_id, f, caption=cap))
                    elif mtype == 'video':
                        await send_with_retry(bot.send_video(chat_id, f, caption=cap))
                    elif mtype == 'animation':
                        await send_with_retry(bot.send_animation(chat_id, f, caption=cap))
                    elif mtype == 'voice':
                        await send_with_retry(bot.send_voice(chat_id, f, caption=cap))
                    elif mtype == 'audio':
                        await send_with_retry(bot.send_audio(chat_id, f, caption=cap))
                    elif mtype == 'sticker':
                        await send_with_retry(bot.send_sticker(chat_id, f))
                        if body:
                            await asyncio.sleep(SEND_DELAY)
                            await send_with_retry(bot.send_message(chat_id, body[:4096]))
                    else:
                        await send_with_retry(bot.send_document(chat_id, f, caption=cap))
                print(f"[{mtype}] sent")

            elif media:
                note = (f"{caption}\n\n⚠️ [{media.media_type} file not found on disk]" if caption
                        else f"{header}\n\n⚠️ [{media.media_type} file not found on disk]")
                await send_with_retry(bot.send_message(chat_id, note[:4096]))
                print(f"[{media.media_type}] file missing — sent text note")

            else:
                if caption:
                    await send_with_retry(bot.send_message(chat_id, caption[:4096]))
                    print("[text] sent")
                else:
                    print("skipped (empty)")

            await asyncio.sleep(SEND_DELAY)

    print(f"\nDone — restored {total} messages to {chat_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Restore a Telegram backup to a channel or group'
    )
    parser.add_argument(
        '--chat-id', required=True,
        help='Target chat/channel ID (e.g. -1001234567890)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview what would be sent without actually sending'
    )
    args = parser.parse_args()
    asyncio.run(restore(args.chat_id, args.dry_run))


if __name__ == '__main__':
    main()
