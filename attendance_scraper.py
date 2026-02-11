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
import subprocess
import sys

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
            print("Setting up ChromeDriver...")
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✓ Browser initialized")
        except Exception as e:
            print(f"⚠ Chromium failed, trying Google Chrome...")
            try:
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
            time.sleep(3)
            
            if "dashboard" in self.driver.current_url:
                print("✓ Already logged in!")
                return True
            
            wait = WebDriverWait(self.driver, 10)
            
            try:
                username_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[name*='user'], input[name*='email'], input[placeholder*='User'], input[placeholder*='Email']"))
                )
                password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                
                username_field.clear()
                username_field.send_keys(self.username)
                password_field.clear()
                password_field.send_keys(self.password)
                
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
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
            attendance_url = f"{self.erp_url}/attendance"
            self.driver.get(attendance_url)
            time.sleep(3)
            
            if "attendance" in self.driver.current_url.lower():
                print("✓ On attendance page")
                return True
            
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
        """Extract attendance data from Acharya ERP cards - improved accuracy"""
        attendance_data = []
        processed = set()
        
        try:
            print("Waiting for page to fully load...")
            time.sleep(5)
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Method 1: Look for card/container elements with attendance data
            print("Method 1: Searching for attendance cards...")
            
            # Common selectors for attendance cards in modern ERPs
            card_selectors = [
                ".attendance-card",
                "[class*='attendance'] [class*='card']",
                ".subject-card",
                ".course-card", 
                "[class*='subject'][class*='card']",
                ".MuiCard-root",  # Material UI cards
                "[class*='card'][class*='course']",
                ".card.mb-3",  # Bootstrap cards
                "[class*='attendance-item']",
                ".list-group-item",
            ]
            
            cards = []
            for selector in card_selectors:
                try:
                    found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if found:
                        cards.extend(found)
                        print(f"  Found {len(found)} elements with selector: {selector}")
                except:
                    pass
            
            # Remove duplicates by checking element IDs
            unique_cards = []
            seen_ids = set()
            for card in cards:
                card_id = card.id if card.id else id(card)
                if card_id not in seen_ids:
                    seen_ids.add(card_id)
                    unique_cards.append(card)
            
            # Process cards
            for card in unique_cards:
                try:
                    card_text = card.text
                    
                    # Look for attendance patterns in card
                    patterns = [
                        re.compile(r'(\d+)\s*of\s*(\d+)\s*classes?', re.IGNORECASE),
                        re.compile(r'(\d+)\s*/\s*(\d+)', re.IGNORECASE),
                        re.compile(r'Present[:\s]*(\d+).*?Total[:\s]*(\d+)', re.IGNORECASE | re.DOTALL),
                        re.compile(r'Attended[:\s]*(\d+).*?Total[:\s]*(\d+)', re.IGNORECASE | re.DOTALL),
                        re.compile(r'(\d+)\s*classes?\s*attended.*?(\d+)\s*total', re.IGNORECASE),
                    ]
                    
                    present, total = None, None
                    for pattern in patterns:
                        match = pattern.search(card_text)
                        if match:
                            present = int(match.group(1))
                            total = int(match.group(2))
                            break
                    
                    if present is not None and total is not None and total > 0:
                        # Find subject name - look for heading elements or first meaningful text
                        subject_name = None
                        
                        # Try to find heading elements within the card
                        heading_selectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                                            '[class*="title"]', '[class*="heading"]', 
                                            '[class*="subject"]', '[class*="course-name"]',
                                            '.card-title', '.card-header']
                        
                        for sel in heading_selectors:
                            try:
                                heading = card.find_element(By.CSS_SELECTOR, sel)
                                if heading and heading.text.strip():
                                    potential_name = heading.text.strip().split('\n')[0]
                                    # Validate it's a subject name
                                    skip_patterns = ['attendance', 'overview', 'semester', 'present', 
                                                    'total', 'absent', 'percentage', '%', 'view', 'track']
                                    if not any(skip.lower() in potential_name.lower() for skip in skip_patterns):
                                        subject_name = potential_name
                                        break
                            except:
                                pass
                        
                        # Fallback: get first meaningful line from card text
                        if not subject_name:
                            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                            for line in lines:
                                if len(line) > 5 and any(c.isalpha() for c in line):
                                    skip_patterns = ['attendance', 'present', 'absent', 'total', 
                                                    '%', 'of classes', 'classes', 'view', 'track']
                                    if not any(skip.lower() in line.lower() for skip in skip_patterns):
                                        subject_name = line
                                        break
                        
                        if subject_name and subject_name not in processed:
                            percentage = round((present / total) * 100, 2)
                            attendance_data.append({
                                'subject': subject_name,
                                'present': present,
                                'total': total,
                                'percentage': percentage
                            })
                            processed.add(subject_name)
                            print(f"  ✓ Found: {subject_name}: {present}/{total} ({percentage}%)")
                except Exception as e:
                    continue
            
            # Method 2: Look for tables with attendance data
            if not attendance_data:
                print("Method 2: Searching for attendance tables...")
                try:
                    tables = self.driver.find_elements(By.CSS_SELECTOR, "table")
                    for table in tables:
                        rows = table.find_elements(By.CSS_SELECTOR, "tr")
                        for row in rows:
                            row_text = row.text
                            
                            # Look for attendance pattern in row
                            match = re.search(r'(\d+)\s*(?:of|/)\s*(\d+)', row_text)
                            if match:
                                present = int(match.group(1))
                                total = int(match.group(2))
                                
                                if total > 0:
                                    # Get cells
                                    cells = row.find_elements(By.CSS_SELECTOR, "td, th")
                                    subject_name = None
                                    
                                    # First cell is usually subject name
                                    if cells:
                                        potential_name = cells[0].text.strip()
                                        if potential_name and len(potential_name) > 3:
                                            skip = ['sl', 'no', '#', 'subject', 'serial']
                                            if not any(s.lower() == potential_name.lower() for s in skip):
                                                subject_name = potential_name
                                    
                                    if subject_name and subject_name not in processed:
                                        percentage = round((present / total) * 100, 2)
                                        attendance_data.append({
                                            'subject': subject_name,
                                            'present': present,
                                            'total': total,
                                            'percentage': percentage
                                        })
                                        processed.add(subject_name)
                                        print(f"  ✓ Found: {subject_name}: {present}/{total} ({percentage}%)")
                except Exception as e:
                    print(f"  Table extraction error: {e}")
            
            # Method 3: Fallback to text-based extraction with improved logic
            if not attendance_data:
                print("Method 3: Fallback text-based extraction...")
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                lines = body_text.split('\n')
                
                attendance_pattern = re.compile(r'(\d+)\s*of\s*(\d+)\s*classes?', re.IGNORECASE)
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    match = attendance_pattern.search(line)
                    if match:
                        present = int(match.group(1))
                        total = int(match.group(2))
                        
                        if total > 0:
                            # Look backwards more carefully for subject name
                            subject_name = None
                            for j in range(i-1, max(0, i-5), -1):
                                prev_line = lines[j].strip()
                                if prev_line and len(prev_line) > 8:
                                    # More comprehensive skip list
                                    skip_patterns = [
                                        'attendance', 'overview', 'semester', 'present classes', 
                                        'total classes', 'view and track', 'dashboard', 'calendar',
                                        'my courses', 'mentorship', 'exam', 'fee payment', 'lms',
                                        'feedback', 'student', 'beta', 'acharya erp', 'toggle',
                                        'offline', 'present', 'records', 'absent', 'percentage',
                                        '%', 'of classes', 'classes attended', 'total', 'click',
                                        'view details', 'show more', 'see all'
                                    ]
                                    
                                    # Check if line is likely a subject name
                                    is_valid = True
                                    for skip in skip_patterns:
                                        if skip.lower() in prev_line.lower():
                                            is_valid = False
                                            break
                                    
                                    # Also check it's not just a number or percentage
                                    if is_valid and not re.match(r'^[\d.%\s]+$', prev_line):
                                        subject_name = prev_line
                                        break
                            
                            if subject_name and subject_name not in processed:
                                percentage = round((present / total) * 100, 2)
                                attendance_data.append({
                                    'subject': subject_name,
                                    'present': present,
                                    'total': total,
                                    'percentage': percentage
                                })
                                processed.add(subject_name)
                                print(f"  ✓ Found: {subject_name}: {present}/{total} ({percentage}%)")
            
            if attendance_data:
                # Sort by subject name for consistency
                attendance_data.sort(key=lambda x: x['subject'])
                print(f"\n✓ Successfully extracted {len(attendance_data)} subjects")
                return attendance_data
            
            print("\n⚠ No attendance data found automatically.")
            print("Please ensure you are on the attendance page with subject cards visible.")
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
    
    def verify_and_correct_data(self, data):
        """Allow user to verify and correct scraped data"""
        print("\n" + "="*70)
        print("DATA VERIFICATION")
        print("="*70)
        print("\nPlease verify the extracted data matches your ERP.")
        print("Compare each subject's Present/Total with your ERP attendance page.\n")
        
        for i, subject in enumerate(data):
            print(f"  [{i+1}] {subject['subject']}: {subject['present']}/{subject['total']} ({subject['percentage']}%)")
        
        print("\n" + "-"*70)
        print("Options:")
        print("  - Press ENTER if data is correct")
        print("  - Enter subject number to correct (e.g., '1' or '2')")
        print("  - Enter 'all' to manually enter all data")
        print("  - Enter 'skip' to skip without saving")
        print("-"*70)
        
        while True:
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == '':
                print("✓ Data verified as correct")
                return data
            
            if choice == 'skip':
                print("✗ Skipping data save")
                return None
            
            if choice == 'all':
                return self.manual_data_entry()
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(data):
                    subject = data[idx]
                    print(f"\nCorrecting: {subject['subject']}")
                    
                    new_name = input(f"  Subject name [{subject['subject']}]: ").strip()
                    if new_name:
                        subject['subject'] = new_name
                    
                    new_present = input(f"  Present classes [{subject['present']}]: ").strip()
                    if new_present:
                        subject['present'] = int(new_present)
                    
                    new_total = input(f"  Total classes [{subject['total']}]: ").strip()
                    if new_total:
                        subject['total'] = int(new_total)
                    
                    # Recalculate percentage
                    if subject['total'] > 0:
                        subject['percentage'] = round((subject['present'] / subject['total']) * 100, 2)
                    
                    print(f"  ✓ Updated: {subject['subject']}: {subject['present']}/{subject['total']} ({subject['percentage']}%)")
                    
                    # Show updated list
                    print("\nUpdated data:")
                    for i, s in enumerate(data):
                        print(f"  [{i+1}] {s['subject']}: {s['present']}/{s['total']} ({s['percentage']}%)")
                    
                    cont = input("\nMore corrections? (number/ENTER to finish): ").strip()
                    if not cont:
                        return data
                else:
                    print("Invalid number. Try again.")
            except ValueError:
                print("Invalid input. Enter a number, 'all', 'skip', or press ENTER.")
        
        return data
    
    def manual_data_entry(self):
        """Manually enter attendance data"""
        print("\n" + "="*70)
        print("MANUAL DATA ENTRY")
        print("="*70)
        print("Enter your attendance data manually.")
        print("For each subject, enter: Subject Name, Present, Total")
        print("Enter 'done' when finished.\n")
        
        data = []
        while True:
            name = input("Subject name (or 'done'): ").strip()
            if name.lower() == 'done':
                break
            
            try:
                present = int(input("  Present classes: ").strip())
                total = int(input("  Total classes: ").strip())
                
                if total > 0:
                    percentage = round((present / total) * 100, 2)
                    data.append({
                        'subject': name,
                        'present': present,
                        'total': total,
                        'percentage': percentage
                    })
                    print(f"  ✓ Added: {name}: {present}/{total} ({percentage}%)\n")
                else:
                    print("  ✗ Total must be greater than 0\n")
            except ValueError:
                print("  ✗ Please enter valid numbers\n")
        
        if data:
            print(f"\n✓ Manually entered {len(data)} subjects")
        return data if data else None
    
    def run_calculator(self):
        """Automatically run the calculator after scraping"""
        print("\n" + "="*70)
        print("RUNNING ATTENDANCE CALCULATOR...")
        print("="*70 + "\n")
        
        try:
            subprocess.run([sys.executable, 'attendance_calculator.py'])
        except Exception as e:
            print(f"✗ Could not run calculator: {e}")
            print("You can run it manually: python3 attendance_calculator.py")
    
    def run(self, auto_mode=False):
        """Main execution flow
        
        Args:
            auto_mode: If True, skip verification and save automatically (for web scraping)
        """
        filename = None
        verified_data = None
        
        try:
            self.setup_driver()
            
            if not self.login():
                print("\n✗ Login failed. Please check your credentials.")
                return None
            
            if not self.navigate_to_attendance():
                print("\n✗ Could not navigate to attendance page")
                return None
            
            print("\nExtracting attendance data...")
            data = self.extract_attendance_data()
            
            if data and len(data) > 0:
                if auto_mode:
                    # Auto mode: save without verification (for web interface)
                    verified_data = data
                else:
                    # Interactive mode: verify data with user
                    verified_data = self.verify_and_correct_data(data)
                
                if verified_data:
                    filename = self.save_data(verified_data)
                    
                    print("\n" + "="*70)
                    print("ATTENDANCE SUMMARY (VERIFIED)")
                    print("="*70)
                    for subject in verified_data:
                        status = "✓" if subject['percentage'] >= 75 else "✗"
                        print(f"{status} {subject['subject']}: {subject['present']}/{subject['total']} ({subject['percentage']}%)")
                    print("="*70)
                else:
                    print("\n✗ Data not saved")
                    return None
            else:
                # No auto-extracted data, offer manual entry
                if not auto_mode:
                    print("\n⚠ Automatic extraction failed.")
                    manual = input("Would you like to enter data manually? (y/n): ").strip().lower()
                    if manual == 'y':
                        verified_data = self.manual_data_entry()
                        if verified_data:
                            filename = self.save_data(verified_data)
                else:
                    print("\n✗ Could not extract attendance data")
                    return None
                
        except Exception as e:
            print(f"\n✗ Error occurred: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            if self.driver:
                print("\nClosing browser...")
                self.driver.quit()
                print("✓ Browser closed\n")
        
        if filename and verified_data and not auto_mode:
            self.run_calculator()
        
        return filename


if __name__ == "__main__":
    print("="*70)
    print("ACHARYA ERP ATTENDANCE SCRAPER")
    print("="*70)
    print()
    
    username = input("Enter your username/roll number: ").strip()
    password = input("Enter your password: ").strip()
    
    if not username or not password:
        print("\n✗ Username and password are required!")
        exit(1)
    
    print()
    scraper = AcharyaERPScraper(username, password)
    scraper.run()
