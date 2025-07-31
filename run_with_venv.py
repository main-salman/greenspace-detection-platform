#!/usr/bin/env python3
"""
Wrapper script to run alignment testing with virtual environment
This automatically activates the virtual environment and runs the test
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run alignment test with virtual environment"""
    
    # Check if virtual environment exists
    venv_path = Path("alignment_venv")
    if not venv_path.exists():
        print("❌ Virtual environment not found. Please run setup first:")
        print("   python3 setup_alignment_testing.py")
        return 1
    
    # Determine the correct Python executable for the venv
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
    else:  # Unix/macOS
        python_exe = venv_path / "bin" / "python"
    
    if not python_exe.exists():
        print(f"❌ Python executable not found in virtual environment: {python_exe}")
        return 1
    
    # Pass all arguments to the run script
    cmd = [str(python_exe), "run_alignment_test.py"] + sys.argv[1:]
    
    print("🚀 Running alignment test with virtual environment...")
    print(f"Command: {' '.join(cmd)}")
    print("="*60)
    
    # Run the command
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())