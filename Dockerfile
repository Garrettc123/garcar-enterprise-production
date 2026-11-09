FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY init_db.py ./init_db.py
COPY src ./src
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "set -e; if [ \"${ENABLE_GOVERNANCE_DB:-false}\" = \"true\" ]; then python init_db.py; unset MIGRATIONS_DATABASE_URL; fi; exec uvicorn src.main:app --host 0.0.0.0 --port 8000"]
