#!/usr/bin/env python3
"""
Photo Server for EyeBox

- Serves the photos directory as a simple web server
- When an image or comment.json is accessed, schedules deletion after 10 seconds
- Keeps the photos folder clean for one-time use images

Requirements:
- pip install flask

Usage:
  python3 photo_server.py --dir ./photos --port 8080 --host 0.0.0.0
"""

import argparse
import os
import threading
import time
from pathlib import Path

from flask import Flask, send_from_directory, abort, jsonify

app = Flask(__name__)

# Global config
PHOTOS_DIR = "./photos"
DELETE_DELAY = 10.0  # seconds
deletion_timers = {}  # Track scheduled deletions by file path
deletion_lock = threading.Lock()


def schedule_deletion(file_path: str):
    """Schedule a file for deletion after DELETE_DELAY seconds.
    Also deletes associated sidecar files (comment.json).
    """
    abs_path = os.path.abspath(file_path)
    
    with deletion_lock:
        # Cancel existing timer if already scheduled
        if abs_path in deletion_timers:
            deletion_timers[abs_path].cancel()
        
        # Schedule new deletion
        timer = threading.Timer(DELETE_DELAY, delete_file_and_sidecars, args=(abs_path,))
        deletion_timers[abs_path] = timer
        timer.start()
        print(f"[server] Scheduled deletion for: {os.path.basename(abs_path)} in {DELETE_DELAY}s")


def delete_file_and_sidecars(file_path: str):
    """Delete the file and any associated sidecar files."""
    try:
        if os.path.exists(file_path):
            # Delete the main file
            os.remove(file_path)
            print(f"[server] Deleted: {os.path.basename(file_path)}")
            
            # Delete sidecar comment.json if it exists (in the same directory)
            dir_path = os.path.dirname(file_path)
            comment_json = os.path.join(dir_path, "comment.json")
            if os.path.exists(comment_json):
                os.remove(comment_json)
                print(f"[server] Deleted sidecar: comment.json")
    except Exception as e:
        print(f"[server] Error deleting {file_path}: {e}")
    finally:
        with deletion_lock:
            deletion_timers.pop(file_path, None)


@app.route('/')
def index():
    """List all files in the photos directory."""
    try:
        files = []
        photos_path = Path(PHOTOS_DIR)
        if photos_path.exists():
            for item in sorted(photos_path.iterdir()):
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "url": f"/{item.name}",
                        "size": item.stat().st_size
                    })
        return jsonify({
            "photos_directory": PHOTOS_DIR,
            "files": files,
            "note": "Accessing a file will schedule it for deletion in 10 seconds"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/<path:filename>')
def serve_file(filename):
    """Serve a file from the photos directory and schedule it for deletion."""
    try:
        file_path = os.path.join(PHOTOS_DIR, filename)
        
        # Security: prevent directory traversal
        if not os.path.abspath(file_path).startswith(os.path.abspath(PHOTOS_DIR)):
            abort(403)
        
        if not os.path.exists(file_path):
            abort(404)
        
        # Schedule deletion for this file
        schedule_deletion(file_path)
        
        # If it's comment.json, also schedule deletion of associated images
        if filename == "comment.json":
            # Find and schedule all image files in the directory
            photos_path = Path(PHOTOS_DIR)
            for item in photos_path.iterdir():
                if item.is_file() and item.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                    schedule_deletion(str(item))
        
        return send_from_directory(PHOTOS_DIR, filename)
    except Exception as e:
        print(f"[server] Error serving {filename}: {e}")
        abort(500)


def main():
    parser = argparse.ArgumentParser(description="Serve photos directory with auto-deletion after access")
    parser.add_argument("--dir", default="./photos", help="Directory to serve (default: ./photos)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--delay", type=float, default=10.0, help="Deletion delay in seconds (default: 10.0)")
    args = parser.parse_args()
    
    global PHOTOS_DIR, DELETE_DELAY
    PHOTOS_DIR = os.path.abspath(args.dir)
    DELETE_DELAY = args.delay
    
    if not os.path.isdir(PHOTOS_DIR):
        print(f"[server] Creating directory: {PHOTOS_DIR}")
        os.makedirs(PHOTOS_DIR, exist_ok=True)
    
    print(f"[server] Serving: {PHOTOS_DIR}")
    print(f"[server] Listening on: http://{args.host}:{args.port}")
    print(f"[server] Delete delay: {DELETE_DELAY}s after access")
    print(f"[server] Access http://{args.host}:{args.port}/ to list files")
    
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
