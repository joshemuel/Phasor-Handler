#!/usr/bin/env python3
"""
convert.py

Given a SINGLE directory (e.g., StreamingPhasorCapture-...), this script
finds and concatenates .npy stacks for Ch0 and Ch1.

It saves the output TIFF inside the INPUT directory.

The default mode is 'interleaved': [Ch0[0], Ch1[0], Ch0[1], Ch1[1], ...]
"""

import argparse
import os
import re
import sys
from typing import List, Dict
import numpy as np
import tifffile
import cv2


def natural_key(s: str):
    """Natural sort key: 'file10' after 'file2'."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

def list_channel_files(folder_path: str, prefix: str, ext: str = ".npy") -> List[str]:
    """Finds all files in a folder with a given prefix and extension."""
    if ext == ".npy":
        files = [fn for fn in os.listdir(folder_path)
                if fn.startswith(prefix) and fn.endswith(ext)]
        files.sort(key=natural_key)
        return [os.path.join(folder_path, fn) for fn in files]
    elif ext == ".tif" or ext == ".tiff":
        matching_files = []
        for root, _, filenames in os.walk(folder_path):
            # Get the directory name
            dir_name = os.path.basename(root)

            if dir_name.startswith(prefix):
                for root, _, filenames in os.walk(root):
                    files = [fn for fn in filenames
                        if fn.endswith(".tif") or fn.endswith(".tiff")]
                if files:
                    pre_folder = re.search(r'.+\\(.+)\\.+$', root)
                    print(f"Match for prefix '{prefix}' in directory: {pre_folder.group(1)}")
                files.sort(key=natural_key)
                matching_files.extend([os.path.join(root, fn) for fn in files])
        
        return matching_files
    else:
        raise ValueError(f"Unsupported extension: {ext}")
            


def load_and_concat(files: List[str]) -> np.ndarray:
    """Load .npy arrays and concatenate along axis=0 (time)."""
    arrays = []
    for fp in files:
        try:
            arr = np.load(fp, mmap_mode="r")
            arrays.append(arr)
        except Exception as e:
            print(f"[WARN] Skipping '{fp}': {e}", file=sys.stderr)
    if not arrays:
        return None
    # Verify all image stacks have the same XY dimensions
    ref_shape = arrays[0].shape[1:]
    for i, a in enumerate(arrays):
        if a.shape[1:] != ref_shape:
            raise ValueError(f"Shape mismatch in {files[i]}: {a.shape} vs {arrays[0].shape}")
    return np.concatenate(arrays, axis=0)


def subfolder_basename(folder_path: str) -> str:
    """Generates a base filename from the folder path."""
    folder_name = os.path.basename(os.path.normpath(folder_path))
    parts = folder_name.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else folder_name


def write_tiff(out_path: str, data: np.ndarray, force_dtype: str = "uint16"):
    """Writes a NumPy array to a BigTIFF file."""
    if data is None:
        raise ValueError("No image data to write.")
    if force_dtype:
        data = data.astype(force_dtype, copy=False)
    tifffile.imwrite(out_path, data, bigtiff=True)
    print(f"[OK] Saved {out_path}  "
          f"(frames={data.shape[0]}, shape={data.shape[1:]}, dtype={data.dtype})")


def process_single_folder(folder_path: str,
                           source: str = "i3",
                           ch0_prefix: str = None,
                           ch1_prefix: str = None,
                           ext: str = ".npy",
                           mode: str = "interleaved",
                           dtype: str = "uint16"):
    """Processes .npy files in a single directory."""
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"Input path is not a valid directory: {folder_path}")

    ch0_prefix = "ImageData_Ch0" if source == "i3" else "CellVideo1"
    ch1_prefix = "ImageData_Ch1" if source == "i3" else "CellVideo2"
    ext = ".npy" if source == "i3" else ".tiff"

    ch0_files = list_channel_files(folder_path, ch0_prefix, ext)
    ch1_files = list_channel_files(folder_path, ch1_prefix, ext)

    if not ch0_files and not ch1_files:
        print(f"[INFO] No '{ch0_prefix}*' or '{ch1_prefix}*' files found in {folder_path}.")
        return

    ch_data: Dict[str, np.ndarray] = {}
    if ch0_files:
        if ext == ".tif" or ext == ".tiff":
            ch0_result = tifffile.imread(ch0_files)
        else:
            ch0_result = load_and_concat(ch0_files)

        if ch0_result is not None:
            ch_data["Ch0"] = ch0_result
    if ch1_files:
        if ext == ".tif" or ext == ".tiff":
            ch1_result = tifffile.imread(ch1_files)
        else:
            ch1_result = load_and_concat(ch1_files)
        if ch1_result is not None:
            ch_data["Ch1"] = ch1_result

    if len(ch_data) == 0:
        print(f"[WARN] No usable image data loaded from {folder_path}.")
        return

    # Verify that channel spatial dimensions match
    shapes = {k: v.shape[1:] for k, v in ch_data.items() if v is not None}
    if len(set(shapes.values())) > 1:
        raise ValueError(f"Channel spatial shape mismatch in '{folder_path}': {shapes}")

    save_array = None

    if mode == "interleaved":
        if "Ch0" in ch_data and "Ch1" in ch_data:
            ch0, ch1 = ch_data["Ch0"], ch_data["Ch1"]
            if ch0.shape[0] != ch1.shape[0]:
                raise ValueError(f"Frame count mismatch: Ch0 has {ch0.shape[0]} frames, Ch1 has {ch1.shape[0]}")
            n_frames = ch0.shape[0]
            interleaved = np.empty((n_frames * 2, *ch0.shape[1:]), dtype=ch0.dtype)
            interleaved[0::2] = ch0
            interleaved[1::2] = ch1
            save_array = interleaved
        else:
            save_array = ch_data.get("Ch0")
            if save_array is None:
                save_array = ch_data.get("Ch1")
    elif mode == "block":
        concat_list = [ch_data[k] for k in ("Ch0", "Ch1") if k in ch_data]
        save_array = np.concatenate(concat_list, axis=0)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    base = subfolder_basename(folder_path)
    # The output TIFF is saved directly inside the input directory
    out_path = os.path.join(folder_path, f"{base}.tif")
    write_tiff(out_path, save_array, force_dtype=dtype)


def main():
    p = argparse.ArgumentParser(description="Convert .npy stacks from a single Phasor directory to a TIFF.")
    p.add_argument("directory", help="Path to the single 'StreamingPhasorCapture*' folder containing .npy files.")
    p.add_argument("-s", "--source", choices=["i3", "mini"], 
                   help="Microscope source type (required).")
    p.add_argument("--mode", choices=["interleaved", "block"], default="interleaved",
                   help="Channel arrangement. Default is 'interleaved'.")
    args = p.parse_args()

    try:
        process_single_folder(
            folder_path=os.path.abspath(args.directory),
            mode=args.mode,
            source=args.source
        )
    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
