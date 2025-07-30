# FFmpeg Video Processing Service

[![Docker Tags](https://img.shields.io/docker/v/funnyzak/ffmpeg-service?sort=semver&style=flat-square)](https://hub.docker.com/r/funnyzak/ffmpeg-service/)
[![Image Size](https://img.shields.io/docker/image-size/funnyzak/ffmpeg-service)](https://hub.docker.com/r/funnyzak/ffmpeg-service/)
[![Docker Stars](https://img.shields.io/docker/stars/funnyzak/ffmpeg-service.svg?style=flat-square)](https://hub.docker.com/r/funnyzak/ffmpeg-service/)
[![Docker Pulls](https://img.shields.io/docker/pulls/funnyzak/ffmpeg-service.svg?style=flat-square)](https://hub.docker.com/r/funnyzak/ffmpeg-service/)

A lightweight, containerized FFmpeg video processing microservice built with Flask and Python. This service provides HTTP API endpoints for video metadata extraction, screenshot capture, and format conversion.

Build with the `linux/arm64`, `linux/386`, `linux/amd64`, `linux/arm/v6`, `linux/arm/v7`, `linux/arm64/v8` architectures.

## Features

- **Video Information Extraction**: Get detailed metadata including duration, codec, resolution, bitrate, etc.
- **Screenshot Capture**: Extract frames at specific timestamps or evenly spaced intervals
- **Format Conversion**: Convert videos between popular formats (MP4, AVI, MOV, MKV, WebM)
- **Batch Processing**: Combine multiple operations in a single API call
- **URL & File Upload Support**: Process videos from URLs or direct file uploads
- **Automatic Cleanup**: Temporary files are automatically deleted after processing
- **Health Monitoring**: Built-in health check endpoint
- **Error Handling**: Comprehensive error handling with appropriate HTTP status codes

## Pull

```bash
docker pull funnyzak/ffmpeg-service:latest
# GHCR
docker pull ghcr.io/funnyzak/ffmpeg-service:latest
# Aliyun
docker pull registry.cn-beijing.aliyuncs.com/funnyzak/ffmpeg-service:latest
```

## Usage

### Docker Run

```bash
# Run with default settings
docker run -d --name ffmpeg-service --restart on-failure \
  -p 8080:8080 \
  funnyzak/ffmpeg-service

# Run with volume for persistent temp storage (optional)
docker run -d --name ffmpeg-service --restart on-failure \
  -p 8080:8080 \
  -v ./temp:/tmp/videos \
  funnyzak/ffmpeg-service
```

### Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: "3.8"
services:
  ffmpeg-service:
    image: funnyzak/ffmpeg-service:latest
    container_name: ffmpeg-service
    environment:
      - TZ=Asia/Shanghai
    ports:
      - "8080:8080"
    restart: on-failure
    volumes:
      - ./temp:/tmp/videos  # Optional: for persistent temp storage
```

Then run:

```bash
docker-compose up -d
```

### Docker Build

```bash
docker build \
  --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
  --build-arg VERSION="1.0.0" \
  -t funnyzak/ffmpeg-service:1.0.0 .
```

## API Endpoints

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "code": 0,
  "msg": "Service is healthy",
  "data": {}
}
```

### Video Processing (Combined Operations)
```http
POST /process
Content-Type: application/json
```

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4",
  "extract_info": true,
  "take_screenshots": true,
  "screenshot_count": 5,
  "convert_format": "mp4",
  "convert_quality": "medium"
}
```

Or upload a file:
```http
POST /process
Content-Type: multipart/form-data

file: [video file]
extract_info: true
take_screenshots: true
screenshot_timestamps: [10, 30, 60]
```

**Response:**
```json
{
  "code": 0,
  "msg": "Processing completed successfully",
  "data": {
    "info": {
      "duration": 120.5,
      "size": 15728640,
      "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
      "codec_name": "h264",
      "width": 1920,
      "height": 1080,
      "frame_rate": 30.0,
      "bit_rate": 1048576
    },
    "screenshots": [
      {
        "timestamp": 24.1,
        "filename": "screenshot_abc123_24.jpg",
        "file_size": 102400,
        "url": "/download/screenshot_abc123_24.jpg"
      }
    ],
    "conversion": {
      "filename": "converted_def456.mp4",
      "file_size": 12582912,
      "format": "mp4",
      "url": "/download/converted_def456.mp4"
    }
  }
}
```

### Video Information Only
```http
POST /info
Content-Type: application/json
```

**Request Body:**
```json
{
  "video_url": "https://example.com/video.mp4"
}
```

**Response:**
```json
{
  "code": 0,
  "msg": "Video info extracted successfully",
  "data": {
    "duration": 120.5,
    "size": 15728640,
    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    "codec_name": "h264",
    "width": 1920,
    "height": 1080,
    "frame_rate": 30.0,
    "bit_rate": 1048576
  }
}
```

### Download Processed Files
```http
GET /download/{filename}
```

Downloads the processed file (screenshot or converted video).

## Request Parameters

### Processing Options

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `video_url` | string | URL to video file | - |
| `extract_info` | boolean | Extract video metadata | true |
| `take_screenshots` | boolean | Capture screenshots | false |
| `screenshot_timestamps` | array | Specific timestamps for screenshots (seconds) | - |
| `screenshot_count` | integer | Number of evenly spaced screenshots | - |
| `convert_format` | string | Target format (mp4, avi, mov, mkv, webm) | - |
| `convert_quality` | string | Conversion quality (low, medium, high) | medium |

### File Upload

Alternatively, you can upload files directly using `multipart/form-data`:

```bash
curl -X POST http://localhost:8080/process \
  -F "file=@video.mp4" \
  -F "take_screenshots=true" \
  -F "screenshot_count=3"
```

## Error Responses

The service returns standardized error responses:

```json
{
  "code": 400,
  "msg": "Error description",
  "data": {}
}
```

**Common Error Codes:**
- `400`: Bad Request (invalid parameters, file too large, unsupported format)
- `404`: Not Found (file or endpoint not found)
- `413`: Payload Too Large (file exceeds 500MB limit)
- `500`: Internal Server Error (processing failed)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_FILE_SIZE` | Maximum file size in bytes | 524288000 (500MB) |
| `TEMP_DIR` | Temporary files directory | /tmp/videos |

### Supported Formats

**Input Formats:**
- MP4, AVI, MOV, MKV, FLV, WMV, WebM, M4V

**Output Formats:**
- MP4, AVI, MOV, MKV, WebM

### Quality Settings

- **Low**: CRF 28 (smaller file size, lower quality)
- **Medium**: CRF 23 (balanced)
- **High**: CRF 18 (larger file size, higher quality)

## Examples

### Extract Video Information
```bash
curl -X POST http://localhost:8080/info \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4"}'
```

### Take 5 Screenshots
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
    "take_screenshots": true,
    "screenshot_count": 5
  }'
```

### Convert to MP4
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://sample-videos.com/zip/10/avi/SampleVideo_1280x720_1mb.avi",
    "convert_format": "mp4",
    "convert_quality": "high"
  }'
```

### Combined Processing
```bash
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4",
    "extract_info": true,
    "take_screenshots": true,
    "screenshot_timestamps": [5, 15, 25],
    "convert_format": "webm",
    "convert_quality": "medium"
  }'
```

## Performance & Limitations

- **File Size Limit**: 500MB per file
- **Concurrent Processing**: Limited by container resources
- **Temporary Storage**: Files are automatically cleaned up after processing
- **Timeout**: 30 seconds for URL downloads
- **Memory Usage**: Depends on video size and processing operations

## Security Considerations

- Files are processed in isolated temporary directories
- Automatic cleanup prevents disk space issues
- Input validation for file types and sizes
- No persistent storage of user files
- Resource limits prevent abuse

## Troubleshooting

### Common Issues

1. **File Too Large Error**
   - Reduce file size or increase `MAX_FILE_SIZE` limit

2. **Processing Timeout**
   - Check video file integrity
   - Reduce processing complexity

3. **Download Failed**
   - Verify URL accessibility
   - Check network connectivity

4. **Unsupported Format**
   - Convert to supported format first
   - Check FFmpeg codec support

### Logs

View container logs:
```bash
docker logs ffmpeg-service
```

## Reference

- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)