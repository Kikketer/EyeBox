#!/usr/bin/env python3
"""
Continuously read depth data from a Microsoft Kinect (v1) on a Raspberry Pi
using libfreenect's Python bindings, and print the closest object's distance.

Requirements:
- libfreenect installed on the system
- Python bindings for libfreenect (package name: freenect)
- numpy

On Raspberry Pi (Debian-based), you typically need to install libfreenect from
source or via your package manager, then install the Python bindings. Example:
  sudo apt-get install libfreenect0.5 libfreenect-dev
  pip3 install freenect numpy

Run:
  python3 depth-check.py
"""

import sys
import time
from typing import Tuple

try:
    import numpy as np
except Exception as e:
    print("Error: numpy is required. Install with: pip3 install numpy", file=sys.stderr)
    raise

try:
    import freenect
except Exception as e:
    print(
        "Error: freenect (libfreenect Python bindings) not found.\n"
        "Install libfreenect and its Python bindings. For example:\n"
        "  sudo apt-get install libfreenect0.5 libfreenect-dev\n"
        "  pip3 install freenect\n",
        file=sys.stderr,
    )
    raise


def get_depth_mm_supported() -> bool:
    """Return True if freenect exposes millimeters depth format."""
    return hasattr(freenect, "DEPTH_MM")


def read_depth_frame() -> Tuple[np.ndarray, bool]:
    """
    Read a single depth frame.

    Returns a tuple of (depth_array, is_millimeters).
    depth_array shape is (480, 640) for Kinect v1.
    If millimeters are not supported, returns raw 11-bit depth values instead
    and is_millimeters will be False.
    """
    if get_depth_mm_supported():
        fmt = freenect.DEPTH_MM
        depth, _ts = freenect.sync_get_depth(format=fmt)
        # depth is already in millimeters; ensure dtype is uint16 for masking
        depth = depth.astype(np.uint16, copy=False)
        return depth, True
    else:
        # Fallback to raw 11-bit values (0..2047). Units are not mm.
        depth, _ts = freenect.sync_get_depth(format=freenect.DEPTH_11BIT)
        depth = depth.astype(np.uint16, copy=False)
        return depth, False


def find_closest(depth: np.ndarray) -> int:
    """Return the smallest positive (non-zero) depth value from the frame."""
    # Mask out invalid/zero values
    valid = depth > 0
    if not np.any(valid):
        return 0
    return int(depth[valid].min())


def main(loop_delay_s: float = 0.1) -> None:
    # Warm-up read (optional)
    try:
        depth, is_mm = read_depth_frame()
    except Exception as e:
        print(f"Failed to read from Kinect depth stream: {e}", file=sys.stderr)
        sys.exit(1)

    if is_mm:
        print("Depth format: millimeters (mm)")
    else:
        print("Depth format: raw 11-bit units (not millimeters)")

    print("Press Ctrl+C to stop.")
    try:
        while True:
            depth, is_mm = read_depth_frame()
            closest = find_closest(depth)

            if closest <= 0:
                print("No valid depth")
            else:
                if is_mm:
                    meters = closest / 1000.0
                    print(f"Closest: {closest} mm ({meters:.2f} m)")
                else:
                    print(f"Closest: {closest} (raw units)")

            time.sleep(loop_delay_s)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        # Ensure we stop the sync when exiting
        try:
            freenect.sync_stop()
        except Exception:
            pass


if __name__ == "__main__":
    print("Starting depth")
    # Optional: allow a simple CLI arg to set delay
    delay = 0.1
    if len(sys.argv) > 1:
        try:
            delay = float(sys.argv[1])
        except ValueError:
            print(f"Invalid delay '{sys.argv[1]}', using default {delay}s.")
    main(delay)

