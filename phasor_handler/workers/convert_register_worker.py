"""
ConvertRegisterWorker - Run conversion then registration per directory in one step.

This worker chains both operations so the user can process directories
with a single button click.
"""

import os
import sys
import glob
import re
import shutil
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal
from phasor_handler.tools.misc import detect_source_type


class ConvertRegisterWorker(QObject):
    """Background worker to run conversion followed by registration per directory."""

    log = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, dirs, mode, reg_params, combine):
        """
        Args:
            dirs: list of directory paths to process
            mode: conversion mode ('interleaved' or 'block')
            reg_params: dict of suite2p parameter overrides
            combine: whether to concatenate registered TIFFs per channel
        """
        super().__init__()
        self.dirs = dirs
        self.mode = mode
        self.reg_params = reg_params
        self.combine = combine

    def run(self):
        try:
            self.log.emit("=== Starting Convert + Register Pipeline ===\n")
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

            for i, conv_dir in enumerate(self.dirs):
                self.log.emit(f"Processing ({i+1}/{len(self.dirs)}): {conv_dir}")

                # --- Phase 1: Conversion ---
                self.log.emit("--- Phase 1: Conversion ---")

                # Detect source type
                source_type = detect_source_type(conv_dir)
                if source_type is None:
                    self.log.emit(f"Can't detect file type for {conv_dir} — skipping.")
                    continue
                self.log.emit(f"Detected {source_type} source based on file pattern.")

                # 1a. Run convert.py
                convert_script = os.path.join(project_root, 'scripts', 'convert.py')
                if not os.path.exists(convert_script):
                    self.log.emit(f"ERROR: Convert script not found: {convert_script}")
                    continue

                cmd = [sys.executable, convert_script, str(conv_dir),
                       "-s", source_type, "--mode", self.mode]
                try:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, creationflags=creationflags, cwd=project_root)
                    for line in proc.stdout:
                        self.log.emit(line.rstrip())
                    if proc.wait() != 0:
                        self.log.emit(f"FAILED to convert: {conv_dir}\n")
                        continue
                    self.log.emit("--- Conversion done ---")
                except Exception as e:
                    self.log.emit(f"FAILED to convert: {conv_dir} (Error: {e})\n")
                    continue

                # 1b. Run meta_reader.py
                meta_script = os.path.join(project_root, 'scripts', 'meta_reader.py')
                if os.path.exists(meta_script):
                    meta_cmd = [sys.executable, meta_script, "-s", source_type, str(conv_dir)]
                    self.log.emit(f"\n[meta_reader] Reading metadata for: {conv_dir}")
                    try:
                        meta_proc = subprocess.Popen(
                            meta_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, creationflags=creationflags, cwd=project_root)
                        for line in meta_proc.stdout:
                            self.log.emit(line.rstrip())
                        meta_proc.wait()
                        self.log.emit("--- Metadata read done ---")
                    except Exception as e:
                        self.log.emit(f"WARNING: Metadata extraction failed: {e}")
                else:
                    self.log.emit(f"WARNING: Metadata script not found: {meta_script}")

                # --- Phase 2: Registration ---
                self.log.emit("\n--- Phase 2: Registration ---")

                # Remove existing suite2p output
                suite2p_dir = os.path.join(conv_dir, "suite2p")
                if os.path.exists(suite2p_dir):
                    self.log.emit("Previous registration exists, overwriting...")
                    shutil.rmtree(suite2p_dir, ignore_errors=True)
                    for ch_name in ["Ch1-reg.tif", "Ch2-reg.tif"]:
                        ch_path = os.path.join(conv_dir, ch_name)
                        if os.path.exists(ch_path):
                            os.remove(ch_path)

                tif_files = [f for f in os.listdir(conv_dir) if f.lower().endswith('.tif')]
                if not tif_files:
                    self.log.emit(f"  No .tif file found for registration in {conv_dir}\n")
                    continue

                movie_path = os.path.join(conv_dir, tif_files[0])
                reg_script = os.path.join(project_root, 'scripts', 'register.py')
                if not os.path.exists(reg_script):
                    self.log.emit(f"ERROR: Registration script not found: {reg_script}")
                    continue

                cmd = [sys.executable, reg_script, "--movie", movie_path, "--outdir", conv_dir]
                for k, v in self.reg_params.items():
                    cmd.extend(["--param", f"{k}={v}"])

                try:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, cwd=project_root)
                    for line in proc.stdout:
                        self.log.emit(line.rstrip())
                    if proc.wait() != 0:
                        self.log.emit(f"FAILED registration: {conv_dir}\n")
                        continue
                    self.log.emit(f"Registration done: {conv_dir}")
                except Exception as e:
                    self.log.emit(f"FAILED registration: {conv_dir} (Error: {e})\n")
                    continue

                # 2b. Concatenation
                if self.combine:
                    self._concatenate_channels(conv_dir, creationflags)

                self.log.emit(f"\n=== Completed ({i+1}/{len(self.dirs)}): {conv_dir} ===\n")

            self.log.emit("=== Convert + Register Pipeline Finished ===")

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def _concatenate_channels(self, outdir, creationflags=0):
        """Concatenate suite2p registered TIFFs into single files per channel."""
        n_channels = int(self.reg_params.get("n_channels", 1))
        channels_to_concat = [("reg_tif", "Ch1-reg.tif")]
        if n_channels >= 2:
            channels_to_concat.append(("reg_tif_chan2", "Ch2-reg.tif"))

        for subfolder, outname in channels_to_concat:
            reg_tif_dir = os.path.join(outdir, "suite2p", "plane0", subfolder)
            if not os.path.isdir(reg_tif_dir):
                self.log.emit(f"  No folder: {reg_tif_dir} (skipping this channel)")
                continue

            tiff_files = glob.glob(os.path.join(reg_tif_dir, "*.tif"))
            if not tiff_files:
                self.log.emit(f"  No .tif files found in {reg_tif_dir}")
                continue

            def natural_sort_key(filepath):
                filename = os.path.basename(filepath)
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split(r'(\d+)', filename)]

            tiff_paths = sorted(tiff_files, key=natural_sort_key)
            out_path = os.path.join(outdir, outname)
            self.log.emit(f"  Combining {len(tiff_paths)} tifs -> {out_path}")

            try:
                import tifftools
                tifftools.tiff_concat(tiff_paths, out_path, overwrite=True)
                self.log.emit(f"  Concatenation completed: {out_path}")
            except Exception as e:
                self.log.emit(f"  tifftools concatenation failed ({e}), trying tifffile fallback...")
                try:
                    import tifffile
                    import numpy as np
                    all_frames = []
                    for tiff_path in tiff_paths:
                        try:
                            frames = tifffile.imread(tiff_path)
                            if frames.ndim == 2:
                                frames = frames[np.newaxis, ...]
                            all_frames.append(frames)
                        except Exception as load_err:
                            self.log.emit(f"    WARNING: Could not load {os.path.basename(tiff_path)}: {load_err}")
                    if all_frames:
                        concatenated = np.concatenate(all_frames, axis=0)
                        tifffile.imwrite(out_path, concatenated)
                        self.log.emit(f"  Fallback concatenation done: {concatenated.shape[0]} frames -> {out_path}")
                    else:
                        self.log.emit(f"  ERROR: No frames could be loaded for concatenation")
                except Exception as e2:
                    self.log.emit(f"  Both concatenation methods failed: {e2}")
