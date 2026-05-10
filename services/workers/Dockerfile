FROM python:3.11-slim

WORKDIR /app

COPY services/workers/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/workers/ services/workers/
COPY packages/ packages/

ENV PYTHONPATH=/app

# The command is overridden per worker in docker-compose.yml
# e.g. CMD ["python", "-m", "services.workers.parser"]
