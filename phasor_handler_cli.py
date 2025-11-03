#!/usr/bin/env python3
"""
Phasor Handler - Two-Photon Phasor Imaging Data Processor

Command-line interface for running Phasor Handler from pip installation.
"""

import sys


def main():
    """Main entry point for the Phasor Handler application."""
    try:
        from phasor_handler.app import main as app_main
        sys.exit(app_main())
    except ImportError:
        # Fallback for running from source without installation
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, parent_dir)
        
        from phasor_handler.app import main as app_main
        sys.exit(app_main())


if __name__ == "__main__":
    main()
