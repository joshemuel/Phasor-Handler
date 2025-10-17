# Publishing Phasor Handler to PyPI

This guide walks through the steps to prepare and publish Phasor Handler to PyPI.

## Prerequisites

1. Install build tools:
```powershell
pip install --upgrade pip setuptools wheel twine build
```

2. Create PyPI account at https://pypi.org/account/register/

3. Create API token at https://pypi.org/manage/account/token/

## Project Structure Changes Needed

Before publishing, the project needs to be reorganized to be pip-compatible:

### 1. Rename root modules to `phasor_handler` package

Create a new directory structure:
```
Phasor-Handler/
├── phasor_handler/           # New package directory
│   ├── __init__.py          # Package init
│   ├── app.py               # Move from root
│   ├── widgets/             # Move from root
│   ├── workers/             # Move from root
│   ├── models/              # Move from root
│   ├── scripts/             # Move from root
│   ├── tools/               # Move from root
│   ├── themes/              # Move from root
│   └── img/                 # Move from root
├── pyproject.toml           # ✅ Already created
├── MANIFEST.in              # ✅ Already created
├── README.md                # Keep at root
├── LICENSE.md               # Keep at root
└── environment.yml          # Keep at root
```

###  app.py to have a main() function

The current `app.py` needs a `main()` function for the entry point:

```python
# At the end of app.py, replace the __main__ block with:

def main():
    """Main entry point for Phasor Handler application."""
    app = QApplication(sys.argv)
    
    qdarktheme.setup_theme()
    
    window = MainWindow()
    window.showMaximized()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
```

### 3. Create `phasor_handler/__init__.py`

```python
"""
Phasor Handler - Two-Photon Phasor Imaging Data Processor

A PyQt6 GUI toolbox for processing two-photon phasor imaging data.
"""

__version__ = "2.2.0"
__author__ = "Josia Shemuel"
__all__ = ["app", "widgets", "workers", "models", "scripts", "tools", "themes"]
```

### 4. Update imports in moved files

After moving files to `phasor_handler/`, update all imports:

```python
# Old import
from widgets import ConversionWidget

# New import  
from phasor_handler.widgets import ConversionWidget
```

## Building the Package

1. **Test the package structure:**
```powershell
python -m build --sdist --wheel .
```

This creates `dist/` directory with:
- `phasor-handler-2.2.0.tar.gz` (source distribution)
- `phasor_handler-2.2.0-py3-none-any.whl` (wheel)

2. **Test installation locally:**
```powershell
pip install dist/phasor_handler-2.0.0-py3-none-any.whl
```

3. **Test the installed package:**
```powershell
phasor-handler
```

## Publishing to PyPI

### Test PyPI (Recommended First)

1. Upload to Test PyPI:
```powershell
python -m twine upload --repository testpypi dist/*
```

2. Test install from Test PyPI:
```powershell
pip install --index-url https://test.pypi.org/simple/ phasor-handler
```

### Production PyPI

1. Upload to PyPI:
```powershell
python -m twine upload dist/*
```

2. Users can then install:
```powershell
pip install phasor-handler
```

## Post-Publication Usage

### For End Users (Non-Programmers)

Simple installation:
```powershell
# Install
pip install phasor-handler

# Launch
phasor-handler

# Or from Python
python -m phasor_handler.app
```

### For Developers

Clone and install in editable mode:
```powershell
git clone https://github.com/joshemuel/Phasor-Handler.git
cd Phasor-Handler
pip install -e .
```

## Version Updates

When releasing new versions:

1. Update version in `pyproject.toml`
2. Update `__version__` in `phasor_handler/__init__.py`
3. Tag the release in git:
```powershell
git tag v2.0.1
git push origin v2.0.1
```
4. Rebuild and upload:
```powershell
python -m build
python -m twine upload dist/*
```

## Troubleshooting

### Import Errors
- Ensure all `__init__.py` files exist in subdirectories
- Check that imports use `phasor_handler.` prefix

### Missing Files
- Update `MANIFEST.in` to include data files
- Use `python -m build --sdist` and inspect the tarball

### Dependencies
- Test installation in a clean virtual environment
- Verify all dependencies are listed in `pyproject.toml`

## Alternative: Using setup.py (Legacy)

If you prefer `setup.py`, here's a minimal version:

```python
from setuptools import setup, find_packages

setup(
    name="phasor-handler",
    version="2.2.0",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.4.0",
        "numpy>=1.21.0,<2.0.0",
        "matplotlib>=3.5.0",
        "tifffile>=2021.11.2",
        "pyyaml>=6.0",
        "suite2p>=0.14.0",
        "qdarktheme>=1.0.0",
        "Pillow>=9.0.0",
        "scikit-image>=0.19.0",
        "scipy>=1.7.0",
    ],
    entry_points={
        'gui_scripts': [
            'phasor-handler=phasor_handler.app:main',
        ],
    },
)
```

However, `pyproject.toml` is the modern standard and preferred approach.
