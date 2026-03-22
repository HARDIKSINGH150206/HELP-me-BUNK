#!/usr/bin/env python3
"""
Acharya ERP Attendance Scraper - v2 (HTTP API Based)
Replaces Selenium with direct httpx API calls to Acharya ERP backend

FIX: get_courses() now correctly parses semester-grouped response.
     Previously only returned 5 courses (data root); now returns all 9
     from the current semester (data.courses["4"]).
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
        self.username = username
        self.password = password
        self.frontend_url = "https://student.acharyaerptech.in"
        self.api_base_url = "https://acerp.acharyaerptech.in/api"
        self.client: Optional[httpx.AsyncClient] = None
        self.session_headers = {}
        self.auth_token = None
        self.batch_id = None
        self.student_id = None
        self.logged_in = False
        self.session_expired = False

    async def __aenter__(self):
        await self.init_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                verify=True
            )

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None
            self.logged_in = False

    def _safe_parse_json(self, response_text: str, endpoint: str) -> Dict[str, Any]:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"\n⚠️  JSON parsing failed for {endpoint}")
            print(f"   Error: {e}")
            print(f"   Raw response (first 500 chars):\n{response_text[:500]}")
            return {}

    async def login(self, username: Optional[str] = None,
                    password: Optional[str] = None) -> bool:
        """
        POST https://acerp.acharyaerptech.in/api/authenticate

        Body:   { "username": "AIT24BECS108", "password": "..." }
        Response data fields used:
          data.token    → Bearer token for all future requests
          data.userId   → numeric internal ID (e.g. 3741)
          data.userName → AUID string (e.g. AIT24BECS108)
        """
        if username:
            self.username = username
        if password:
            self.password = password

        if not self.client:
            await self.init_client()

        try:
            endpoint = "https://acerp.acharyaerptech.in/api/authenticate"
            request_body = {"username": self.username, "password": self.password}

            print(f"🔑 Logging in to Acharya ERP")
            print(f"   Endpoint: {endpoint}")
            print(f"   User: {self.username}")

            response = await self.client.post(endpoint, json=request_body)
            print(f"   Response status: {response.status_code}")

            if response.status_code in [200, 201]:
                response_data = self._safe_parse_json(response.text, endpoint)
                if not response_data:
                    print("   ✗ Empty response")
                    return False

                if response_data.get('success') and response_data.get('data'):
                    data = response_data['data']
                    self.auth_token = data.get('token')
                    self.student_id = data.get('userId')
                    self.username = data.get('userName', self.username)

                    if self.auth_token:
                        self.session_headers = {
                            'Authorization': f'Bearer {self.auth_token}',
                            'Content-Type': 'application/json',
                            'Ngrok-Skip-Browser-Warning': 'true',
                        }
                        self.logged_in = True
                        self.session_expired = False
                        print(f"✓ Login successful!")
                        print(f"  Token: {self.auth_token[:30]}...")
                        print(f"  User ID: {self.student_id}")
                        print(f"  AUID: {self.username}")
                        return True
                    else:
                        print("✗ No token in response")
                        return False
                else:
                    print(f"✗ Invalid response structure")
                    print(f"  Response keys: {list(response_data.keys())}")
                    return False

            elif response.status_code in [401, 403]:
                print("✗ Authentication failed (401/403)")
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
        GET /api/getStudentDetailsBasedOnAuidAndStrudentId?auid=...&studentId=...
        """
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return {}

        try:
            endpoint = f"{self.api_base_url}/getStudentDetailsBasedOnAuidAndStrudentId"
            params = {
                'auid': self.username,
                'studentId': self.student_id or self.username,
            }
            print("📋 Fetching student details...")
            response = await self.client.get(
                endpoint, params=params, headers=self.session_headers
            )
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return {}
            if response.status_code != 200:
                print(f"✗ Failed to fetch student details: {response.status_code}")
                return {}
            data = self._safe_parse_json(response.text, endpoint)
            print("✓ Student details fetched")
            return data
        except Exception as e:
            print(f"✗ Error fetching student details: {e}")
            return {}

    async def get_attendance(self) -> List[Dict[str, Any]]:
        """
        GET /api/academic/students/{student_id}/studentAttendance
        """
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired - run login() first")
            return []

        try:
            if not self.student_id:
                print("✗ Student ID not set - login first")
                return []

            endpoint = (
                f"https://acerp.acharyaerptech.in/api/academic/students"
                f"/{self.student_id}/studentAttendance"
            )
            print(f"📚 Fetching attendance data for student {self.student_id}...")

            response = await self.client.get(endpoint, headers=self.session_headers)

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

            attendance_list = self._parse_attendance_response(raw_data)
            if attendance_list:
                print(f"✓ Fetched attendance for {len(attendance_list)} subjects")
                return attendance_list
            else:
                print("⚠️  Could not parse attendance data")
                print(f"   Response keys: {list(raw_data.keys())}")
                return []

        except Exception as e:
            print(f"✗ Error fetching attendance: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_attendance_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        attendance_data = []
        processed = set()

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
                subject_name = (
                    item.get('subjectName') or item.get('subject') or
                    item.get('name') or item.get('subjectTitle') or
                    item.get('courseName')
                )
                present = (
                    item.get('present') or item.get('attended') or
                    item.get('classesAttended') or item.get('conductedAttended')
                )
                total = (
                    item.get('total') or item.get('conducted') or
                    item.get('totalClasses') or item.get('totalConducted')
                )
                percentage = (
                    item.get('percentage') or item.get('percent') or
                    item.get('attendancePercent') or item.get('percentageAttendance')
                )
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
                    print(f"⚠️  Could not parse item: {item} — {e}")
                    continue

        return attendance_data

    # ── FIXED METHOD ──────────────────────────────────────────────────────────
    async def get_courses(self, target_sem: int = None) -> List[Dict[str, Any]]:
        """
        GET /api/academic/students/{student_id}/courses

        ╔══════════════════════════════════════════════════════════╗
        ║  BUG FIX: response structure is NOT a flat list.         ║
        ║                                                          ║
        ║  Actual shape:                                           ║
        ║    data.courses = {                                      ║
        ║      "1": [ 2 courses ],                                 ║
        ║      "2": [ 11 entries ],                                ║
        ║      "3": [ 8 courses ],                                 ║
        ║      "4": [ 9 courses ]  ← current sem, was being missed ║
        ║    }                                                     ║
        ║                                                          ║
        ║  Old code: data.get("data") → only hit root, got 5       ║
        ║  New code: data["courses"]["4"] → gets all 9 ✓           ║
        ╚══════════════════════════════════════════════════════════╝

        Args:
          target_sem=None  → latest (highest) semester only  [DEFAULT]
          target_sem=0     → ALL courses across every semester (flattened)
          target_sem=N     → courses for a specific semester N
        """
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return []

        try:
            endpoint = (
                f"https://acerp.acharyaerptech.in/api/academic"
                f"/students/{self.student_id}/courses"
            )
            print("📖 Fetching courses list...")

            response = await self.client.get(endpoint, headers=self.session_headers)

            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            if response.status_code != 200:
                print(f"✗ Failed to fetch courses: {response.status_code}")
                return []

            body = self._safe_parse_json(response.text, endpoint)
            data = body.get("data", {})

            # Courses are nested under data.courses keyed by semester string
            courses_by_sem = data.get("courses", {})

            if not courses_by_sem:
                print("⚠️  No courses found in response")
                return []

            # target_sem=0 → return everything flattened
            if target_sem == 0:
                all_courses = []
                for sem_courses in courses_by_sem.values():
                    if isinstance(sem_courses, list):
                        all_courses.extend(sem_courses)
                print(f"✓ Fetched {len(all_courses)} courses (all semesters)")
                return all_courses

            # Default: use the highest available semester key (current sem)
            if target_sem is None:
                latest_key = str(max(int(k) for k in courses_by_sem.keys()))
            else:
                latest_key = str(target_sem)

            result = courses_by_sem.get(latest_key, [])
            print(f"✓ Fetched {len(result)} courses for semester {latest_key}")
            return result

        except Exception as e:
            print(f"✗ Error fetching courses: {e}")
            import traceback
            traceback.print_exc()
            return []
    # ── END FIX ───────────────────────────────────────────────────────────────

    async def get_internals(self) -> List[Dict[str, Any]]:
        """
        GET /api/fetchStudentInternalsReportWithFilteredData?student_id={id}
        """
        if not self.logged_in or self.session_expired:
            print("✗ Not logged in or session expired")
            return []

        try:
            endpoint = (
                f"{self.api_base_url}/fetchStudentInternalsReportWithFilteredData"
                f"?student_id={self.student_id}"
            )
            print("📊 Fetching internals data...")
            response = await self.client.get(endpoint, headers=self.session_headers)
            if response.status_code == 401:
                self.session_expired = True
                print("✗ Session expired (401)")
                return []
            if response.status_code != 200:
                print(f"✗ Failed to fetch internals: {response.status_code}")
                return []
            data = self._safe_parse_json(response.text, endpoint)
            print("✓ Fetched internals data")
            return data
        except Exception as e:
            print(f"✗ Error fetching internals: {e}")
            return []


async def scrape_for_user(username: str, password: str,
                          auto_mode: bool = True) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement — maintains API compatibility with original scraper.
    """
    scraper = None
    try:
        scraper = AcharyaScraper(username, password)
        await scraper.init_client()

        if not await scraper.login():
            print("\n✗ Login failed")
            return None

        attendance_list = await scraper.get_attendance()
        if not attendance_list:
            print("\n✗ No attendance data retrieved")
            return None

        # get_courses() now returns all 9 current-sem subjects by default
        courses = await scraper.get_courses()
        internals = await scraper.get_internals()

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

        total_present = sum(s['present'] for s in attendance_list)
        total_classes = sum(s['total'] for s in attendance_list)
        overall_pct = round(
            (total_present / total_classes) * 100, 2
        ) if total_classes > 0 else 0

        return {
            'attendance_file': filename,
            'attendance_data': attendance_list,
            'overall': {
                'present': total_present,
                'total': total_classes,
                'percentage': overall_pct
            },
            'timetable_data': [],
            'courses': courses,
            'internals': internals
        }

    finally:
        if scraper:
            await scraper.close()


if __name__ == "__main__":
    print("=" * 70)
    print("ACHARYA ERP ATTENDANCE SCRAPER v2 (HTTP API) — FIXED")
    print("=" * 70)
    print()

    username = input("Enter your username/roll number: ").strip()
    password = input("Enter your password: ").strip()

    if not username or not password:
        print("\n✗ Username and password are required!")
        exit(1)

    async def main():
        scraper = None
        try:
            scraper = AcharyaScraper(username, password)
            await scraper.init_client()

            print("\n" + "=" * 70)
            print("STEP 1: Login")
            print("=" * 70)
            if not await scraper.login():
                print("\n✗ Login failed")
                return

            print("\n" + "=" * 70)
            print("STEP 2: Student Details")
            print("=" * 70)
            details = await scraper.get_student_details()
            print(f"  Keys: {list(details.keys())}")

            print("\n" + "=" * 70)
            print("STEP 3: Attendance")
            print("=" * 70)
            attendance = await scraper.get_attendance()
            print(f"  {len(attendance)} subjects found:")
            for s in attendance:
                print(f"  - {s['subject']}: {s['present']}/{s['total']} ({s['percentage']}%)")

            print("\n" + "=" * 70)
            print("STEP 4: Courses (current semester)")
            print("=" * 70)
            courses = await scraper.get_courses()          # default: latest sem
            print(f"  {len(courses)} courses (should be 9):")
            for c in courses:
                print(f"  - [{c.get('course_code','?')}] {c.get('course_name','?')}")

            print("\n" + "=" * 70)
            print("STEP 5: Internals")
            print("=" * 70)
            internals = await scraper.get_internals()
            print(f"  Type: {type(internals)}, Count: {len(internals) if isinstance(internals, list) else 'N/A'}")

            print("\n" + "=" * 70)
            print("✓ ALL DONE")
            print("=" * 70)

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if scraper:
                await scraper.close()

    asyncio.run(main())
