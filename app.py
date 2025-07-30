#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg Video Processing Service
A Flask-based microservice for video processing using FFmpeg
"""

import os
import json
import uuid
import subprocess
import time
import threading
from urllib.parse import urlparse
import requests
from flask import Flask, request, jsonify, send_file
import magic

app = Flask(__name__)

# Configuration from environment variables
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/videos')
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '524288000'))  # Default: 500MB
FILE_RETENTION_HOURS = int(os.getenv('FILE_RETENTION_HOURS', '2'))
CLEANUP_INTERVAL_MINUTES = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))

# Parse allowed extensions from environment
allowed_ext_str = os.getenv('ALLOWED_VIDEO_EXTENSIONS', 'mp4,avi,mov,mkv,flv,wmv,webm,m4v')
ALLOWED_VIDEO_EXTENSIONS = {f'.{ext.strip()}' for ext in allowed_ext_str.split(',')}

# Parse supported output formats from environment  
output_fmt_str = os.getenv('SUPPORTED_OUTPUT_FORMATS', 'mp4,avi,mov,mkv,webm')
SUPPORTED_OUTPUT_FORMATS = {fmt.strip() for fmt in output_fmt_str.split(',')}

class VideoProcessor:
    """Video processing utility class"""
    
    def __init__(self, video_path):
        self.video_path = video_path
        self.video_info = None
    
    def get_video_info(self):
        """Extract video metadata using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', self.video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("No video stream found")
            
            format_info = data.get('format', {})
            
            self.video_info = {
                'duration': float(format_info.get('duration', 0)),
                'size': int(format_info.get('size', 0)),
                'format_name': format_info.get('format_name', ''),
                'codec_name': video_stream.get('codec_name', ''),
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'frame_rate': eval(video_stream.get('r_frame_rate', '0/1')) if '/' in str(video_stream.get('r_frame_rate', '')) else 0,
                'bit_rate': int(format_info.get('bit_rate', 0))
            }
            
            return self.video_info
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFprobe failed: {e.stderr}")
        except json.JSONDecodeError:
            raise Exception("Failed to parse video metadata")
        except Exception as e:
            raise Exception(f"Error getting video info: {str(e)}")
    
    def take_screenshots(self, timestamps=None, count=None):
        """Take screenshots from video"""
        try:
            if not self.video_info:
                self.get_video_info()
            
            duration = self.video_info['duration']
            screenshots = []
            
            if timestamps:
                # Use provided timestamps
                for timestamp in timestamps:
                    if timestamp > duration:
                        continue
                    screenshots.append(self._capture_screenshot(timestamp))
            elif count:
                # Take screenshots at evenly spaced intervals
                if count <= 0:
                    raise ValueError("Screenshot count must be positive")
                
                interval = duration / (count + 1)
                for i in range(1, count + 1):
                    timestamp = i * interval
                    screenshots.append(self._capture_screenshot(timestamp))
            else:
                # Default: take 3 screenshots
                for i in [0.25, 0.5, 0.75]:
                    timestamp = duration * i
                    screenshots.append(self._capture_screenshot(timestamp))
            
            return screenshots
            
        except Exception as e:
            raise Exception(f"Screenshot capture failed: {str(e)}")
    
    def _capture_screenshot(self, timestamp):
        """Capture a single screenshot at specified timestamp"""
        output_filename = f"screenshot_{uuid.uuid4().hex}_{int(timestamp)}.jpg"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        cmd = [
            'ffmpeg', '-i', self.video_path, '-ss', str(timestamp),
            '-vframes', '1', '-q:v', '2', '-y', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Screenshot failed: {result.stderr}")
        
        # Get file size
        file_size = os.path.getsize(output_path)
        
        return {
            'timestamp': timestamp,
            'filename': output_filename,
            'file_path': output_path,
            'file_size': file_size,
            'url': f"/download/{output_filename}"
        }
    
    def convert_format(self, output_format, quality='medium'):
        """Convert video to specified format"""
        try:
            if output_format not in SUPPORTED_OUTPUT_FORMATS:
                raise ValueError(f"Unsupported output format. Supported: {SUPPORTED_OUTPUT_FORMATS}")
            
            output_filename = f"converted_{uuid.uuid4().hex}.{output_format}"
            output_path = os.path.join(TEMP_DIR, output_filename)
            
            # Quality settings
            quality_settings = {
                'low': ['-crf', '28'],
                'medium': ['-crf', '23'],
                'high': ['-crf', '18']
            }
            
            cmd = [
                'ffmpeg', '-i', self.video_path,
                '-c:v', 'libx264', '-c:a', 'aac',
                *quality_settings.get(quality, quality_settings['medium']),
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Conversion failed: {result.stderr}")
            
            # Get output file info
            file_size = os.path.getsize(output_path)
            
            return {
                'filename': output_filename,
                'file_path': output_path,
                'file_size': file_size,
                'format': output_format,
                'url': f"/download/{output_filename}"
            }
            
        except Exception as e:
            raise Exception(f"Format conversion failed: {str(e)}")

def download_video_from_url(url):
    """Download video from URL"""
    try:
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Invalid URL")
        
        # Create temporary file
        temp_filename = f"input_{uuid.uuid4().hex}"
        temp_path = os.path.join(TEMP_DIR, temp_filename)
        
        # Download file
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if not any(video_type in content_type for video_type in ['video', 'application/octet-stream']):
            raise ValueError("URL does not point to a video file")
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE:
            raise ValueError("File too large")
        
        # Save file
        with open(temp_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_FILE_SIZE:
                        os.remove(temp_path)
                        raise ValueError("File too large")
        
        return temp_path
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download video: {str(e)}")
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Download error: {str(e)}")

def save_uploaded_file(file):
    """Save uploaded file"""
    try:
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)     # Seek back to beginning
        
        if file_size > MAX_FILE_SIZE:
            raise ValueError("File too large")
        
        # Check file extension
        filename = file.filename or ''
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in ALLOWED_VIDEO_EXTENSIONS:
            # Try to detect file type using magic
            file_content = file.read(1024)
            file.seek(0)
            mime_type = magic.from_buffer(file_content, mime=True)
            if not mime_type.startswith('video/'):
                raise ValueError("Not a valid video file")
        
        # Save file
        temp_filename = f"upload_{uuid.uuid4().hex}{file_ext}"
        temp_path = os.path.join(TEMP_DIR, temp_filename)
        
        file.save(temp_path)
        return temp_path
        
    except Exception as e:
        raise Exception(f"File upload error: {str(e)}")

def cleanup_temp_files(*file_paths):
    """Clean up temporary files"""
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass  # Ignore cleanup errors


def _parse_bool(value):
    """Parse boolean value from string or boolean"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value) if value is not None else False


def _parse_int(value):
    """Parse integer value from string or int"""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_list(value):
    """Parse list value from string or list"""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            # Try to parse as JSON array
            import json
            return json.loads(value)
        except json.JSONDecodeError:
            # Fall back to comma-separated values
            return [float(x.strip()) for x in value.split(',') if x.strip()]
    return None

def create_response(code=0, msg="", data=None):
    """Create standardized response"""
    return jsonify({
        "code": code,
        "msg": msg,
        "data": data or {}
    })


def cleanup_old_files():
    """Clean up files older than FILE_RETENTION_HOURS"""
    try:
        if not os.path.exists(TEMP_DIR):
            return
        
        current_time = time.time()
        retention_seconds = FILE_RETENTION_HOURS * 3600
        
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            
            # Skip input files (they should be cleaned immediately)
            if filename.startswith('input_') or filename.startswith('upload_'):
                continue
            
            # Check if file is older than retention period
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > retention_seconds:
                    try:
                        os.remove(file_path)
                        print(f"Cleaned up old file: {filename}")
                    except Exception as e:
                        print(f"Failed to clean up {filename}: {e}")
                        
    except Exception as e:
        print(f"Cleanup error: {e}")


def start_cleanup_thread():
    """Start background cleanup thread"""
    def cleanup_worker():
        while True:
            time.sleep(CLEANUP_INTERVAL_MINUTES * 60)
            cleanup_old_files()
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    print(f"Started cleanup thread (interval: {CLEANUP_INTERVAL_MINUTES} minutes, retention: {FILE_RETENTION_HOURS} hours)")

# API Routes

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return create_response(msg="Service is healthy")

@app.route('/process', methods=['POST'])
def process_video():
    """Main video processing endpoint"""
    input_files = []  # Files to clean up immediately (input files)
    output_files = []  # Files to keep for download (output files)
    
    try:
        # Parse request - handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Get processing options with type conversion for form data
        extract_info = _parse_bool(data.get('extract_info', True))
        take_screenshots = _parse_bool(data.get('take_screenshots', False))
        screenshot_timestamps = _parse_list(data.get('screenshot_timestamps'))
        screenshot_count = _parse_int(data.get('screenshot_count'))
        convert_format = data.get('convert_format')
        convert_quality = data.get('convert_quality', 'medium')
        
        # Get video file
        video_path = None
        
        if 'video_url' in data:
            # Download from URL
            video_path = download_video_from_url(data['video_url'])
            input_files.append(video_path)
        elif 'file' in request.files:
            # Upload file
            video_path = save_uploaded_file(request.files['file'])
            input_files.append(video_path)
        else:
            return create_response(code=400, msg="No video URL or file provided"), 400
        
        # Initialize processor
        processor = VideoProcessor(video_path)
        result = {}
        
        # Extract video info
        if extract_info:
            result['info'] = processor.get_video_info()
        
        # Take screenshots
        if take_screenshots:
            screenshots = processor.take_screenshots(
                timestamps=screenshot_timestamps,
                count=screenshot_count
            )
            result['screenshots'] = screenshots
            # Keep screenshot files for download
            output_files.extend([shot['file_path'] for shot in screenshots])
        
        # Convert format
        if convert_format:
            conversion_result = processor.convert_format(convert_format, convert_quality)
            result['conversion'] = conversion_result
            # Keep converted file for download
            output_files.append(conversion_result['file_path'])
        
        # Clean up input files only (keep output files for download)
        cleanup_temp_files(*input_files)
        
        return create_response(msg="Processing completed successfully", data=result)
        
    except ValueError as e:
        # Clean up all files on error
        cleanup_temp_files(*(input_files + output_files))
        return create_response(code=400, msg=str(e)), 400
    except Exception as e:
        # Clean up all files on error
        cleanup_temp_files(*(input_files + output_files))
        return create_response(code=500, msg=f"Processing failed: {str(e)}"), 500

@app.route('/info', methods=['POST'])
def get_video_info():
    """Get video information only"""
    temp_files = []
    
    try:
        # Parse request - handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Get video file
        if 'video_url' in data:
            video_path = download_video_from_url(data['video_url'])
            temp_files.append(video_path)
        elif 'file' in request.files:
            video_path = save_uploaded_file(request.files['file'])
            temp_files.append(video_path)
        else:
            return create_response(code=400, msg="No video URL or file provided"), 400
        
        processor = VideoProcessor(video_path)
        info = processor.get_video_info()
        
        cleanup_temp_files(*temp_files)
        return create_response(msg="Video info extracted successfully", data=info)
        
    except ValueError as e:
        cleanup_temp_files(*temp_files)
        return create_response(code=400, msg=str(e)), 400
    except Exception as e:
        cleanup_temp_files(*temp_files)
        return create_response(code=500, msg=f"Failed to extract video info: {str(e)}"), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download processed files"""
    try:
        file_path = os.path.join(TEMP_DIR, filename)
        if not os.path.exists(file_path):
            return create_response(code=404, msg="File not found"), 404
        
        # Check if auto-delete is requested
        auto_delete = request.args.get('auto_delete', 'false').lower() == 'true'
        
        response = send_file(file_path, as_attachment=True, download_name=filename)
        
        if auto_delete:
            # Schedule file deletion after response is sent
            @response.call_on_close
            def cleanup_after_download():
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Auto-deleted file after download: {filename}")
                except Exception as e:
                    print(f"Failed to auto-delete {filename}: {e}")
        
        return response
        
    except Exception as e:
        return create_response(code=500, msg=f"Download failed: {str(e)}"), 500

@app.errorhandler(413)
def file_too_large(e):
    return create_response(code=413, msg="File too large"), 413

@app.errorhandler(404)
def not_found(e):
    return create_response(code=404, msg="Endpoint not found"), 404

@app.errorhandler(500)
def internal_error(e):
    return create_response(code=500, msg="Internal server error"), 500

if __name__ == '__main__':
    # Configuration from environment variables
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '8080'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')
    
    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Start background cleanup thread
    start_cleanup_thread()
    
    # Initial cleanup on startup
    cleanup_old_files()
    
    # Run Flask app
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)