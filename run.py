#!/usr/bin/env python3
"""
WeeklyPilot - Cross-platform launcher
Works on Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def find_python():
    """Find Python interpreter"""
    # Check current interpreter
    if sys.executable:
        return sys.executable
    
    # Try common names
    for name in ["python3", "python"]:
        path = shutil.which(name)
        if path:
            return path
    
    return None


def check_python_version(python_path):
    """Check Python version (requires 3.8+)"""
    try:
        result = subprocess.run(
            [python_path, "--version"],
            capture_output=True,
            text=True
        )
        version_str = result.stdout.strip()
        if not version_str:
            version_str = result.stderr.strip()
        
        # Parse version
        parts = version_str.split()
        if len(parts) >= 2:
            version = parts[1]
            major, minor = map(int, version.split(".")[:2])
            if major < 3 or (major == 3 and minor < 8):
                return False, version
            return True, version
    except Exception:
        pass
    
    return True, "unknown"


def create_env_if_needed():
    """Create .env from .env.example if not exists"""
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if not env_path.exists() and example_path.exists():
        shutil.copy(example_path, env_path)
        print("\n[SETUP] Created .env from .env.example")
        print("[SETUP] Please edit .env and fill in your account info before running.")
        print("       Required fields: LANQIAO_USERNAME, LANQIAO_PASSWORD, OPENAI_API_KEY")
        
        # Try to open in default editor
        try:
            if sys.platform == "win32":
                os.startfile(str(env_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(env_path)])
            else:
                subprocess.run(["xdg-open", str(env_path)])
        except Exception:
            print(f"\nPlease edit: {env_path.absolute()}")
        
        input("\nPress Enter to continue...")
        return False
    
    return True


def install_dependencies(python_path):
    """Install dependencies if needed"""
    try:
        subprocess.run(
            [python_path, "-c", "import flask"],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        pass
    
    print("\n[SETUP] First run detected, installing dependencies...")
    
    # Try with mirror first (for users in China)
    try:
        subprocess.run(
            [python_path, "-m", "pip", "install", "-r", "requirements.txt", 
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
            check=True
        )
        print("[SETUP] Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        pass
    
    # Retry with default source
    print("[WARN] Install with mirror failed, retrying with default source...")
    try:
        subprocess.run(
            [python_path, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print("[SETUP] Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        pass
    
    print("[ERROR] Failed to install dependencies. Please run manually:")
    print(f"       {python_path} -m pip install -r requirements.txt")
    return False


def show_help():
    """Show help message"""
    print("""
Usage: python run.py [mode] [args]

Modes:
  select       Visual select mode (default)
  direct       Direct input mode
  catalog ID   View course catalog
  test ID      Test mode
  clear-cache  Clear cache
  help         Show help
""")


def main():
    """Main entry point"""
    print("\n" + "=" * 50)
    print("  WeeklyPilot - LanQiao Weekly Report System V4.1")
    print("=" * 50 + "\n")
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Find Python
    python_path = find_python()
    if not python_path:
        print("[ERROR] Python not found. Please install Python 3.8+")
        print("        Download: https://www.python.org/downloads/")
        return 1
    
    print(f"[INFO] Found Python: {python_path}")
    
    # Check version
    version_ok, version = check_python_version(python_path)
    if not version_ok:
        print(f"[ERROR] Python version {version} is too old. Python 3.8+ is required.")
        return 1
    
    # Create .env if needed
    if not create_env_if_needed():
        return 0
    
    # Install dependencies
    if not install_dependencies(python_path):
        return 1
    
    # Parse arguments
    args = sys.argv[1:]
    mode = args[0] if args else "select"
    
    if mode == "help":
        show_help()
        return 0
    
    # Run main.py with arguments
    cmd = [python_path, "main.py"]
    
    if mode == "select":
        cmd.append("--select")
    elif mode == "direct":
        cmd.append("--direct")
    elif mode == "catalog":
        cmd.append("--catalog")
        if len(args) > 1:
            cmd.extend(["--course-id", args[1]])
    elif mode == "test":
        cmd.append("--test")
        if len(args) > 1:
            cmd.extend(["--course-id", args[1]])
    elif mode == "clear-cache":
        cmd.append("--clear-cache")
    else:
        # Default to select mode
        cmd.append("--select")
    
    print(f"\n[MODE] {mode.capitalize()} Mode\n")
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
