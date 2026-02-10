#!/usr/bin/env python3
"""
Acharya ERP Attendance Scraper
Custom scraper for student.acharyaerptech.in
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import json
from datetime import datetime
import re

class AcharyaERPScraper:
    def __init__(self, username, password):
        """Initialize scraper with credentials"""
        self.erp_url = "https://student.acharyaerptech.in"
        self.username = username
        self.password = password
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome driver"""
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        try:
            # Try using webdriver-manager with chromium
            print("Setting up ChromeDriver...")
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✓ Browser initialized")
        except Exception as e:
            print(f"⚠ Chromium failed, trying Google Chrome...")
            try:
                # Fallback to regular Chrome
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                print("✓ Browser initialized")
            except Exception as e2:
                print(f"✗ All methods failed: {e2}")
                raise
        
    def login(self):
        """Login to Acharya ERP"""
        try:
            self.driver.get(self.erp_url)
            print(f"✓ Navigated to {self.erp_url}")
            
            # Wait for page to load
            time.sleep(3)
            
            # Check if already logged in
            if "dashboard" in self.driver.current_url:
                print("✓ Already logged in!")
                return True
            
            # Find login fields
            wait = WebDriverWait(self.driver, 10)
            
            try:
                # Try finding by input type
                username_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[name*='user'], input[name*='email'], input[placeholder*='User'], input[placeholder*='Email']"))
                )
                password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                
                username_field.clear()
                username_field.send_keys(self.username)
                password_field.clear()
                password_field.send_keys(self.password)
                
                # Find login button
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
                # Wait for dashboard
                time.sleep(5)
                
                if "dashboard" in self.driver.current_url:
                    print("✓ Logged in successfully")
                    return True
                else:
                    print("✗ Login may have failed - not on dashboard")
                    return False
                    
            except Exception as e:
                print(f"✗ Could not find login fields: {e}")
                print("\nPlease log in manually. You have 30 seconds...")
                time.sleep(30)
                
                if "dashboard" in self.driver.current_url:
                    print("✓ Manual login successful")
                    return True
                else:
                    return False
                
        except Exception as e:
            print(f"✗ Login failed: {e}")
            return False
    
    def navigate_to_attendance(self):
        """Navigate to attendance page"""
        try:
            # Try direct URL first
            attendance_url = f"{self.erp_url}/attendance"
            self.driver.get(attendance_url)
            time.sleep(3)
            
            # Check if we're on attendance page
            if "attendance" in self.driver.current_url.lower():
                print("✓ On attendance page")
                return True
            
            # Otherwise try to find attendance link
            try:
                attendance_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Attendance")
                attendance_link.click()
                time.sleep(3)
                print("✓ Navigated to attendance page")
                return True
            except:
                print("⚠ Couldn't auto-navigate. Please click on Attendance manually.")
                print("You have 15 seconds...")
                time.sleep(15)
                return True
                
        except Exception as e:
            print(f"✗ Navigation failed: {e}")
            return False
    
    def extract_attendance_data(self):
        """Extract attendance data from Acharya ERP cards"""
        attendance_data = []
        
        try:
            # Wait for content to load
            print("Waiting for page to fully load...")
            time.sleep(5)
            
            # Scroll down to ensure all content is loaded
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Pattern: "XofYclasses" (no spaces in Acharya ERP)
            attendance_pattern = re.compile(r'(\d+)\s*of\s*(\d+)\s*classes', re.IGNORECASE)
            processed = set()
            
            # Method 1: Get all visible text and parse it
            print("Extracting from page text...")
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Split into lines and process
            lines = body_text.split('\n')
            current_subject = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check if this line has "XofYclasses" pattern
                match = attendance_pattern.search(line)
                if match:
                    present = int(match.group(1))
                    total = int(match.group(2))
                    
                    # Look back for subject name (should be 2-3 lines before)
                    # Pattern is: Subject Name -> Code -> XofYclasses
                    subject_name = None
                    for j in range(max(0, i-3), i):
                        prev_line = lines[j].strip()
                        if prev_line and len(prev_line) > 10 and any(c.isalpha() for c in prev_line):
                            # Skip UI elements
                            skip_patterns = ['Attendance', 'Overview', 'Semester', 'Present Classes', 
                                            'Total Classes', 'View and track', 'Dashboard', 'Calendar',
                                        'My Courses', 'Mentorship', 'Exam', 'Fee Payment', 'LMS',
                                            'Feedback', 'Student', 'Beta', 'Acharya ERP', 'Toggle',
                                            'Offline', 'Present', 'Records']
                            if not any(skip in prev_line for skip in skip_patterns) and '%' not in prev_line:
                                subject_name = prev_line
                                break
                    
                    if subject_name and subject_name not in processed:
                        percentage = round((present / total) * 100, 2) if total > 0 else 0
                        attendance_data.append({
                            'subject': subject_name,
                            'present': present,
                            'total': total,
                            'percentage': percentage
                        })
                        processed.add(subject_name)
                        print(f"  ✓ Found: {subject_name}: {present}/{total} ({percentage}%)")
            
            # If text parsing worked, return results
            if attendance_data:
                print(f"\n✓ Successfully extracted {len(attendance_data)} subjects")
                return attendance_data
            
            # Method 2: Debug output if nothing found
            print("\n⚠ No attendance data found automatically.")
            print("Page text sample for debugging:")
            print("-" * 40)
            print(body_text[:1000])
            print("-" * 40)
            
            print("\nTaking screenshot for debugging...")
            self.driver.save_screenshot("attendance_page_debug.png")
            print("Screenshot saved as 'attendance_page_debug.png'")
            return None
            
        except Exception as e:
            print(f"✗ Data extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_data(self, data):
        """Save attendance data to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"attendance_{timestamp}.json"
        
        output_data = {
            'timestamp': timestamp,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'source': 'Acharya ERP',
            'data': data
        }
        
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✓ Data saved to {filename}")
        return filename
    
    def run(self):
        """Main execution flow"""
        try:
            self.setup_driver()
            
            if not self.login():
                print("\n✗ Login failed. Please check your credentials.")
                return
            
            if not self.navigate_to_attendance():
                print("\n✗ Could not navigate to attendance page")
                return
            
            print("\nExtracting attendance data...")
            data = self.extract_attendance_data()
            
            if data and len(data) > 0:
                filename = self.save_data(data)
                
                print("\n" + "="*70)
                print("ATTENDANCE SUMMARY")
                print("="*70)
                for subject in data:
                    status = "✓" if subject['percentage'] >= 75 else "✗"
                    print(f"{status} {subject['subject']}: {subject['present']}/{subject['total']} ({subject['percentage']}%)")
                
                print("\n" + "="*70)
                print(f"Next step: Run the calculator!")
                print(f"Command: python3 attendance_calculator.py")
                print("="*70)
            else:
                print("\n✗ Could not extract attendance data")
                
        except Exception as e:
            print(f"\n✗ Error occurred: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if self.driver:
                print("\nPress Enter to close browser...")
                input()
                self.driver.quit()
                print("✓ Browser closed")


if __name__ == "__main__":
    print("="*70)
    print("ACHARYA ERP ATTENDANCE SCRAPER")
    print("="*70)
    print()
    
    # Get credentials
    username = input("Enter your username/roll number: ").strip()
    password = input("Enter your password: ").strip()
    
    if not username or not password:
        print("\n✗ Username and password are required!")
        exit(1)
    
    print()
    scraper = AcharyaERPScraper(username, password)
    scraper.run()