import os
import sys
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal


class ConversionWorker(QObject):
    """Background worker to run conversion and metadata extraction per directory.

    Signals:
        log(str): status or log line
        finished(): emitted when worker completes (success or after error)
        error(str): emitted when an exception occurs

    Contract:
        - __init__(dirs: list[str], mode: str)
        - run(): execute conversion sequentially for dirs
    """

    log = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, dirs, mode):
        super().__init__()
        self.dirs = dirs
        self.mode = mode

    def run(self):
        try:
            self.log.emit(f"--- Starting Batch Conversion in '{self.mode}' mode ---\n")
            
            for i, conv_dir in enumerate(self.dirs):
                self.log.emit(f"Processing ({i+1}/{len(self.dirs)}): {conv_dir}")
                
                # Detect source type based on file pattern
                if any(fname.endswith("000.npy") for fname in os.listdir(conv_dir)):
                    source_type = "i3"
                    self.log.emit("Detected i3 source based on file pattern.")
                else:
                    source_type = "mini"
                    self.log.emit("Detected mini source based on file pattern.")
                
                # 1. Run convert.py
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                convert_script = os.path.join(project_root, 'scripts', 'convert.py')
                
                if not os.path.exists(convert_script):
                    self.log.emit(f"ERROR: Convert script not found: {convert_script}")
                    self.log.emit(f"FAILED to convert: {conv_dir}\n")
                    continue
                
                cmd = [sys.executable, convert_script, str(conv_dir), "-s", source_type, "--mode", self.mode]
                
                try:
                    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        creationflags=creationflags,
                        cwd=project_root
                    )
                    
                    for line in proc.stdout:
                        self.log.emit(line.rstrip())
                    
                    retcode = proc.wait()
                    
                    if retcode != 0:
                        self.log.emit(f"FAILED to convert: {conv_dir}\n")
                        continue
                    else:
                        self.log.emit("--- Conversion done ---\n")
                        
                except Exception as e:
                    self.log.emit(f"FAILED to convert: {conv_dir} (Error: {e})\n")
                    continue

                # 2. Run meta_reader.py
                meta_script = os.path.join(project_root, 'scripts', 'meta_reader.py')
                
                if not os.path.exists(meta_script):
                    self.log.emit(f"ERROR: Metadata script not found: {meta_script}")
                    self.log.emit(f"FAILED to read metadata: {conv_dir}\n")
                    continue
                
                meta_cmd = [sys.executable, meta_script, "-s", source_type, str(conv_dir)]
                self.log.emit(f"\n[meta_reader] Reading metadata for: {conv_dir}")
                
                try:
                    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    meta_proc = subprocess.Popen(
                        meta_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        creationflags=creationflags,
                        cwd=project_root
                    )
                    
                    for line in meta_proc.stdout:
                        self.log.emit(line.rstrip())
                    
                    meta_retcode = meta_proc.wait()
                    
                    if meta_retcode != 0:
                        self.log.emit(f"FAILED to read metadata: {conv_dir}\n")
                    else:
                        self.log.emit("--- Metadata read done ---\n")
                        
                except Exception as e:
                    self.log.emit(f"FAILED to read metadata: {conv_dir} (Error: {e})\n")
                    continue
            
            self.log.emit("--- Batch Conversion Finished ---")
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
