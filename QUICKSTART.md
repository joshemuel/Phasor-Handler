# Quick Start Guide for End Users

This guide is for researchers and lab members who want to use Phasor Handler without programming knowledge.

## Installation (Simple - One Command)

Once published to PyPI, installation will be as simple as:

```powershell
pip install phasor-handler
```

That's it! No need to download code, create environments, or configure anything.

## Launching the Application

After installation, launch Phasor Handler:

```powershell
phasor-handler
```

Or from Python:
```powershell
python -m phasor_handler.app
```

## System Requirements

- **Operating System:** Windows 10 or 11
- **Python:** 3.9, 3.10, 3.11, or 3.12
- **RAM:** 8 GB minimum, 16 GB recommended
- **Disk Space:** ~2 GB for installation

## First Time Setup

1. **Install Python** (if not already installed):
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **Open PowerShell or Command Prompt**

3. **Install Phasor Handler:**
   ```powershell
   pip install phasor-handler
   ```

4. **Launch:**
   ```powershell
   phasor-handler
   ```

## Updating to Latest Version

When new features are released:

```powershell
pip install --upgrade phasor-handler
```

## Uninstallation

```powershell
pip uninstall phasor-handler
```

## Troubleshooting

### "pip is not recognized"
- Python is not in your PATH
- Reinstall Python and check "Add to PATH"

### "Module not found" errors
- Make sure you're in the correct Python environment
- Try: `python -m pip install phasor-handler`

### Application won't launch
- Check Python version: `python --version` (must be 3.9-3.12)
- Reinstall: `pip uninstall phasor-handler` then `pip install phasor-handler`

### Performance issues
- Close other applications
- Ensure at least 8 GB RAM available
- Consider upgrading to 16 GB RAM for large datasets

## Getting Help

- **Documentation:** https://github.com/joshemuel/Phasor-Handler
- **Issues:** https://github.com/joshemuel/Phasor-Handler/issues
- **Email:** Contact your lab's designated Phasor Handler administrator

## Benefits of pip Installation

✅ **Easy Updates:** One command to get the latest features
✅ **No Code:** Don't need to understand Python or Git
✅ **Clean Install:** Automatic dependency management
✅ **Portable:** Works on any Windows computer with Python
✅ **Lab-Wide:** Share the same version across all lab members
