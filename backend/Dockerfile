# Build context is the repository root (the image also needs database/schema.sql):
#   docker build -f backend/Dockerfile .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend

# prophet==1.1.5 ships a precompiled Stan model, so no compiler is needed.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY database/ /app/database/

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]
