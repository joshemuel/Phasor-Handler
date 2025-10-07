# Contributing to Phasor-Handler

Thanks for your interest in improving Phasor-Handler\! This document explains how to set up a dev environment, coding standards, and how to submit issues/PRs.

> **Platform:** Windows 10/11 only
> **Primary stack:** Python 3.9, PyQt6, NumPy/SciPy, tifffile/tifftools, Suite2p, Matplotlib
> **Env manager:** Conda/Mamba (Windows)

-----

## Development Environment Setup

### 1\. Prerequisites

Before you begin, ensure you have the following installed:

  * [Git](https://git-scm.com/downloads)
  * [Conda](https://www.anaconda.com/products/distribution) (or Miniforge/Mamba for a faster experience)

### 2\. Fork and Clone the Repository

First, create your own copy (a "fork") of the Phasor-Handler repository by clicking the **Fork** button on the GitHub page.

Next, clone your forked repository to your local machine.

```powershell
# Replace <your-username> with your GitHub username
git clone https://github.com/<your-username>/Phasor-Handler.git

# Navigate into the project directory
cd Phasor-Handler
```

### 3\. Create and Activate the Conda Environment

The `environment.yml` file contains all the necessary dependencies. Create the environment using Mamba (recommended for speed) or Conda.

**Using Mamba:**

```powershell
mamba env create -f environment.yml
```

**Or, using Conda:**

```powershell
conda env create -f environment.yml
```

Once the installation is complete, activate the new environment. The environment name is specified inside the `.yml` file (let's assume it's `phasor-handler`).

```powershell
conda activate phasor-handler
```

### 4\. Install the Application in Editable Mode

To ensure that changes you make to the code are immediately reflected when you run the app, install it in "editable" mode.

```powershell
# This links the package to your source code
pip install -e .
```

### 5\. Run the Application

You are now ready to run the application from the root of the project directory.

```powershell
python app.py
```

The application window should now appear. You're all set to start developing\!
