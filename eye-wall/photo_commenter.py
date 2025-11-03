#!/usr/bin/env python3
"""
Photo watcher for EyeBox

- Monitors the photos directory created by focus-eyes.py
- When a new image appears, waits until it is fully written
- Sends the image to a local Ollama vision model
- Writes a single social-media-style comment to a sidecar .comment.txt file next to the image

Requirements:
- pip install watchdog ollama
- Ollama running locally with a vision model pulled (e.g., `ollama pull llava` or `ollama pull llama3.2-vision`)

Usage:
  python3 photo_watcher.py --dir ./photos --model llava
"""

import argparse
import os
import json
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

# Optional: import ollama package (local API). If not available, we error with a clear message.
try:
    import ollama  # type: ignore
except Exception as e:  # pragma: no cover
    ollama = None

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def is_supported_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTS


def wait_for_stable_file(path: str, timeout: float = 10.0, poll: float = 0.25) -> bool:
    """Wait until the file size stops changing, up to timeout seconds.
    Returns True if stable, False if timed out or file missing.
    """
    start = time.time()
    last_size = -1
    while time.time() - start < timeout:
        if not os.path.exists(path):
            return False
        try:
            size = os.path.getsize(path)
        except OSError:
            size = -1
        if size == last_size and size > 0:
            return True
        last_size = size
        time.sleep(poll)
    return False


@dataclass
class WorkItem:
    path: str


class PhotoEventHandler(FileSystemEventHandler):
    def __init__(self, work_q: "queue.Queue[WorkItem]") -> None:
        super().__init__()
        self.work_q = work_q

    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            print("Image was added!")
            if is_supported_image(event.src_path):
                self.work_q.put(WorkItem(event.src_path))

def generate_comment_with_ollama(model: str, image_path: str, timeout: float = 120.0) -> str:
    if ollama is None:
        raise RuntimeError("The 'ollama' Python package is not installed. Install it with: pip install ollama")

    print("Asking AI to generate a comment...")
    prompt = (
        "Analyze this photo of a person's face and briefly note notable visual features (e.g., hair color, face shape, clothing, etc).\n"
        "Then craft ONE short, friendly, complimentary, social-media-style comment for the photo.\n"
        "- Keep it under 30 words.\n"
        "- No hashtags.\n"
        "- No emojis.\n"
        "Return ONLY the final comment text."
    )

    # Use the images parameter supported by Ollama's vision-capable models
    resp = ollama.generate(
        model=model,
        prompt=prompt,
        images=[image_path],
        options={"temperature": 0.7},
        keep_alive=timeout,
    )
    # Response structure typically: { 'model': ..., 'created_at': ..., 'response': 'text', ... }
    text = resp.get("response", "").strip()
    print(f"Comment generated: {text}")
    return text


def process_image(model: str, image_path: str) -> None:
    if not wait_for_stable_file(image_path):
        print(f"[watcher] Skipping (unstable or missing): {image_path}")
        return

    try:
        comment = generate_comment_with_ollama(model, image_path)
        if not comment:
            print(f"[watcher] No comment generated for {image_path}")
            return
        out_path = image_path + ".comment.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(comment + "\n")
        print(f"[watcher] Comment saved: {out_path}")

        # Also write/update a single JSON file in the same folder: comment.json
        dir_path = os.path.dirname(image_path)
        json_path = os.path.join(dir_path, "comment.json")
        try:
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump({"comment": comment}, jf, ensure_ascii=False)
            print(f"[watcher] JSON comment saved: {json_path}")
        except Exception as je:
            print(f"[watcher] Failed to write JSON comment: {je}")
    except Exception as e:
        print(f"[watcher] Error processing {image_path}: {e}")


def worker(model: str, work_q: "queue.Queue[WorkItem]", stop_event: threading.Event):
    seen = {}
    while not stop_event.is_set():
        try:
            item = work_q.get(timeout=0.5)
        except queue.Empty:
            continue
        path = item.path
        # De-dupe quick successive events
        last_ts = seen.get(path, 0)
        now = time.time()
        if now - last_ts < 0.5:
            continue
        seen[path] = now
        if is_supported_image(path):
            print("Processing image...")
            process_image(model, path)
        work_q.task_done()


def main():
    parser = argparse.ArgumentParser(description="Watch a folder for new images and generate comments via Ollama.")
    parser.add_argument("--dir", default=os.path.join(os.getcwd(), "photos"), help="Directory to watch (default: ./photos)")
    parser.add_argument("--model", default="qwen3-vl:2b", help="Ollama vision model to use (e.g., qwen3-vl, llava, llama3.2-vision)")
    args = parser.parse_args()

    watch_dir = os.path.abspath(args.dir)
    if not os.path.isdir(watch_dir):
        print(f"[watcher] Creating directory: {watch_dir}")
        os.makedirs(watch_dir, exist_ok=True)

    if ollama is None:
        print("[watcher] Missing dependency: ollama. Install with: pip install ollama")
        return 1

    print(f"[watcher] Watching: {watch_dir}")
    print(f"[watcher] Using model: {args.model}")

    # Quick test: process first existing photo in directory
    print("[watcher] Looking for existing photos to test...")
    existing_photos = []
    try:
        for filename in os.listdir(watch_dir):
            filepath = os.path.join(watch_dir, filename)
            if os.path.isfile(filepath) and is_supported_image(filepath):
                existing_photos.append(filepath)
        
        if existing_photos:
            test_photo = existing_photos[0]
            print(f"[watcher] Running test with: {os.path.basename(test_photo)}")
            process_image(args.model, test_photo)
            print("[watcher] Test complete!\n")
        else:
            print("[watcher] No existing photos found for testing.\n")
    except Exception as e:
        print(f"[watcher] Error during test: {e}\n")

    work_q: "queue.Queue[WorkItem]" = queue.Queue()
    handler = PhotoEventHandler(work_q)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=False)

    stop_event = threading.Event()

    th = threading.Thread(target=worker, args=(args.model, work_q, stop_event), daemon=True)
    th.start()

    def handle_sigint(_sig, _frame):
        print("\n[watcher] Shutting down...")
        stop_event.set()
        observer.stop()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    observer.start()
    try:
        while observer.is_alive():
            time.sleep(0.5)
    finally:
        observer.join(timeout=5)
        return 0


if __name__ == "__main__":
    sys.exit(main())
