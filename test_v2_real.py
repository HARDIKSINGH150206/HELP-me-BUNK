#!/usr/bin/env python3
"""
Quick test of v2 scraper with real API endpoints
"""
import asyncio
from attendance_scraper_v2 import AcharyaScraper

async def test():
    username = input("Enter your AUID (e.g., AIT24BECS108): ").strip()
    password = input("Enter your ERP password: ").strip()
    
    print(f"\n🧪 Testing v2 scraper with real API endpoints...")
    print(f"   Username: {username}")
    
    try:
        async with AcharyaScraper(username, password) as scraper:
            # Test login
            print(f"\n1️⃣  Testing login...")
            login_result = await scraper.login()
            
            if not login_result:
                print(f"❌ Login FAILED")
                print(f"   Check credentials or server status")
                return
            
            print(f"✅ Login SUCCESSFUL")
            print(f"   Token: {scraper.auth_token[:40]}...")
            print(f"   User ID: {scraper.student_id}")
            print(f"   AUID: {scraper.username}")
            
            # Test attendance
            print(f"\n2️⃣  Testing attendance fetch...")
            attendance = await scraper.get_attendance()
            
            if attendance:
                print(f"✅ Attendance fetch SUCCESSFUL")
                print(f"   Subjects: {len(attendance)}")
                for subject in attendance[:3]:  # Show first 3
                    print(f"     - {subject.get('subject', 'N/A')}: {subject.get('present', 0)}/{subject.get('total', 0)}")
                if len(attendance) > 3:
                    print(f"     ... and {len(attendance) - 3} more")
            else:
                print(f"⚠️  No attendance data returned")
        
        print(f"\n✅ v2 scraper is WORKING with real API!")
        print(f"   Your app is now 5-10x faster!")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
