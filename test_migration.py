#!/usr/bin/env python3
"""Quick test of migration to v2 scraper"""

import sys
print("Testing migration to v2 scraper...")

try:
    from attendance_scraper_v2 import AcharyaScraper
    print("✓ AcharyaScraper v2 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

try:
    scraper = AcharyaScraper('test_user', 'test_pass')
    print("✓ Scraper instance created")
except Exception as e:
    print(f"✗ Failed to create instance: {e}")
    sys.exit(1)

try:
    from app import run_scraper_background
    print("✓ run_scraper_background imported from app.py")
except ImportError as e:
    print(f"✗ Failed to import run_scraper_background: {e}")
    sys.exit(1)

print("\n✓ All migration tests passed!")
print("✓ App is ready to use the faster HTTP API scraper (v2)")
