#!/usr/bin/env python3
"""
Diagnostic tool to test scraper login with your credentials

Usage:
    python test_scraper_login.py <username> <password>

This script tests both v1 (Selenium) and v2 (HTTP API) scrapers
to identify which API endpoints are working.
"""

import asyncio
import sys
from attendance_scraper import AcharyaERPScraper
from attendance_scraper_v2 import AcharyaScraper

async def test_v2(username: str, password: str):
    """Test v2 HTTP API scraper"""
    print(f"\n{'='*60}")
    print(f"Testing v2 (HTTP API Scraper)")
    print(f"{'='*60}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print()
    
    try:
        async with AcharyaScraper(username, password) as scraper:
            print("Attempting login...")
            result = await scraper.login()
            
            if result:
                print(f"\n✓ LOGIN SUCCESSFUL")
                print(f"  Logged in: {scraper.logged_in}")
                print(f"  Session expired: {scraper.session_expired}")
                print(f"  Auth token: {scraper.auth_token[:30] if scraper.auth_token else 'None'}...")
                print(f"  Student ID: {scraper.student_id}")
                return True
            else:
                print(f"\n✗ LOGIN FAILED")
                print(f"  The HTTP API endpoints need to be debugged")
                print(f"  See DevTools Network tab for correct endpoints")
                return False
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_v1(username: str, password: str):
    """Test v1 Selenium scraper"""
    print(f"\n{'='*60}")
    print(f"Testing v1 (Selenium Scraper)")
    print(f"{'='*60}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print()
    
    scraper = None
    try:
        scraper = AcharyaERPScraper(username, password)
        
        print("Setting up WebDriver...")
        scraper.setup_driver()
        
        print("Attempting login...")
        result = scraper.login()
        
        if result:
            print(f"\n✓ LOGIN SUCCESSFUL")
            print(f"  Browser automation working")
            print(f"  Can now navigate to attendance page")
            return True
        else:
            print(f"\n✗ LOGIN FAILED")
            print(f"  - Credentials may be incorrect")
            print(f"  - Server may be down")
            print(f"  - Login validation may have changed")
            return False
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if scraper and scraper.driver:
            try:
                scraper.driver.quit()
            except:
                pass

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_scraper_login.py <username> <password>")
        print()
        print("Example:")
        print("  python test_scraper_login.py john_doe MyPassword123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    print(f"\nTesting scrapers with credentials for: {username}")
    
    # Test v1 first (proven to work)
    v1_result = test_v1(username, password)
    
    # Test v2 (may not have correct API endpoints)
    v2_result = asyncio.run(test_v2(username, password))
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"v1 (Selenium):     {'✓ WORKING' if v1_result else '✗ FAILED'}")
    print(f"v2 (HTTP API):     {'✓ WORKING' if v2_result else '✗ FAILED (needs API endpoint debugging)'}")
    
    if v1_result:
        print(f"\n✓ Your credentials are correct!")
        print(f"✓ v1 Selenium scraper is working")
        print(f"  (v2 will be used as fallback when API endpoints are verified)")
    else:
        print(f"\n✗ Login failed with both scrapers")
        print(f"✗ Check if:")
        print(f"   - Credentials are correct")
        print(f"   - Server is accessible")
        print(f"   - No account lockout or 2FA enabled")

if __name__ == '__main__':
    main()
