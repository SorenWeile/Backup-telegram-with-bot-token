import os
import logging
import sys
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///telegram_backup.db')
MEDIA_BACKUP_DIR = os.getenv('MEDIA_BACKUP_DIR', 'telegram_media_backup')
ALLOWED_CHAT_IDS = {
    int(cid.strip())
    for cid in os.getenv('ALLOWED_CHAT_IDS', '').split(',')
    if cid.strip()
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in the .env file")

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()


class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    date = Column(DateTime)
    message_id = Column(Integer, unique=True)
    reply_to_message_id = Column(Integer, nullable=True)
    chat_type = Column(String, nullable=True)
    is_group = Column(Boolean, default=False)


class Media(Base):
    __tablename__ = 'media'
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer)
    media_type = Column(String)
    file_name = Column(String)
    file_path = Column(String)


Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

os.makedirs(MEDIA_BACKUP_DIR, exist_ok=True)


async def backup_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if ALLOWED_CHAT_IDS and message.chat_id not in ALLOWED_CHAT_IDS:
        logger.warning("Ignored message from unauthorized chat %s", message.chat_id)
        return

    try:
        from_user = message.from_user
        chat_type = message.chat.type
        text = message.text or message.caption

        with SessionLocal() as db_session:
            db_message = Message(
                chat_id=message.chat_id,
                user_id=from_user.id if from_user else None,
                username=from_user.username if from_user else None,
                full_name=from_user.full_name if from_user else None,
                text=text,
                date=message.date,
                message_id=message.message_id,
                reply_to_message_id=(
                    message.reply_to_message.message_id if message.reply_to_message else None
                ),
                chat_type=chat_type,
                is_group=chat_type in ('group', 'supergroup', 'channel'),
            )
            db_session.add(db_message)

            media_file = None
            media_type = None
            if message.photo:
                media_file = await message.photo[-1].get_file()
                media_type = 'photo'
            elif message.video:
                media_file = await message.video.get_file()
                media_type = 'video'
            elif message.document:
                media_file = await message.document.get_file()
                media_type = 'document'
            elif message.voice:
                media_file = await message.voice.get_file()
                media_type = 'voice'
            elif message.audio:
                media_file = await message.audio.get_file()
                media_type = 'audio'
            elif message.animation:
                media_file = await message.animation.get_file()
                media_type = 'animation'
            elif message.sticker:
                media_file = await message.sticker.get_file()
                media_type = 'sticker'

            if media_file:
                file_name = f'{message.message_id}_{media_file.file_id}'
                file_path = os.path.join(MEDIA_BACKUP_DIR, file_name)
                await media_file.download_to_drive(file_path)
                db_session.add(Media(
                    message_id=message.message_id,
                    media_type=media_type,
                    file_name=file_name,
                    file_path=file_path,
                ))

            db_session.commit()
            logger.info("Backed up message %s from chat %s", message.message_id, message.chat_id)

    except Exception as e:
        logger.error("Error processing message %s: %s", message.message_id, e, exc_info=True)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    content_filter = (
        filters.TEXT
        | filters.PHOTO
        | filters.VIDEO
        | filters.Document.ALL
        | filters.VOICE
        | filters.AUDIO
        | filters.ANIMATION
        | filters.Sticker.ALL
        | filters.CAPTION
    )
    app.add_handler(MessageHandler(content_filter, backup_message))

    logger.info("Bot started, polling for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
