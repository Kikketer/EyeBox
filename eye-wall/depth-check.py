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


def find_closest(depth: np.ndarray, debug: bool = False) -> Tuple[int, int, int]:
    """
    Find the closest valid depth point in the frame.
    
    Args:
        depth: 2D numpy array of depth values
        debug: If True, print debug information about the depth data
        
    Returns:
        tuple: (min_depth, y, x) where (y, x) are the coordinates of the closest point
               and min_depth is its depth value. Returns (0, -1, -1) if no valid points.
    """
    if debug:
        print(f"Depth array shape: {depth.shape}")
        print(f"Depth range: {depth.min()} to {depth.max()}")
        print(f"Non-zero count: {np.count_nonzero(depth > 0)} / {depth.size} pixels")
    
    # Get all valid (non-zero) depth values
    valid_depths = depth[depth > 0]
    
    if len(valid_depths) == 0:
        if debug:
            print("No valid depth values found (all zeros or negative)")
        return (0, -1, -1)
    
    # Find the minimum valid depth
    min_depth = valid_depths.min()
    
    # Find all positions with this minimum depth
    y, x = np.where(depth == min_depth)
    
    if debug:
        print(f"Found {len(y)} points with min depth {min_depth}")
        if len(y) > 0:
            print(f"First point at y={y[0]}, x={x[0]}")
    
    # Return the first occurrence if there are multiple points with same depth
    return (int(min_depth), int(y[0]), int(x[0]))


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
            # Get closest point (with debug disabled for cleaner output)
            min_depth, y, x = find_closest(depth, debug=False)

            if min_depth <= 0 or y == -1 or x == -1:
                # Output zeros if no valid depth
                print("0 0 0")
            else:
                # Output format: depth_mm x_px y_px
                print(f"{min_depth} {x} {y}")
                
                # Optional: Keep debug output but less frequently
                if time.time() % 5 < 0.1:  # Print debug info every ~5 seconds
                    frame_width, frame_height = 640, 480
                    x_pct = (x / frame_width) * 100
                    y_pct = (y / frame_height) * 100
                    print(f"[Debug] Closest: {min_depth}mm at ({x}, {y}) - X:{x_pct:.1f}%, Y:{y_pct:.1f}%", 
                          file=sys.stderr)

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

