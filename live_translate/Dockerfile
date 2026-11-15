# Muối Từ translation server (used by Railway; works with any Docker host).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    LIVE_TRANSLATE_DB=/data/invites.db

WORKDIR /app
COPY requirements.txt /app/live_translate/requirements.txt
RUN pip install --no-cache-dir -r /app/live_translate/requirements.txt
COPY . /app/live_translate

# PORT is provided by Railway; the server falls back to 8765 elsewhere.
CMD ["python", "-m", "live_translate.server"]
