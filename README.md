# Phasor-Handler v2.0 (Windows)

Phasor Handler is a toolbox for processing raw two-photon phasor imaging data: **convert → register → explore → extract calcium traces**.  
It provides a PyQt6 GUI for viewing registered or raw stacks (Ch1/Ch2), z-projections (std/max/mean), drawing/storing ROIs, overlaying stimulated ROIs from metadata, and exporting ROI traces.

> ⚠️ **Platform:** Windows 10/11 only  
> 🧪 Status: actively developed (Brightness & Contrast dialog is WIP)

---

## Features

- Load **registered TIFF** (`Ch1-reg.tif`, `Ch2-reg.tif`) or **raw NPY** fallbacks (`ImageData_Ch0_TP0000000.npy`, `ImageData_Ch1_TP0000000.npy`)
- Linear and non-linear motion-correct **TIFF images** using Suite2p
- Automated cell detection using Suite2p
- Channel switching (Ch1/Ch2) and **Composite (G/R)**
- **Z-projections**: standard deviation, max, mean
- **ROI tools**: draw elliptical ROIs, translate or rotate ROIs, save/load as JSON, quick-select saved ROIs
- **Stimulus overlay**: show stimulated ROI locations from experiment metadata and add to the saved ROIs
- **Trace plotting**: configurable formula, custom y-limits, frame/time (s) x-axis
- **Export**: write per-ROI traces for all frames to `.txt` (tab-separated)
- Keyboard: `R` save/add ROI, `Delete` remove selected ROI, `Esc` clear selection, `Alt+S` load stimulated ROIs, `Right Click + drag` translate selected ROI, `Y` toggle right click to rotation mode

---

## Input data layout

For each dataset directory, Phasor Handler looks for any of:

<dataset_dir>/
├── Ch1-reg.tif
├── Ch2-reg.tif                 # optional
├── ImageData_Ch0_TP0000000.npy # raw fallback for Ch1
├── ImageData_Ch1_TP0000000.npy # optional raw fallback for Ch2
└── experiment_summary.pkl      # optional metadata (or .json)

Registered TIFFs are preferred when available; raw NPYs are used as fallback.

---

## Installation (Windows, Conda)

This project provides an `environment.yml` for Windows. The environment is large (GUI, image I/O, napari/suite2p), so **mamba** is recommended, but `conda` works too.

### 1) Install Conda/Mamba (if needed)
- Install **Miniconda** or **Mambaforge** on Windows.
- (Optional) Add mamba for faster solves:
  ```powershell
  conda install -n base -c conda-forge mamba

### 2) Get the code
- Clone the repo and change it into
  ```powershell
  git clone https://github.com/<your-user>/<your-repo>.git
  cd <your-repo>
- Alternatively, you can download the entire project as a zip file, unzip it, then open that directory in **Miniconda**
  cd <your-repo>

### 3) Create the environment
- Using mamba:
  ```powershell
  mamba env create -f environment.yml
- Using conda:
  ```powershell
  conda env create -f environment.yml

# 4) Activate and run
- Before running the toolbox, activate the environment
  ```powershell
  conda activate suite2p
  python app.py
