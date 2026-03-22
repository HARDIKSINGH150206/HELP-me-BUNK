#!/usr/bin/env python3
"""
Startup validation script for HELP-me-BUNK
Checks environment, dependencies, and configuration before app start
"""

import os
import sys
import subprocess
from pathlib import Path

class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_status(status, message):
    """Print formatted status message"""
    if status == 'ok':
        symbol = f"{Colors.GREEN}✓{Colors.RESET}"
    elif status == 'warn':
        symbol = f"{Colors.YELLOW}⚠{Colors.RESET}"
    else:
        symbol = f"{Colors.RED}✗{Colors.RESET}"
    
    print(f"{symbol} {message}")

def check_python_version():
    """Check Python version >= 3.10"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print_status('ok', f"Python {version.major}.{version.minor}.{version.micro} ✓")
        return True
    else:
        print_status('error', f"Python 3.10+ required (found {version.major}.{version.minor})")
        return False

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print_status('ok', ".env file found")
        return True
    else:
        print_status('warn', ".env file not found - will use defaults/fallbacks")
        return False

def check_env_vars():
    """Check critical environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    critical = ['SECRET_KEY']
    optional = ['MONGODB_URI', 'ENCRYPTION_KEY', 'ERP_URL']
    issues = []
    
    for var in critical:
        if not os.getenv(var):
            issues.append(f"Missing critical: {var}")
            print_status('error', f"Missing critical env var: {var}")
        else:
            print_status('ok', f"Env var {var} is set")
    
    for var in optional:
        if not os.getenv(var):
            print_status('warn', f"Optional env var {var} not set (auto-fallback enabled)")
        else:
            print_status('ok', f"Env var {var} is set")
    
    return len(issues) == 0

def check_packages():
    """Check if required packages are installed"""
    packages = {
        'flask': 'flask',
        'selenium': 'selenium',
        'pymongo': 'pymongo',
        'python-dotenv': 'dotenv',
        'cryptography': 'cryptography',
        'APScheduler': 'apscheduler',
        'werkzeug': 'werkzeug'
    }
    
    missing = []
    for package_name, import_name in packages.items():
        try:
            __import__(import_name)
            print_status('ok', f"Package '{package_name}' installed")
        except ImportError:
            print_status('error', f"Package '{package_name}' missing")
            missing.append(package_name)
    
    if missing:
        print(f"\n{Colors.YELLOW}Install missing packages:{Colors.RESET}")
        print(f"  pip install {' '.join(missing)}")
        return False
    return True

def check_chrome():
    """Check if Chrome/Chromium is available"""
    try:
        subprocess.run(['which', 'chromium-browser'], 
                      capture_output=True, check=True)
        print_status('ok', "Chromium browser found")
        return True
    except:
        try:
            subprocess.run(['which', 'google-chrome'], 
                          capture_output=True, check=True)
            print_status('ok', "Chrome browser found")
            return True
        except:
            print_status('warn', "Chrome/Chromium not found (needed for ERP scraping)")
            return False

def check_directories():
    """Check if required directories exist"""
    dirs = ['.', 'templates', 'frontend']
    missing = False
    for d in dirs:
        if os.path.isdir(d):
            print_status('ok', f"Directory '{d}' exists")
        else:
            print_status('error', f"Directory '{d}' missing")
            missing = True
    return not missing

def check_database():
    """Check database connectivity"""
    from dotenv import load_dotenv
    load_dotenv()
    
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print_status('warn', "No MongoDB configured (using JSON fallback)")
        return True
    
    try:
        from pymongo import MongoClient
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print_status('ok', "MongoDB connection successful")
        return True
    except Exception as e:
        print_status('warn', f"MongoDB connection failed: {str(e)[:50]}... (JSON fallback)")
        return False

def main():
    """Run all checks"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== HELP-me-BUNK Startup Validation ==={Colors.RESET}\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Environment File", check_env_file),
        ("Environment Variables", check_env_vars),
        ("Required Packages", check_packages),
        ("Chrome/Chromium", check_chrome),
        ("Directories", check_directories),
        ("Database", check_database),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{Colors.BOLD}{name}:{Colors.RESET}")
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_status('error', f"Check failed: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{Colors.BOLD}=== Summary ==={Colors.RESET}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"{Colors.BOLD}Passed: {passed}/{total}{Colors.RESET}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}✓ All checks passed! Ready to start.{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.YELLOW}⚠ Some checks failed - see above for details{Colors.RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
