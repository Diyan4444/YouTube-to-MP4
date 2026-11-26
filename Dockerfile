# Lightweight Debian base with Python
FROM python:3.11-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# Install FFmpeg, curl, unzip, and Node.js for yt-dlp JS runtime extraction
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl nodejs ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Verify FFmpeg and Node installations
RUN ffmpeg -version && node -v

WORKDIR /app

# Install Python dependencies and ensure latest yt-dlp
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -U pip setuptools && \
    pip install --no-cache-dir -U yt-dlp && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 3000

# Start server using gunicorn on port 3000
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "8", "--timeout", "300", "--chdir", "backend", "app:app"]
