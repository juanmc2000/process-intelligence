FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# packages/ is copied from the project root when the build context is .
# docker-compose must set context: . and dockerfile: services/api/Dockerfile
COPY app/ app/
COPY packages/ packages/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
