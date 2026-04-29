FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/

WORKDIR /

# Install system dependencies for OpenCV and other libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt && \
    pip install --no-cache-dir gunicorn uvicorn

# Copy backend code
COPY . /app/backend/

# Copy evaluation and training to root so Python can import them
# (they are uploaded to the HF Space repo alongside the backend files)
RUN if [ -d /app/backend/evaluation ]; then cp -r /app/backend/evaluation /evaluation; fi
RUN if [ -d /app/backend/training ]; then cp -r /app/backend/training /training; fi

# Create necessary directories
RUN mkdir -p /app/backend/tmp /app/backend/outputs

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120", "app.backend.main:app"]
