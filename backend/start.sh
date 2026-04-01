#!/bin/bash
# Production startup script for GARCAR Enterprise Platform
# Auto-initializes database and starts uvicorn

echo "GARCAR Enterprise Platform — Starting..."
echo "Environment: ${ENVIRONMENT:-production}"

# Start the server
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}
