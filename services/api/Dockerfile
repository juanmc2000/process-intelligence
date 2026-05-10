FROM python:3.11-slim

WORKDIR /app

COPY services/api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Build context is project root (set in docker-compose.yml)
COPY services/api/app/ app/
COPY packages/ packages/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
