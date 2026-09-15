FROM python:3.12-slim
WORKDIR /app
COPY runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY runtime /app/runtime
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "runtime.app:app", "--host", "0.0.0.0", "--port", "8000"]
