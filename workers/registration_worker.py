import os
import sys
import glob
import shutil
import subprocess
import tifftools
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
                    for subfolder, outname in [("reg_tif", "Ch1-reg.tif"), ("reg_tif_chan2", "Ch2-reg.tif")]:
                        reg_tif_dir = os.path.join(outdir, "suite2p", "plane0", subfolder)
                        if not os.path.isdir(reg_tif_dir):
                            self.log.emit(f"  No folder: {reg_tif_dir}")
                            continue
                        tiff_paths = sorted(glob.glob(os.path.join(reg_tif_dir, "*.tif")))
                        if not tiff_paths:
                            self.log.emit(f"  No .tif files found in {reg_tif_dir}")
                            continue
                        out_path = os.path.join(outdir, outname)
                        self.log.emit(f"  Combining {len(tiff_paths)} tifs from {reg_tif_dir} -> {out_path}")
                        try:
                            tifftools.tiff_concat(tiff_paths, out_path, overwrite=True)
                            self.log.emit(f"  Combine done: {out_path}")
                        except Exception as e:
                            self.log.emit(f"  FAILED to combine tifs in {reg_tif_dir} (Error: {e})")
                else:
                    self.log.emit("Skipping concatenation...")

            self.log.emit("--- Batch Registration Finished ---")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
