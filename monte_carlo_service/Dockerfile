# Cloud Run sets PORT at runtime (often 8080). Listen on $PORT so traffic reaches the app.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

EXPOSE 8080

# Shell form so ${PORT:-8080} is expanded when the container starts
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
