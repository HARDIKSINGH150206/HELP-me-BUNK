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
    
    def is_valid_subject_name(self, name):
        """
        Validate if a string is a valid subject name.
        Rejects attendance data formats, course codes, and invalid patterns.
        """
        if not name or len(name.strip()) < 3:
            return False
        
        name = name.strip()
        
        # Reject if it's mostly numbers/special chars (e.g., "123/456", "2of5")
        alpha_count = sum(1 for c in name if c.isalpha())
        if alpha_count < len(name) * 0.3:  # Less than 30% alphabetic
            return False
        
        # Reject specific patterns that match attendance data
        bad_patterns = [
            r'\d+\s*of\s*\d+',             # "2 of 5", "2of5", "2of6classes"
            r'^\d+\s*[/]\s*\d+',            # "2/5", "2 / 5"
            r'^\d+\s*classes',              # "2 classes", "2classes"
            r'^\d+\.?\d*\s*%',              # "0.0%", "75%", "42.86%"
            r'^[A-Z]{1,5}\d{3,4}[A-Z]?$',  # Course codes: BCS401, BCSL404, BBOC407, BCS405A, BCS456C
            r'^[A-Z]{2,6}\d{2,4}$',         # More course codes: UH408, etc.
        ]
        
        for pattern in bad_patterns:
            if re.search(pattern, name.strip(), re.IGNORECASE):
                return False
        
        # Must NOT be a pure course-code-like string (all caps + digits)
        if re.match(r'^[A-Z0-9]+$', name) and any(c.isdigit() for c in name):
            return False
        
        # Reject short all-caps abbreviations (e.g., UHV, ADA, DBMS, DMS, ADAL)
        # Real subject names are multi-word or longer; these are just short codes
        if re.match(r'^[A-Z]{2,6}$', name):
            return False
        
        # Skip keywords that indicate UI elements, not subjects
        skip_keywords = [
            'attendance', 'present', 'absent', 'total', 'view', 'track', 
            'urgent', 'danger', 'overview', 'semester', 'dashboard',
            'calendar', 'mentorship', 'exam', 'fee payment', 'lms',
            'feedback', 'beta', 'acharya erp', 'toggle', 'offline',
            'records', 'percentage', 'click', 'show more', 'see all',
            'view details', 'my courses', 'classes attended',
        ]
        if any(kw in name.lower() for kw in skip_keywords):
            return False
        
        return True
        
    def setup_driver(self):
        """Setup Chrome driver"""
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # Required for server/deployment
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--remote-debugging-port=9222')
        
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
        """Navigate to a page with attendance data.
        
        The Acharya ERP dashboard already shows attendance cards after login.
        We first check if the dashboard has attendance data visible.
        If not, we try the /attendance page with proper wait for SPA rendering.
        """
        try:
            # Strategy 1: Check if dashboard already has attendance data
            # (After login, we're already on the dashboard)
            current_url = self.driver.current_url
            print(f"  Current URL: {current_url}")
            
            if "dashboard" in current_url.lower():
                print("  Already on dashboard, checking for attendance data...")
                # Wait for attendance cards to render on dashboard
                try:
                    WebDriverWait(self.driver, 15).until(
                        lambda d: re.search(
                            r'\d+\s*of\s*\d+\s*class',
                            d.find_element(By.TAG_NAME, "body").text, re.IGNORECASE
                        )
                    )
                    print("✓ Dashboard has attendance data - staying here")
                    return True
                except Exception as e:
                    print(f"  Dashboard doesn't have attendance data yet: {e}")
            
            # Strategy 2: Navigate to /attendance and wait for SPA to render
            print("  Trying /attendance page...")
            attendance_url = f"{self.erp_url}/attendance"
            self.driver.get(attendance_url)
            
            # Wait up to 30 seconds for the SPA to render attendance content
            try:
                WebDriverWait(self.driver, 30).until(
                    lambda d: re.search(
                        r'\d+\s*of\s*\d+\s*class',
                        d.find_element(By.TAG_NAME, "body").text, re.IGNORECASE
                    )
                )
                print("✓ Attendance page loaded with data")
                return True
            except:
                print("  /attendance SPA didn't render content in time")
            
            # Strategy 3: Go back to dashboard and try harder
            print("  Going back to dashboard...")
            self.driver.get(f"{self.erp_url}/dashboard")
            time.sleep(5)
            
            # Scroll to trigger any lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if 'classes' in body_text.lower():
                print("✓ Dashboard has attendance data after scrolling")
                return True
            
            # Strategy 4: Try clicking Attendance link in sidebar/nav
            try:
                attendance_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Attendance")
                attendance_link.click()
                time.sleep(5)
                print("✓ Navigated via Attendance link")
                return True
            except:
                pass
            
            print("⚠ Could not find attendance data on any page, proceeding anyway...")
            return True
                
        except Exception as e:
            print(f"✗ Navigation failed: {e}")
            return False
    
    def navigate_to_calendar(self):
        """Navigate to calendar/timetable page"""
        try:
            calendar_url = f"{self.erp_url}/calendar"
            self.driver.get(calendar_url)
            time.sleep(5)
            
            if "calendar" in self.driver.current_url.lower():
                print("✓ On calendar page")
                return True
            
            try:
                calendar_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Calendar")
                calendar_link.click()
                time.sleep(5)
                print("✓ Navigated to calendar page")
                return True
            except:
                try:
                    timetable_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Timetable")
                    timetable_link.click()
                    time.sleep(5)
                    print("✓ Navigated to timetable page")
                    return True
                except:
                    print("⚠ Couldn't auto-navigate to calendar.")
                    return False
                
        except Exception as e:
            print(f"✗ Calendar navigation failed: {e}")
            return False
    
    def extract_timetable_data(self):
        """Extract weekly timetable from Acharya ERP calendar page.
        
        The ERP calendar is a 7-column grid (Sun-Sat) with events inside
        each date cell. Events use color-coded CSS classes:
          - chart-7: Lectures
          - chart-9: Labs
          - chart-10: Holidays/special days
        
        Event text format: "Lecture - Subject Name" or "Lab - Subject Name"
        Attendance: P (present) or A (absent) badges
        
        We extract all events, map dates to day-of-week, and build a
        recurring weekly schedule by finding the most common pattern.
        
        Returns a list of timetable entries with:
          subject, event_type (Lecture/Lab/Holiday), day (0=Mon..6=Sun),
          color_class, attendance records, and order within the day.
        """
        from datetime import datetime as dt
        from collections import defaultdict
        
        timetable = []
        
        try:
            print("Extracting timetable from calendar...")
            time.sleep(3)
            
            # Click "Show more" / expand hidden events first
            try:
                more_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'more...') or contains(text(), '+')]")
                for btn in more_buttons:
                    try:
                        if btn.is_displayed() and ('more' in btn.text.lower() or btn.text.strip().startswith('+')):
                            btn.click()
                            time.sleep(1)
                    except:
                        continue
            except:
                pass
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Save debug HTML
            try:
                with open('last_scrape_debug.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
            except:
                pass
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            try:
                with open('last_scrape_text.txt', 'w', encoding='utf-8') as f:
                    f.write(body_text)
            except:
                pass
            
            # ==========================================
            # Determine current month/year from page
            # ==========================================
            month_year = None
            try:
                # Look for "March 2026" type text
                month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', body_text)
                if month_match:
                    month_name = month_match.group(1)
                    year = int(month_match.group(2))
                    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                                   'July', 'August', 'September', 'October', 'November', 'December']
                    month_num = month_names.index(month_name) + 1
                    month_year = (year, month_num)
                    print(f"  Calendar month: {month_name} {year}")
            except:
                pass
            
            if not month_year:
                now = dt.now()
                month_year = (now.year, now.month)
                print(f"  Using current month: {month_year}")
            
            # ==========================================
            # Parse the calendar grid using Selenium
            # ==========================================
            # The grid is: div.grid.grid-cols-7 containing day cells
            # Header row: Sun, Mon, Tue, Wed, Thu, Fri, Sat
            # ERP uses Sun=0 column layout
            
            # Find all day cells in the calendar grid
            # Each cell has a date number span and event buttons
            day_cells = self.driver.find_elements(By.CSS_SELECTOR, "div.grid.grid-cols-7 > div")
            
            if not day_cells:
                # Fallback: try broader selector
                day_cells = self.driver.find_elements(By.CSS_SELECTOR, "[class*='grid-cols-7'] > div")
            
            print(f"  Found {len(day_cells)} grid cells")
            
            # Skip header row (first 7 cells are Sun/Mon/Tue/Wed/Thu/Fri/Sat)
            # Identify header cells by looking for day name text
            header_count = 0
            for cell in day_cells[:14]:
                txt = cell.text.strip().lower()
                if txt in ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']:
                    header_count += 1
            
            if header_count >= 5:
                # First 7 are headers
                data_cells = day_cells[7:]
            else:
                data_cells = day_cells
            
            # Parse each date cell
            # Column index: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
            # We convert to: 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
            
            erp_to_our_day = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}  # Sun→6, Mon→0, etc.
            
            # Track events per day-of-week for building weekly pattern
            weekly_events = defaultdict(list)  # day_num -> list of (order, event_info)
            all_events = []
            
            for cell_idx, cell in enumerate(data_cells):
                col = cell_idx % 7  # 0=Sun column
                our_day = erp_to_our_day[col]
                
                try:
                    # Get date number from the cell
                    date_spans = cell.find_elements(By.CSS_SELECTOR, "span")
                    date_num = None
                    for span in date_spans[:3]:
                        txt = span.text.strip()
                        if txt.isdigit() and 1 <= int(txt) <= 31:
                            # Check if this is a dimmed/opacity date (prev/next month)
                            span_classes = span.get_attribute("class") or ""
                            parent_classes = cell.get_attribute("class") or ""
                            if "opacity-20" in span_classes or "opacity-50" in parent_classes:
                                date_num = None  # Skip dates from other months
                            else:
                                date_num = int(txt)
                            break
                    
                    if date_num is None:
                        continue
                    
                    # Find all event buttons in this cell
                    event_buttons = cell.find_elements(By.CSS_SELECTOR, "[role='button'], [data-slot='dialog-trigger']")
                    
                    for order, btn in enumerate(event_buttons):
                        try:
                            btn_classes = btn.get_attribute("class") or ""
                            btn_text = btn.text.strip()
                            
                            if not btn_text or len(btn_text) < 3:
                                continue
                            
                            # Extract event text from span.font-semibold
                            event_spans = btn.find_elements(By.CSS_SELECTOR, "span.font-semibold")
                            event_text = ""
                            for es in event_spans:
                                t = es.text.strip()
                                if t and len(t) > 2:
                                    event_text = t
                                    break
                            
                            if not event_text:
                                event_text = btn_text.split('\n')[0].strip()
                            
                            # Determine color class
                            color_class = 'chart-7'  # default (lecture)
                            if 'chart-9' in btn_classes:
                                color_class = 'chart-9'  # lab
                            elif 'chart-10' in btn_classes:
                                color_class = 'chart-10'  # holiday
                            elif 'chart-8' in btn_classes:
                                color_class = 'chart-8'
                            
                            # Determine event type and subject name
                            event_type = 'Lecture'
                            subject = event_text
                            
                            if event_text.startswith('Lecture - '):
                                event_type = 'Lecture'
                                subject = event_text[len('Lecture - '):].strip()
                            elif event_text.startswith('Lab - '):
                                event_type = 'Lab'
                                subject = event_text[len('Lab - '):].strip()
                            elif 'Holiday' in event_text or 'DH' in event_text:
                                event_type = 'Holiday'
                                subject = event_text
                            elif event_text.startswith('Tutorial - '):
                                event_type = 'Tutorial'
                                subject = event_text[len('Tutorial - '):].strip()
                            
                            # Check attendance status (P/A badge)
                            attendance_status = None
                            try:
                                success_badge = btn.find_elements(By.CSS_SELECTOR, ".bg-success\\/20 span, [class*='text-success']")
                                destruct_badge = btn.find_elements(By.CSS_SELECTOR, ".bg-destructive\\/20 span, [class*='text-destructive']")
                                if success_badge:
                                    attendance_status = 'P'
                                elif destruct_badge:
                                    attendance_status = 'A'
                            except:
                                # Fallback: check text
                                if btn_text.endswith(' P') or '\nP' in btn_text:
                                    attendance_status = 'P'
                                elif btn_text.endswith(' A') or '\nA' in btn_text:
                                    attendance_status = 'A'
                            
                            event_info = {
                                'subject': subject,
                                'event_type': event_type,
                                'color_class': color_class,
                                'date': date_num,
                                'day': our_day,
                                'order': order,
                                'attendance': attendance_status,
                                'raw_text': event_text
                            }
                            
                            all_events.append(event_info)
                            
                            # Add to weekly pattern (skip holidays)
                            if event_type != 'Holiday':
                                weekly_events[our_day].append(event_info)
                            
                        except Exception as e:
                            continue
                
                except Exception as e:
                    continue
            
            print(f"  Extracted {len(all_events)} total calendar events")
            
            # ==========================================
            # Build recurring weekly schedule
            # ==========================================
            # For each day of week, find the most common set of classes
            # (to handle weeks where some classes are cancelled due to holidays)
            
            from collections import Counter
            
            weekly_schedule = {}
            
            for day_num in range(7):
                day_events = weekly_events.get(day_num, [])
                if not day_events:
                    continue
                
                # Group events by date to see what classes happen per day
                by_date = defaultdict(list)
                for ev in day_events:
                    key = f"{ev['event_type']} - {ev['subject']}"
                    by_date[ev['date']].append(ev)
                
                # Find the most populated date (most classes = normal schedule)
                best_date = max(by_date.keys(), key=lambda d: len(by_date[d]))
                schedule_for_day = by_date[best_date]
                
                # Sort by order (position on the page = time order)
                schedule_for_day.sort(key=lambda x: x['order'])
                
                weekly_schedule[day_num] = schedule_for_day
            
            # Build final timetable entries
            for day_num in sorted(weekly_schedule.keys()):
                events_for_day = weekly_schedule[day_num]
                for order, ev in enumerate(events_for_day):
                    timetable.append({
                        'subject': ev['subject'],
                        'event_type': ev['event_type'],
                        'day': day_num,
                        'order': order,
                        'color_class': ev['color_class'],
                        'start_time': None,  # ERP calendar doesn't show times
                        'end_time': None,
                        'raw_text': ev['raw_text']
                    })
            
            print(f"\n✓ Built weekly schedule with {len(timetable)} recurring classes:")
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            for entry in timetable:
                day_name = day_names[entry['day']] if entry['day'] < 7 else '?'
                print(f"  {day_name} #{entry['order']+1}: [{entry['event_type']}] {entry['subject']}")
            
            return timetable
            
        except Exception as e:
            print(f"✗ Timetable extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_attendance_data(self):
        """Extract attendance data from Acharya ERP attendance page.
        
        The Acharya ERP dashboard shows attendance in card format:
            SubjectName
            CourseCode (e.g. BCS401)
            ShortName (e.g. ADA)
            X          <-- present count (separate line)
            of         <-- separate line  
            Y          <-- total count (separate line)
            classes    <-- separate line
            Z%         <-- percentage
        
        There is also a "Show more (N more)" button that hides some subjects.
        
        Returns dict with 'subjects' list and 'overall' attendance.
        """
        attendance_data = []
        processed = set()
        overall_attendance = None
        
        try:
            print("Waiting for page to fully load...")
            # Wait for attendance content to be present (up to 20s)
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda d: re.search(
                        r'\d+\s*of\s*\d+\s*class',
                        d.find_element(By.TAG_NAME, "body").text, re.IGNORECASE
                    )
                )
                print("  ✓ Attendance content detected on page")
            except:
                print("  ⚠ Timed out waiting for attendance content, proceeding anyway...")
            
            time.sleep(2)
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # ==========================================
            # Click "Show more" to reveal all subjects
            # ==========================================
            print("Looking for 'Show more' button...")
            try:
                show_more_selectors = [
                    "//button[contains(text(), 'Show more')]",
                    "//a[contains(text(), 'Show more')]",
                    "//span[contains(text(), 'Show more')]",
                    "//*[contains(text(), 'Show more')]",
                    "//button[contains(text(), 'show more')]",
                    "//button[contains(text(), 'View All')]",
                    "//a[contains(text(), 'View All')]",
                    "//*[contains(text(), 'See all')]",
                ]
                clicked = False
                for xpath in show_more_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        for elem in elements:
                            if elem.is_displayed():
                                elem.click()
                                clicked = True
                                print(f"  ✓ Clicked 'Show more' button")
                                time.sleep(3)
                                break
                        if clicked:
                            break
                    except:
                        continue
                
                if not clicked:
                    # Try CSS selectors too
                    css_selectors = [
                        "[class*='show-more']",
                        "[class*='showMore']",
                        "[class*='view-all']",
                        "[class*='viewAll']",
                        "button.MuiButton-root",
                    ]
                    for sel in css_selectors:
                        try:
                            buttons = self.driver.find_elements(By.CSS_SELECTOR, sel)
                            for btn in buttons:
                                btn_text = btn.text.strip().lower()
                                if 'show more' in btn_text or 'view all' in btn_text or 'see all' in btn_text:
                                    btn.click()
                                    clicked = True
                                    print(f"  ✓ Clicked expand button: '{btn.text.strip()}'")
                                    time.sleep(3)
                                    break
                            if clicked:
                                break
                        except:
                            continue
                
                if not clicked:
                    print("  ⚠ No 'Show more' button found (may not exist or all subjects visible)")
            except Exception as e:
                print(f"  ⚠ Show more handling: {e}")
            
            # Scroll again after expanding
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # ==========================================
            # Save debug files
            # ==========================================
            try:
                page_source = self.driver.page_source
                with open('last_scrape_debug.html', 'w', encoding='utf-8') as f:
                    f.write(page_source)
                print("  ✓ Saved page source to last_scrape_debug.html")
            except:
                page_source = ""
            
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            try:
                with open('last_scrape_text.txt', 'w', encoding='utf-8') as f:
                    f.write(body_text)
                print("  ✓ Saved page text to last_scrape_text.txt")
            except:
                pass
            
            # ==========================================
            # Extract overall attendance
            # ==========================================
            print("\nLooking for overall attendance...")
            overall_match = re.search(
                r'Overall\s+Attendance\s*\n\s*(\d+(?:\.\d+)?)\s*%',
                body_text, re.IGNORECASE
            )
            if overall_match:
                pct = float(overall_match.group(1))
                overall_attendance = {'present': None, 'total': None, 'percentage': pct}
                print(f"  ✓ Overall attendance: {pct}%")
            else:
                # Fallback patterns
                for pat in [
                    re.compile(r'overall[:\s]*(\d+(?:\.\d+)?)\s*%', re.IGNORECASE),
                    re.compile(r'overall\s*(?:attendance)?[:\s]*(\d+)\s*[/of]\s*(\d+)', re.IGNORECASE),
                ]:
                    m = pat.search(body_text)
                    if m:
                        groups = m.groups()
                        if len(groups) == 1:
                            overall_attendance = {'present': None, 'total': None, 'percentage': float(groups[0])}
                        elif len(groups) == 2:
                            p, t = int(groups[0]), int(groups[1])
                            overall_attendance = {'present': p, 'total': t, 'percentage': round(p/t*100, 2) if t > 0 else 0}
                        print(f"  ✓ Overall attendance found")
                        break
            
            # ==========================================
            # Parse attendance using Acharya ERP format
            # ==========================================
            # The ERP renders each subject as separate lines:
            #   SubjectName
            #   CourseCode
            #   ShortCode
            #   X
            #   of
            #   Y
            #   classes
            #   Z%
            # We look for the pattern: <number> \n of \n <number> \n classes
            
            print("\nExtracting subject attendance...")
            lines = body_text.split('\n')
            lines = [l.strip() for l in lines]
            
            # Find all attendance blocks by looking for various patterns:
            # Format 1 (multiline): lines[i]=number, lines[i+1]="of", lines[i+2]=number, lines[i+3]="classes"  
            # Format 2 (spaced): "3 of 5 classes"
            # Format 3 (joined): "3of5classes" or "1of2classes" (Acharya /attendance page)
            i = 0
            while i < len(lines):
                present, total = None, None
                skip_count = 1  # How many lines to skip after match
                
                # Format 1: Multiline  X / of / Y / classes
                if (i < len(lines) - 3 and
                    lines[i].isdigit() and 
                    lines[i+1].lower() == 'of' and 
                    lines[i+2].isdigit() and 
                    lines[i+3].lower().startswith('class')):
                    present = int(lines[i])
                    total = int(lines[i+2])
                    skip_count = 4
                
                # Format 2 & 3: Single-line with optional spaces
                # Matches: "3 of 5 classes", "3of5classes", "3 of5 classes", etc.
                if present is None:
                    match = re.match(r'^(\d+)\s*of\s*(\d+)\s*classes?$', lines[i], re.IGNORECASE)
                    if match:
                        present = int(match.group(1))
                        total = int(match.group(2))
                        skip_count = 1
                
                if present is not None and total is not None and total > 0:
                    # Search BACKWARDS for the subject name
                    # The structure before attendance is: [%], SubjectName, CourseCode, XofYclasses
                    # OR: SubjectName, CourseCode, ShortCode, X, of, Y, classes
                    subject_name = None
                    for j in range(i-1, max(0, i-8), -1):
                        candidate = lines[j].strip()
                        if not candidate:
                            continue
                        if self.is_valid_subject_name(candidate):
                            subject_name = candidate
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
                        print(f"  ✓ {subject_name}: {present}/{total} ({percentage}%)")
                    
                    i += skip_count
                    continue
                
                i += 1
            
            # ==========================================
            # Fallback: card-based extraction
            # ==========================================
            if not attendance_data:
                print("\nFallback: Card-based extraction...")
                
                card_selectors = [
                    ".MuiCard-root",
                    ".MuiPaper-root",
                    "[class*='card']",
                    "[class*='attendance']",
                ]
                
                cards = []
                for selector in card_selectors:
                    try:
                        found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if found:
                            cards.extend(found)
                    except:
                        pass
                
                seen_ids = set()
                for card in cards:
                    try:
                        card_id = card.id if card.id else id(card)
                        if card_id in seen_ids:
                            continue
                        seen_ids.add(card_id)
                        
                        card_text = card.text.strip()
                        if not card_text:
                            continue
                        
                        card_lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                        
                        # Look for multiline attendance pattern in card
                        present, total = None, None
                        for ci in range(len(card_lines) - 3):
                            if (card_lines[ci].isdigit() and 
                                card_lines[ci+1].lower() == 'of' and 
                                card_lines[ci+2].isdigit() and
                                ci+3 < len(card_lines) and card_lines[ci+3].lower().startswith('class')):
                                present = int(card_lines[ci])
                                total = int(card_lines[ci+2])
                                break
                        
                        # Also try single-line
                        if present is None:
                            for cl in card_lines:
                                m = re.search(r'(\d+)\s*of\s*(\d+)\s*classes?', cl, re.IGNORECASE)
                                if m:
                                    present = int(m.group(1))
                                    total = int(m.group(2))
                                    break
                        
                        if present is not None and total is not None and total > 0:
                            subject_name = None
                            for cl in card_lines:
                                if self.is_valid_subject_name(cl):
                                    subject_name = cl
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
                                print(f"  ✓ {subject_name}: {present}/{total} ({percentage}%)")
                    except:
                        continue
            
            # ==========================================
            # Return results
            # ==========================================
            if attendance_data:
                attendance_data.sort(key=lambda x: x['subject'])
                print(f"\n✓ Successfully extracted {len(attendance_data)} subjects")
                
                print("\n--- EXTRACTED SUBJECTS ---")
                for s in attendance_data:
                    print(f"  {s['subject']}: {s['present']}/{s['total']} ({s['percentage']}%)")
                print("--- END ---\n")
                
                if not overall_attendance:
                    total_present = sum(s['present'] for s in attendance_data)
                    total_classes = sum(s['total'] for s in attendance_data)
                    if total_classes > 0:
                        overall_attendance = {
                            'present': total_present,
                            'total': total_classes,
                            'percentage': round((total_present / total_classes) * 100, 2)
                        }
                
                return {
                    'subjects': attendance_data,
                    'overall': overall_attendance
                }
            
            print("\n⚠ No attendance data found automatically.")
            print("Check last_scrape_debug.html and last_scrape_text.txt for debugging.")
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
        timetable_data = None
        
        try:
            self.setup_driver()
            
            if not self.login():
                print("\n✗ Login failed. Please check your credentials.")
                return None
            
            if not self.navigate_to_attendance():
                print("\n✗ Could not navigate to attendance page")
                return None
            
            print("\nExtracting attendance data...")
            raw_data = self.extract_attendance_data()
            
            # extract_attendance_data returns {'subjects': [...], 'overall': {...}} or None
            if raw_data and isinstance(raw_data, dict) and raw_data.get('subjects'):
                subjects_data = raw_data['subjects']
                
                if auto_mode:
                    # Auto mode: save without verification (for web interface)
                    verified_data = subjects_data
                else:
                    # Interactive mode: verify data with user
                    verified_data = self.verify_and_correct_data(subjects_data)
                
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
            
            # Now try to extract and save timetable
            print("\n" + "="*70)
            print("EXTRACTING TIMETABLE DATA...")
            print("="*70)
            
            if self.navigate_to_calendar():
                timetable_data = self.extract_timetable_data()
                if timetable_data and len(timetable_data) > 0:
                    print(f"\n✓ Extracted {len(timetable_data)} timetable entries")
                else:
                    print("\n⚠ Could not extract timetable from calendar page")
            else:
                print("\n⚠ Could not navigate to calendar page")
                
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
        
        # Return both attendance and timetable data
        return {
            'attendance_file': filename,
            'attendance_data': verified_data,
            'timetable_data': timetable_data
        }


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
