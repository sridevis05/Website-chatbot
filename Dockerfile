# Use standard python runtime base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HF_HOME=/app/model_cache

WORKDIR /app

# Install system dependencies needed for lxml, pycryptodome, chromium runtime, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install CPU-only PyTorch first to avoid massive CUDA dependencies (saves build time/space)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download SentenceTransformer model to avoid downloading at startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Install Playwright and chromium browser binary + system dependencies for headless running
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy app code
COPY . .

# Expose backend API port
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]

