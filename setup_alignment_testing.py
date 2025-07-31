#!/usr/bin/env python3
"""
Setup script for the Alignment Testing System
This will install all dependencies and verify the setup
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def install_chrome_driver():
    """Install Chrome driver automatically"""
    try:
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
        print("✅ Chrome driver installed successfully")
        return True
    except Exception as e:
        print(f"❌ Chrome driver installation failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Satellite-OSM Alignment Testing System")
    print("="*60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return 1
    
    print(f"✅ Python {sys.version} detected")
    
    # Check if we need to create a virtual environment
    venv_path = Path("alignment_venv")
    if not venv_path.exists():
        print("🔧 Creating virtual environment...")
        if not run_command(
            f"{sys.executable} -m venv alignment_venv",
            "Creating virtual environment"
        ):
            return 1
    
    # Determine the correct Python executable for the venv
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/macOS
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"
    
    print(f"✅ Using virtual environment: {venv_path}")
    
    # Install Python dependencies in venv
    if not run_command(
        f"{pip_exe} install -r alignment_testing_requirements.txt",
        "Installing Python dependencies in virtual environment"
    ):
        return 1
    
    # Install Chrome driver in venv
    print("🔧 Installing Chrome driver...")
    if not run_command(
        f"{pip_exe} install chromedriver-autoinstaller",
        "Installing Chrome driver package"
    ):
        print("⚠️  Chrome driver installation failed. Please install manually:")
        print("   - Download from: https://chromedriver.chromium.org/")
        print("   - Add to PATH")
    
    # Verify installations using venv Python
    print("\n🔍 Verifying installations...")
    
    required_packages = [
        'rasterio', 'pyproj', 'shapely', 'folium', 'pystac_client',
        'cv2', 'numpy', 'matplotlib', 'selenium'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            import_name = 'opencv-python' if package == 'cv2' else package
            check_cmd = f"{python_exe} -c \"import {package}; print('✅ {package}')\""
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {package}")
            else:
                print(f"❌ {package}")
                missing_packages.append(package)
        except Exception as e:
            print(f"❌ {package} - {e}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install manually or run setup again")
        return 1
    
    # Create test directories
    print("\n🔧 Creating directories...")
    base_dir = Path("alignment_testing")
    for subdir in ["screenshots", "satellite_data", "results"]:
        dir_path = base_dir / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created {dir_path}")
    
    # Test browser setup using venv
    print("\n🔧 Testing browser setup...")
    browser_test_cmd = f"""{python_exe} -c "
import chromedriver_autoinstaller
chromedriver_autoinstaller.install()
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(options=chrome_options)
driver.get('https://www.google.com')
driver.quit()
print('✅ Browser setup successful')
" """
    
    try:
        result = subprocess.run(browser_test_cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ Browser setup successful")
        else:
            print(f"❌ Browser setup failed: {result.stderr}")
            print("Please ensure Chrome browser is installed")
    except Exception as e:
        print(f"❌ Browser setup failed: {e}")
        print("Please ensure Chrome browser is installed")
    
    print("\n" + "="*60)
    print("🎉 Setup completed successfully!")
    print("\nTo run the alignment testing system:")
    print("1. Activate the virtual environment:")
    if os.name == 'nt':
        print("   alignment_venv\\Scripts\\activate")
    else:
        print("   source alignment_venv/bin/activate")
    print("\n2. Run the alignment test:")
    print("   python alignment_testing_system.py --city Toronto --province Ontario --country Canada")
    print("\nOr use the quick runner:")
    print("   python run_alignment_test.py")
    print("="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())