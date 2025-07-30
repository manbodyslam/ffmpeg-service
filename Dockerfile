FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        wget \
        curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set default environment variables
ENV TEMP_DIR="/tmp/videos" \
    MAX_FILE_SIZE="524288000" \
    FILE_RETENTION_HOURS="2" \
    CLEANUP_INTERVAL_MINUTES="30" \
    ALLOWED_VIDEO_EXTENSIONS="mp4,avi,mov,mkv,flv,wmv,webm,m4v" \
    SUPPORTED_OUTPUT_FORMATS="mp4,avi,mov,mkv,webm" \
    FLASK_HOST="0.0.0.0" \
    FLASK_PORT="8080" \
    FLASK_DEBUG="false"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /tmp/videos

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${FLASK_PORT}/health || exit 1

CMD ["python", "app.py"]