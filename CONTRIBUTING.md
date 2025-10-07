# Contributing to Phasor-Handler

Thanks for your interest in improving Phasor-Handler! This document explains how to set up a dev environment, coding standards, and how to submit issues/PRs.

> **Platform:** Windows 10/11 only  
> **Primary stack:** Python 3.9, PyQt6, NumPy/SciPy, tifffile/tifftools, Suite2p, Matplotlib  
> **Env manager:** Conda/Mamba (Windows)

---

## Quick Start (Development)

1) **Fork & clone**
```powershell
git clone https://github.com/<your-user>/<your-fork>.git
cd <your-fork>

2) **Environment**
- Make sure you create environment.
- Create and activate:
```powershell
  mamba env create -f environment.yml 
  conda activate suite2p

3) **Run the app**
```powershell
  python app.py