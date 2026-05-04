FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' botuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

RUN mkdir -p /data/db /data/media && chown -R botuser:botuser /data

USER botuser

ENV DATABASE_URL=sqlite:////data/db/telegram_backup.db
ENV MEDIA_BACKUP_DIR=/data/media

CMD ["python", "Bkt.py"]
