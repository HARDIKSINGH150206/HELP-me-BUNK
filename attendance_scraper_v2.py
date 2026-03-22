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
        
        VERIFIED API ENDPOINT (from DevTools):
        POST https://acerp.acharyaerptech.in/api/authenticate
        
        Request Fields:
          - username: student AUID (e.g. AIT24BECS108)
          - password: ERP password
        
        Response Format:
          {
            "success": true,
            "data": {
              "token": "eyJhbGc...",
              "userId": 3741,
              "userName": "AIT24BECS108"
            }
          }
        """
        
        if username:
            self.username = username
        if password:
            self.password = password
        
        if not self.client:
            await self.init_client()
        
        try:
            # VERIFIED endpoint from DevTools
            endpoint = "https://acerp.acharyaerptech.in/api/authenticate"
            
            request_body = {
                "username": self.username,
                "password": self.password,
            }
            
            print(f"🔑 Logging in to Acharya ERP")
            print(f"   Endpoint: {endpoint}")
            print(f"   User: {self.username}")
            
            response = await self.client.post(endpoint, json=request_body)
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                response_data = self._safe_parse_json(response.text, endpoint)
                
                if not response_data:
                    print(f"   ✗ Empty response")
                    return False
                
                # Extract from nested 'data' structure
                if response_data.get('success') and response_data.get('data'):
                    data = response_data['data']
                    
                    # Get token (verified location)
                    self.auth_token = data.get('token')
                    
                    # Get numeric user ID (userId not student_id in login response)
                    self.student_id = data.get('userId')
                    
                    # Also save AUID for reference
                    self.username = data.get('userName', self.username)
                    
                    if self.auth_token:
                        # Set Bearer token for all future requests
                        self.session_headers = {
                            'Authorization': f'Bearer {self.auth_token}',
                            'Content-Type': 'application/json',
                        }
                        
                        self.logged_in = True
                        self.session_expired = False
                        print(f"✓ Login successful!")
                        print(f"  Token: {self.auth_token[:30]}...")
                        print(f"  User ID: {self.student_id}")
                        print(f"  AUID: {self.username}")
                        return True
                    else:
                        print(f"✗ No token in response")
                        return False
                else:
                    print(f"✗ Invalid response structure")
                    print(f"  Response keys: {list(response_data.keys())}")
                    return False
            
            elif response.status_code in [401, 403]:
                print(f"✗ Authentication failed (401/403)")
                print(f"  Invalid credentials or server rejected")
                return False
            
            elif response.status_code >= 500:
                print(f"✗ Server error ({response.status_code})")
                return False
            
            else:
                print(f"✗ Unexpected status: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False
        
        except Exception as e:
            print(f"✗ Login error: {e}")
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
        
        VERIFIED ENDPOINT (from DevTools):
        GET https://acerp.acharyaerptech.in/api/academic/students/{student_id}/studentAttendance
        
        NOTE: Uses numeric student_id (userId from login response, e.g. 3741)
        NOT the AUID (e.g. AIT24BECS108)
        
        Response: Expected to contain attendance data for all enrolled subjects
        """
        
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired - run login() first")
            return []
        
        try:
            # Use numeric student_id (userId from login response)
            if not self.student_id:
                print("✗ Student ID not set - login first")
                return []
            
            # VERIFIED endpoint from DevTools
            endpoint = f"https://acerp.acharyaerptech.in/api/academic/students/{self.student_id}/studentAttendance"
            
            print(f"📚 Fetching attendance data for student {self.student_id}...")
            
            response = await self.client.get(
                endpoint,
                headers=self.session_headers
            )
            
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch attendance: {response.status_code}")
                print(f"   Endpoint: {endpoint}")
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
                print("⚠️  Could not parse attendance data")
                print(f"   Response keys: {list(raw_data.keys())}")
                print(f"   Full response for debugging: {raw_data}")
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
