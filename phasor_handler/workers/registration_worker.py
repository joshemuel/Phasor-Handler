import os
import sys
import glob
import shutil
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal


class RegistrationWorker(QObject):
    """Background worker to run suite2p registration per directory.

    Signals:
        log(str): status or log line
        finished(): emitted when worker completes (success or after error)
        error(str): emitted when an exception occurs

    Contract:
        - __init__(dirs: list[str], params: dict, combine: bool)
        - run(): execute registration sequentially for dirs
    """

    log = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, dirs, params, combine):
        super().__init__()
        self.dirs = dirs
        self.params = params
        self.combine = combine

    def run(self):
        try:
            for i, reg_dir in enumerate(self.dirs):
                self.log.emit(f"[{i+1}/{len(self.dirs)}] Registering: {reg_dir}")
                if os.path.exists(os.path.join(reg_dir, "suite2p")):
                    self.log.emit("Registration exists, overwriting...\n")
                    shutil.rmtree(os.path.join(reg_dir, "suite2p"), ignore_errors=True)
                    ch1_path = os.path.join(reg_dir, "Ch1-reg.tif")
                    ch2_path = os.path.join(reg_dir, "Ch2-reg.tif")
                    if os.path.exists(ch1_path):
                        os.remove(ch1_path)
                    if os.path.exists(ch2_path):
                        os.remove(ch2_path)

                tif_files = [f for f in os.listdir(reg_dir) if f.lower().endswith('.tif')]
                if not tif_files:
                    self.log.emit(f"  No .tif file found in {reg_dir}\n")
                    continue
                movie_path = os.path.join(reg_dir, tif_files[0])
                outdir = reg_dir
                # Resolve the project root and the absolute path to the register script
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                script_path = os.path.join(project_root, 'scripts', 'register.py')
                if not os.path.exists(script_path):
                    self.log.emit(f"Script not found: {script_path}")
                    self.log.emit(f"FAILED: {reg_dir}\n")
                    continue
                cmd = [sys.executable, script_path, "--movie", movie_path, "--outdir", outdir]
                for k, v in self.params.items():
                    cmd.extend(["--param", f"{k}={v}"])

                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=project_root)
                    for line in proc.stdout:
                        self.log.emit(line.rstrip())
                    retcode = proc.wait()
                    if retcode != 0:
                        self.log.emit(f"FAILED: {reg_dir}\n")
                    else:
                        self.log.emit(f"Registration done: {reg_dir}\n")
                except Exception as e:
                    self.log.emit(f"FAILED: {reg_dir} (Error: {e})\n")
                    continue

                if self.combine:
                    # Determine which channels to concatenate based on user's nchannels parameter
                    n_channels = int(self.params.get("n_channels", 1))
                    channels_to_concat = [("reg_tif", "Ch1-reg.tif")]
                    if n_channels >= 2:
                        channels_to_concat.append(("reg_tif_chan2", "Ch2-reg.tif"))
                    
                    for subfolder, outname in channels_to_concat:
                        reg_tif_dir = os.path.join(outdir, "suite2p", "plane0", subfolder)
                        if not os.path.isdir(reg_tif_dir):
                            self.log.emit(f"  No folder: {reg_tif_dir} (skipping this channel)")
                            continue
                        
                        # Get all TIFF files and sort them with proper numerical ordering
                        tiff_files = glob.glob(os.path.join(reg_tif_dir, "*.tif"))
                        if not tiff_files:
                            self.log.emit(f"  No .tif files found in {reg_tif_dir}")
                            continue
                        
                        # Smart sorting for numerical filenames (handles file_001.tif, file_010.tif correctly)
                        def natural_sort_key(filepath):
                            import re
                            filename = os.path.basename(filepath)
                            # Extract numbers from filename and pad them for proper sorting
                            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]
                        
                        tiff_paths = sorted(tiff_files, key=natural_sort_key)
                            
                        # Enhanced logging for debugging
                        self.log.emit(f"  Found {len(tiff_paths)} TIFF files in {reg_tif_dir}")
                        self.log.emit(f"  First few files: {[os.path.basename(p) for p in tiff_paths[:5]]}")
                        if len(tiff_paths) > 5:
                            self.log.emit(f"  Last few files: {[os.path.basename(p) for p in tiff_paths[-3:]]}")
                        
                        out_path = os.path.join(outdir, outname)
                        self.log.emit(f"  Combining {len(tiff_paths)} tifs -> {out_path}")
                        
                        try:
                            # Verify all input files exist and count total frames
                            valid_paths = []
                            total_size = 0
                            total_expected_frames = 0
                            
                            # First pass: validate files and count frames
                            for i, tiff_path in enumerate(tiff_paths):
                                if not os.path.exists(tiff_path) or os.path.getsize(tiff_path) == 0:
                                    self.log.emit(f"  WARNING: Skipping invalid/empty file: {os.path.basename(tiff_path)}")
                                    continue
                                    
                                try:
                                    # Count frames in each TIFF file using tifftools
                                    import tifftools
                                    info = tifftools.read_tiff(tiff_path)
                                    frame_count = len(info['ifds']) if 'ifds' in info else 1
                                    total_expected_frames += frame_count
                                    
                                    valid_paths.append(tiff_path)
                                    total_size += os.path.getsize(tiff_path)
                                    
                                    # Log progress for large numbers of files
                                    if i < 5 or i >= len(tiff_paths) - 3:
                                        self.log.emit(f"    {os.path.basename(tiff_path)}: {frame_count} frames")
                                    elif i == 5:
                                        self.log.emit(f"    ... processing {len(tiff_paths) - 8} more files ...")
                                        
                                except Exception as frame_error:
                                    self.log.emit(f"  WARNING: Could not read frame count from {os.path.basename(tiff_path)}: {frame_error}")
                                    # Still include the file, assume 1 frame
                                    valid_paths.append(tiff_path)
                                    total_size += os.path.getsize(tiff_path)
                                    total_expected_frames += 1
                            
                            if not valid_paths:
                                self.log.emit(f"  ERROR: No valid TIFF files found for concatenation")
                                continue
                                
                            self.log.emit(f"  Using {len(valid_paths)} valid files (total size: {total_size/1024/1024:.1f} MB)")
                            self.log.emit(f"  Expected total frames after concatenation: {total_expected_frames}")
                            
                            # Perform concatenation
                            self.log.emit(f"  Starting concatenation with tifftools...")
                            tifftools.tiff_concat(valid_paths, out_path, overwrite=True)
                            
                            # Verify output file
                            if os.path.exists(out_path):
                                output_size = os.path.getsize(out_path)
                                self.log.emit(f"  Concatenation completed: {out_path} (size: {output_size/1024/1024:.1f} MB)")
                                
                                # Verify frame count in output file
                                try:
                                    output_info = tifftools.read_tiff(out_path)
                                    actual_frames = len(output_info['ifds']) if 'ifds' in output_info else 1
                                    self.log.emit(f"  Output file contains {actual_frames} frames (expected: {total_expected_frames})")
                                    
                                    if actual_frames != total_expected_frames:
                                        self.log.emit(f"  WARNING: Frame count mismatch! Expected {total_expected_frames}, got {actual_frames}")
                                        self.log.emit(f"  This indicates incomplete concatenation - some frames may be missing!")
                                    else:
                                        self.log.emit(f"  SUCCESS: All {actual_frames} frames concatenated correctly!")
                                        
                                except Exception as verify_error:
                                    self.log.emit(f"  WARNING: Could not verify output frame count: {verify_error}")
                                
                                # Size comparison
                                if output_size < total_size * 0.5:  # If output is less than 50% of input
                                    self.log.emit(f"  WARNING: Output file seems much smaller than expected!")
                                    self.log.emit(f"  Input total: {total_size/1024/1024:.1f} MB, Output: {output_size/1024/1024:.1f} MB")
                                    
                            else:
                                self.log.emit(f"  ERROR: Output file was not created: {out_path}")
                                
                        except Exception as e:
                            self.log.emit(f"  FAILED to combine tifs with tifftools (Error: {e})")
                            import traceback
                            self.log.emit(f"  Traceback: {traceback.format_exc()}")
                            
                            # Try alternative concatenation method using tifffile
                            self.log.emit(f"  Attempting alternative concatenation method...")
                            try:
                                import tifffile
                                import numpy as np
                                
                                self.log.emit(f"  Loading and concatenating {len(valid_paths)} TIFF files with tifffile...")
                                all_frames = []
                                
                                for i, tiff_path in enumerate(valid_paths):
                                    try:
                                        frames = tifffile.imread(tiff_path)
                                        if frames.ndim == 2:
                                            frames = frames[np.newaxis, ...]  # Add frame dimension
                                        all_frames.append(frames)
                                        
                                        if i % 100 == 0 or i < 5 or i >= len(valid_paths) - 3:
                                            self.log.emit(f"    Loaded {os.path.basename(tiff_path)}: {frames.shape}")
                                            
                                    except Exception as load_error:
                                        self.log.emit(f"    ERROR loading {os.path.basename(tiff_path)}: {load_error}")
                                        continue
                                
                                if all_frames:
                                    self.log.emit(f"  Concatenating {len(all_frames)} file arrays...")
                                    concatenated = np.concatenate(all_frames, axis=0)
                                    self.log.emit(f"  Final concatenated shape: {concatenated.shape}")
                                    
                                    self.log.emit(f"  Saving concatenated TIFF to {out_path}...")
                                    tifffile.imwrite(out_path, concatenated)
                                    
                                    if os.path.exists(out_path):
                                        output_size = os.path.getsize(out_path)
                                        self.log.emit(f"  Alternative concatenation SUCCESS: {out_path}")
                                        self.log.emit(f"  Output: {concatenated.shape[0]} frames, {output_size/1024/1024:.1f} MB")
                                    else:
                                        self.log.emit(f"  ERROR: Alternative method failed to create output file")
                                else:
                                    self.log.emit(f"  ERROR: No frames could be loaded for alternative concatenation")
                                    
                            except Exception as alt_error:
                                self.log.emit(f"  Alternative concatenation also FAILED: {alt_error}")
                                self.log.emit(f"  Both concatenation methods failed for {reg_tif_dir}")
                else:
                    self.log.emit("Skipping concatenation...")

            self.log.emit("--- Batch Registration Finished ---")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
