# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 appuser
COPY src ./src
COPY models ./models
RUN mkdir logs && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "scoring_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
