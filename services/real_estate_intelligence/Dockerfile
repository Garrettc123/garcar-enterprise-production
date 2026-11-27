FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY garcar_reos ./garcar_reos
RUN pip install --no-cache-dir . && useradd -m -u 10001 appuser && mkdir -p /app/data && chown appuser /app/data
USER appuser
EXPOSE 8091
CMD ["uvicorn", "garcar_reos.api:app", "--host", "127.0.0.1", "--port", "8091"]
