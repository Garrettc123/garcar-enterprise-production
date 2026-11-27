FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY garcar_reos ./garcar_reos
RUN python -m pip install . && useradd -m -u 10001 appuser && mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8091
# 0.0.0.0 is only suitable behind HTTPS/private gateway with independent ingress protection.
CMD ["sh", "-c", "exec uvicorn garcar_reos.api:app --host 0.0.0.0 --port ${PORT:-8091}"]
