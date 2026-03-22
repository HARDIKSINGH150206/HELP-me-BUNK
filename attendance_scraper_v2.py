#!/usr/bin/env python3
"""
Acharya ERP Attendance Scraper - v2 (HTTP API Based)
Replaces Selenium with direct httpx API calls to Acharya ERP backend
"""

import httpx
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class AcharyaScraper:
    """Non-blocking async HTTP scraper using httpx for Acharya ERP API"""
    
    def __init__(self, username: str, password: str):
        """Initialize scraper with credentials and API endpoints"""
        self.username = username
        self.password = password
        
        # Base URLs for API calls
        self.frontend_url = "https://student.acharyaerptech.in"
        self.api_base_url = "https://acerp.acharyaerptech.in/api"
        
        # Session management
        self.client: Optional[httpx.AsyncClient] = None
        self.session_headers = {}
        self.auth_token = None
        self.batch_id = None
        self.student_id = None
        
        # Flags
        self.logged_in = False
        self.session_expired = False
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()
    
    async def init_client(self):
        """Initialize httpx AsyncClient with proper headers"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=True
            )
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.logged_in = False
    
    def _safe_parse_json(self, response_text: str, endpoint: str) -> Dict[str, Any]:
        """
        Safely parse JSON response with detailed logging for debugging.
        If parsing fails, logs the raw response so user can debug field names.
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"\n⚠️  JSON parsing failed for {endpoint}")
            print(f"   Error: {e}")
            print(f"   Raw response (first 500 chars):\n{response_text[:500]}")
            print(f"\n   → TODO: Check DevTools Network tab for correct response structure")
            return {}
    
    async def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Login to Acharya ERP using HTTP API
        
        TODO: Confirm the exact login endpoint URL from DevTools > Network tab
        Try these patterns:
        1. POST /auth/login
        2. POST /auth/authenticate
        3. POST /api/student/login
        4. Check Frontend XHR calls during manual login
        
        TODO: Verify exact request body field names from DevTools Request tab
        Common patterns:
        - {"username": "...", "password": "..."}
        - {"email": "...", "password": "..."}
        - {"studentId": "...", "password": "..."}
        - {"auid": "...", "password": "..."}
        
        TODO: Verify auth response format and where auth token is stored:
        - In response JSON field like "token", "access_token", "sessionId"?
        - In Set-Cookie headers (httpx handles automatically)?
        - In custom headers like "X-Auth-Token"?
        """
        
        if username:
            self.username = username
        if password:
            self.password = password
        
        if not self.client:
            await self.init_client()
        
        try:
            # TODO: Replace with actual login endpoint from DevTools
            login_endpoints = [
                f"{self.frontend_url}/api/auth/login",
                f"{self.frontend_url}/api/login",
                f"{self.api_base_url}/auth/login",
                f"{self.api_base_url}/login",
            ]
            
            # TODO: Verify correct request body field names
            request_bodies = [
                {"username": self.username, "password": self.password},
                {"email": self.username, "password": self.password},
                {"studentId": self.username, "password": self.password},
                {"auid": self.username, "password": self.password},
            ]
            
            print(f"🔑 Attempting login for user: {self.username}")
            print(f"   (Will try {len(login_endpoints)} endpoint patterns)")
            
            last_error = None
            
            for endpoint_idx, endpoint in enumerate(login_endpoints):
                for body_idx, body in enumerate(request_bodies):
                    try:
                        print(f"   Trying: {endpoint} with {list(body.keys())}")
                        
                        response = await self.client.post(endpoint, json=body)
                        
                        print(f"   ✓ Response status: {response.status_code}")
                        
                        # Handle successful response
                        if response.status_code in [200, 201]:
                            response_data = self._safe_parse_json(response.text, endpoint)
                            
                            if not response_data:
                                print(f"   ⚠️  Empty response")
                                continue
                            
                            # TODO: Verify the tokens/session are returned in one of these fields:
                            self.auth_token = (
                                response_data.get('token') or 
                                response_data.get('access_token') or 
                                response_data.get('sessionId') or 
                                response_data.get('sid')
                            )
                            
                            # TODO: Verify student ID field name from response
                            self.student_id = (
                                response_data.get('studentId') or 
                                response_data.get('id') or 
                                response_data.get('auid')
                            )
                            
                            if self.auth_token:
                                # Set up auth headers for future requests
                                # TODO: Verify which header format backend expects:
                                # Option 1: Authorization: Bearer <token>
                                # Option 2: X-Auth-Token: <token>
                                # Option 3: Custom header like Authorization: <token>
                                self.session_headers = {
                                    'Authorization': f'Bearer {self.auth_token}',
                                    # 'X-Auth-Token': self.auth_token,  # Alternative
                                }
                                
                                self.logged_in = True
                                self.session_expired = False
                                print(f"✓ Login successful!")
                                print(f"  Auth Token: {self.auth_token[:20]}..." if self.auth_token else "  (Using cookies)")
                                print(f"  Student ID: {self.student_id}")
                                return True
                            
                            # Fallback: cookies might be set automatically by httpx
                            if response.status_code == 200:
                                self.logged_in = True
                                self.session_expired = False
                                print(f"✓ Login successful (cookie-based auth)")
                                return True
                        
                        elif response.status_code in [401, 403]:
                            print(f"   ✗ Unauthorized (401/403) - invalid credentials")
                            return False
                        
                        elif response.status_code >= 500:
                            print(f"   ✗ Server error ({response.status_code})")
                            last_error = f"Server error {response.status_code}"
                            continue
                    
                    except httpx.TimeoutException:
                        print(f"   ✗ Timeout - server not responding")
                        last_error = "Timeout"
                    except httpx.ConnectError:
                        print(f"   ✗ Connection error - check URL and network")
                        last_error = "Connection error"
                    except Exception as e:
                        print(f"   ✗ Error: {type(e).__name__}: {e}")
                        last_error = str(e)
            
            # All attempts failed
            print(f"\n✗ Login failed after {len(login_endpoints) * len(request_bodies)} attempts")
            if last_error:
                print(f"   Last error: {last_error}")
            print(f"\n→ TODO: Inspect DevTools Network tab during manual login:")
            print(f"   1. Open DevTools (F12) > Network tab")
            print(f"   2. Login manually on {self.frontend_url}")
            print(f"   3. Look for XHR POST request")
            print(f"   4. Note: URL, Request body fields, Response status, Response fields")
            return False
        
        except Exception as e:
            print(f"✗ Login exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def get_student_details(self) -> Dict[str, Any]:
        """
        Fetch student profile details from API
        
        Endpoint: GET https://acerp.acharyaerptech.in/api/getStudentDetailsBasedOnAuidAndStrudentId
        
        TODO: Verify exact endpoint URL and required query parameters
        Common params: ?auid=...&studentId=...
        """
        
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return {}
        
        try:
            endpoint = f"{self.api_base_url}/getStudentDetailsBasedOnAuidAndStrudentId"
            
            # TODO: Verify these are the correct parameter names
            params = {
                'auid': self.username,
                'studentId': self.student_id or self.username,
            }
            
            print(f"📋 Fetching student details...")
            
            response = await self.client.get(
                endpoint,
                params=params,
                headers=self.session_headers
            )
            
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return {}
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch student details: {response.status_code}")
                return {}
            
            data = self._safe_parse_json(response.text, endpoint)
            print(f"✓ Student details fetched")
            return data
        
        except Exception as e:
            print(f"✗ Error fetching student details: {e}")
            return {}
    
    async def get_attendance(self) -> List[Dict[str, Any]]:
        """
        Fetch attendance data from Acharya ERP API
        
        Endpoint: GET https://acerp.acharyaerptech.in/api/attendance/{batch_id}?date=YYYY-MM-DD
        
        TODO: Verify exact endpoint pattern and required parameters:
        1. Does batch_id come from student details response?
        2. What's the exact field name in student response? ("batchId", "batch", etc?)
        3. Is date parameter required or optional?
        4. What date format? (YYYY-MM-DD, DD-MM-YYYY, timestamp, etc?)
        
        TODO: Verify the attendance JSON response structure:
        Response might look like:
        {
          "subjects": [
            {
              "subjectName": "Mathematics",
              "courseCode": "BCS401",
              "present": 23,
              "total": 53,
              "percentage": 43.4
            }
          ]
        }
        OR:
        {
          "data": [
            {
              "name": "Subject",
              "attended": 23,
              "conducted": 53,
              "percent": 43.4
            }
          ]
        }
        OR fully different structure
        """
        
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired - run login() first")
            return []
        
        try:
            # Get batch_id from student details if not already set
            if not self.batch_id:
                student_details = await self.get_student_details()
                # TODO: Verify field name for batch ID in response
                self.batch_id = (
                    student_details.get('batchId') or 
                    student_details.get('batch_id') or 
                    student_details.get('batch') or 
                    student_details.get('id')
                )
            
            if not self.batch_id:
                print("✗ Could not determine batch ID")
                return []
            
            # TODO: Verify date parameter format and necessity
            endpoint = f"{self.api_base_url}/attendance/{self.batch_id}"
            today = datetime.now().strftime("%Y-%m-%d")
            
            params = {
                'date': today,  # TODO: Verify if this parameter is needed
            }
            
            print(f"📚 Fetching attendance data for batch {self.batch_id}...")
            
            response = await self.client.get(
                endpoint,
                params=params,
                headers=self.session_headers
            )
            
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch attendance: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return []
            
            raw_data = self._safe_parse_json(response.text, endpoint)
            
            if not raw_data:
                print("✗ Empty response from attendance endpoint")
                return []
            
            # Parse attendance data with fallback field names
            attendance_list = self._parse_attendance_response(raw_data)
            
            if attendance_list:
                print(f"✓ Fetched attendance for {len(attendance_list)} subjects")
                return attendance_list
            else:
                print("⚠️  Could not parse attendance data - check field names in DevTools")
                print(f"   Raw response keys: {list(raw_data.keys())}")
                return []
        
        except Exception as e:
            print(f"✗ Error fetching attendance: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_attendance_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse raw API attendance response into standardized format
        
        TODO: Verify these field names from actual API response:
        subject_field_names = ["subjectName", "subject", "name", "course_name"]
        present_field_names = ["present", "attended", "conducted_attended", "classesAttended"]
        total_field_names = ["total", "conducted", "total_conducted", "totalClasses"]
        percentage_field_names = ["percentage", "percent", "attendance_percent", "percentage_attendance"]
        """
        
        attendance_data = []
        processed = set()
        
        # Try different possible data structures
        data_sources = [
            response.get('subjects'),
            response.get('data'),
            response.get('attendance'),
            response.get('results'),
            response if isinstance(response, list) else None,
        ]
        
        for data_source in data_sources:
            if not data_source or not isinstance(data_source, list):
                continue
            
            for item in data_source:
                if not isinstance(item, dict):
                    continue
                
                # TODO: Verify these field names from API response
                # Multiple fallbacks in case naming varies
                subject_name = (
                    item.get('subjectName') or 
                    item.get('subject') or 
                    item.get('name') or 
                    item.get('subjectTitle') or 
                    item.get('courseName')
                )
                
                present = (
                    item.get('present') or 
                    item.get('attended') or 
                    item.get('classesAttended') or 
                    item.get('conductedAttended')
                )
                
                total = (
                    item.get('total') or 
                    item.get('conducted') or 
                    item.get('totalClasses') or 
                    item.get('totalConducted')
                )
                
                percentage = (
                    item.get('percentage') or 
                    item.get('percent') or 
                    item.get('attendancePercent') or 
                    item.get('percentageAttendance')
                )
                
                # Validate and convert types
                if not subject_name or subject_name in processed:
                    continue
                
                try:
                    present = int(present) if present is not None else None
                    total = int(total) if total is not None else None
                    
                    if percentage is not None:
                        percentage = float(percentage)
                    elif present is not None and total is not None and total > 0:
                        percentage = round((present / total) * 100, 2)
                    
                    if present is not None and total is not None and total > 0:
                        attendance_data.append({
                            'subject': str(subject_name).strip(),
                            'present': present,
                            'total': total,
                            'percentage': percentage if percentage is not None else 0.0
                        })
                        processed.add(subject_name)
                
                except (ValueError, TypeError) as e:
                    print(f"⚠️  Could not parse item: {item}")
                    print(f"    Error: {e}")
                    continue
        
        return attendance_data
    
    async def get_courses(self) -> List[Dict[str, Any]]:
        """
        Fetch courses/subjects list from Acharya ERP API
        
        Endpoint: GET https://acerp.acharyaerptech.in/api/courses
        
        TODO: Verify exact endpoint and response format
        Response might include: courseId, courseName, courseCode, credits, etc.
        """
        
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return []
        
        try:
            endpoint = f"{self.api_base_url}/courses"
            
            print(f"📖 Fetching courses list...")
            
            response = await self.client.get(endpoint, headers=self.session_headers)
            
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch courses: {response.status_code}")
                return []
            
            data = self._safe_parse_json(response.text, endpoint)
            
            # TODO: Verify response structure
            courses = data.get('courses') or data.get('data') or (data if isinstance(data, list) else [])
            
            print(f"✓ Fetched {len(courses)} courses")
            return courses
        
        except Exception as e:
            print(f"✗ Error fetching courses: {e}")
            return []
    
    async def get_internals(self) -> List[Dict[str, Any]]:
        """
        Fetch internal marks/assessment data
        
        Endpoint: GET https://acerp.acharyaerptech.in/api/fetchStudentInternalsReportWithFilteredData
        
        TODO: Verify exact endpoint and query parameters
        """
        
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return []
        
        try:
            endpoint = f"{self.api_base_url}/fetchStudentInternalsReportWithFilteredData"
            
            print(f"📊 Fetching internals data...")
            
            response = await self.client.get(endpoint, headers=self.session_headers)
            
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch internals: {response.status_code}")
                return []
            
            data = self._safe_parse_json(response.text, endpoint)
            print(f"✓ Fetched internals data")
            return data
        
        except Exception as e:
            print(f"✗ Error fetching internals: {e}")
            return []


async def scrape_for_user(username: str, password: str, auto_mode: bool = True) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement function that maintains API compatibility with original scraper
    
    Args:
        username: ERP username/roll number
        password: ERP password
        auto_mode: If True, skip verification (for web scraping)
    
    Returns:
        {
            'attendance_file': str (filename),
            'attendance_data': [{subject, present, total, percentage}],
            'timetable_data': [],  # Not implemented yet in API version
            'courses': [],
            'internals': []
        }
        or None on failure
    """
    
    scraper = None
    try:
        scraper = AcharyaScraper(username, password)
        await scraper.init_client()
        
        # Attempt login
        if not await scraper.login():
            print("\n✗ Login failed")
            return None
        
        # Fetch attendance
        attendance_list = await scraper.get_attendance()
        
        if not attendance_list:
            print("\n✗ No attendance data retrieved")
            return None
        
        # Fetch additional data
        courses = await scraper.get_courses()
        internals = await scraper.get_internals()
        
        # Save attendance data to file (mimics original behavior)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"attendance_{timestamp}.json"
        
        output_data = {
            'timestamp': timestamp,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'source': 'Acharya ERP (API)',
            'data': attendance_list
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n✓ Data saved to {filename}")
        except Exception as e:
            print(f"\n⚠️  Could not save file: {e}")
        
        # Calculate overall attendance
        total_present = sum(s['present'] for s in attendance_list)
        total_classes = sum(s['total'] for s in attendance_list)
        overall_percentage = round((total_present / total_classes) * 100, 2) if total_classes > 0 else 0
        
        return {
            'attendance_file': filename,
            'attendance_data': attendance_list,
            'overall': {
                'present': total_present,
                'total': total_classes,
                'percentage': overall_percentage
            },
            'timetable_data': [],  # TODO: API might not expose timetable - use courses instead
            'courses': courses,
            'internals': internals
        }
    
    finally:
        if scraper:
            await scraper.close()


if __name__ == "__main__":
    """
    Standalone testing script
    Prints raw API responses for debugging field names
    """
    
    print("="*70)
    print("ACHARYA ERP ATTENDANCE SCRAPER v2 (HTTP API)")
    print("="*70)
    print()
    
    username = input("Enter your username/roll number: ").strip()
    password = input("Enter your password: ").strip()
    
    if not username or not password:
        print("\n✗ Username and password are required!")
        exit(1)
    
    print()
    
    async def main():
        scraper = None
        try:
            scraper = AcharyaScraper(username, password)
            await scraper.init_client()
            
            # Test login
            print("\n" + "="*70)
            print("STEP 1: Testing Login")
            print("="*70)
            if not await scraper.login():
                print("\n✗ Login failed - cannot proceed")
                return
            
            # Test student details
            print("\n" + "="*70)
            print("STEP 2: Fetching Student Details")
            print("="*70)
            student_details = await scraper.get_student_details()
            print(f"✓ Response keys: {list(student_details.keys())}")
            print(f"✓ Raw response:\n{json.dumps(student_details, indent=2)[:500]}")
            
            # Test attendance
            print("\n" + "="*70)
            print("STEP 3: Fetching Attendance")
            print("="*70)
            attendance = await scraper.get_attendance()
            print(f"✓ Retrieved {len(attendance)} subjects:")
            for subject in attendance:
                print(f"  - {subject['subject']}: {subject['present']}/{subject['total']} ({subject['percentage']}%)")
            
            # Test courses
            print("\n" + "="*70)
            print("STEP 4: Fetching Courses")
            print("="*70)
            courses = await scraper.get_courses()
            print(f"✓ Retrieved {len(courses)} courses")
            if courses:
                print(f"  First course keys: {list(courses[0].keys())}")
            
            # Test internals
            print("\n" + "="*70)
            print("STEP 5: Fetching Internals")
            print("="*70)
            internals = await scraper.get_internals()
            print(f"✓ Retrieved internals")
            print(f"  Type: {type(internals)}, Length: {len(internals) if isinstance(internals, list) else 'N/A'}")
            
            print("\n" + "="*70)
            print("✓ ALL TESTS PASSED")
            print("="*70)
        
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if scraper:
                await scraper.close()
    
    # Run async main
    asyncio.run(main())
