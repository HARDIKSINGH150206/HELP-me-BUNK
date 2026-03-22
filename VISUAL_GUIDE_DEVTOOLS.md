#!/usr/bin/env python3
r"""
VISUAL GUIDE: How to Find Real API in Browser DevTools
=======================================================

STEP 1: Open https://student.acharyaerptech.in
────────────────────────────────────────────────

     ┌─ Firefox/Chrome ─────────────────────────────────┐
     │ https://student.acharyaerptech.in                │
     │                                                  │
     │  ┌──────────────────────────────────────────┐   │
     │  │  Acharya ERP Login                       │   │
     │  │  ────────────────────────────────────    │   │
     │  │  Username: [________________]            │   │
     │  │  Password: [________________]            │   │
     │  │                                          │   │
     │  │         [ Login -->                      │   │
     │  │                                          │   │
     │  └──────────────────────────────────────────┘   │
     │                                                  │
     └──────────────────────────────────────────────────┘

STEP 2: Open DevTools (Press F12)
─────────────────────────────────

     ┌─ Browser Window ─────────────────────────────────┐
     │                                                  │
     │  Login Form (at top) ☝                          │
     │                                                  │
     ├──────────────────────────────────────────────────┤
     │ Elements  Console  Sources│ Network  ... ← CLICK │
     │                           │                      │
     └──────────────────────────────────────────────────┘

STEP 3: Clear Network Log and Preserve
───────────────────────────────────────

     ┌─ Network Tab ──────────────────────────────────┐
     │ [🔴] Preserve log    [✓] Disable cache        │
     │                                               │
     │ [🗑] Clear all requests ← CLICK THIS FIRST  │
     │                                               │
     │ [Filter]                                      │
     │                                               │
     │ Name         Type    Status  Size  Time       │
     │                                               │
     │ (empty - waiting for requests...)             │
     │                                               │
     └───────────────────────────────────────────────┘

STEP 4: Type Credentials and Click Login
─────────────────────────────────────────

     ┌─ Login Form ──────────────────────────────────┐
     │  Username: [john_doe________________]         │
     │  Password: [••••••••••••••••••]              │
     │                                              │
     │         [ Login -->                          │
     │                                              │
     └──────────────────────────────────────────────┘

     As you click Login, watch the Network tab...

STEP 5: Find the Blue/Green POST Request
──────────────────────────────────────────

     ┌─ Network Tab ──────────────────────────────────┐
     │                                               │
     │ Name                          Type      Status │
     │ ─────────────────────────────────────────     │
     │ student.acharyaerptech.in     document   200   │
     │ jquery.js                     script    200   │
     │ bootstrap.css                 style     200   │
     │ ▶ api/studentLogin            xhr       200   │ ← CLICK THIS!
     │ styles.css                    style     200   │
     │                                               │
     └───────────────────────────────────────────────┘

STEP 6: Click the POST Request
──────────────────────────────

When you click on the XHR request, you'll see it expands with tabs:

     ┌─ POST Request Details ─────────────────────────┐
     │ Request  Response  Preview  Timing  Cookies    │
     │                                               │
     │ General:                                      │
     │ Request URL: https://acerp.acharyaerptech    │
     │              .in/api/studentLogin             │
     │ Request Method: POST                          │
     │ Status Code: 200                              │
     │                                               │
     └───────────────────────────────────────────────┘

STEP 7: Check REQUEST Tab - See What We Sent
─────────────────────────────────────────────

     ┌─ Request Tab ──────────────────────────────────┐
     │                                               │
     │ Request Headers:                              │
     │   Content-Type: application/json              │
     │   User-Agent: Mozilla/5.0...                  │
     │   Authorization: Bearer eyJ...                │
     │                                               │
     │ Request Body:                                 │
     │ {                                             │
     │   "studentId": "CS2024001",                   │
     │   "password": "MyPassword123"                 │
     │ }                                             │
     │                                               │
     └───────────────────────────────────────────────┘

     ☝ COPY THESE VALUES!
        - Endpoint: /api/studentLogin
        - Field names: studentId, password

STEP 8: Check RESPONSE Tab - See What Server Returned
──────────────────────────────────────────────────────

     ┌─ Response Tab ─────────────────────────────────┐
     │                                               │
     │ {                                             │
     │   "success": true,                            │
     │   "token": "eyJhbGciOiJIUzI1NiIs...",        │
     │   "student_id": "12345",                      │
     │   "student_name": "John Doe",                 │
     │   "semester": "6",                            │
     │   "expires_in": 86400                         │
     │ }                                             │
     │                                               │
     └───────────────────────────────────────────────┘

     ☝ COPY THESE VALUES!
        - Token field: "token"
        - Student ID field: "student_id"

STEP 9: Fill Out Discovery Form
───────────────────────────────

Run: python discover_real_api.py

Then enter:

     Login Endpoint URL?
     → https://acerp.acharyaerptech.in/api/studentLogin

     Username Field Name?
     → studentId

     Password Field Name?
     → password

     Token Field Name?
     → token

     Student ID Field Name?
     → student_id

STEP 10: Script Updates v2 Automatically
──────────────────────────────────────────

     discover_real_api.py will:
     ✓ Validate your inputs
     ✓ Create backup of old v2
     ✓ Update v2 with real values
     ✓ Test the new version

     Then you'll see:
     ✓ v2 Has Been Updated!
     ✓ Your app is now 5-10x faster!

─────────────────────────────────────────────────────
QUICK CHECKLIST: What to Look For
─────────────────────────────────────────────────────

✓ POST request (not GET)
✓ URL contains "api" or "login" 
✓ Status code is 200 (not 404, 500)
✓ Request body has fields like username/password
✓ Response body has a token field
✓ Response has success or auth information

If you see all of these, you have the right request!

─────────────────────────────────────────────────────
COMMON ENDPOINT PATTERNS
─────────────────────────────────────────────────────

Here are patterns we often see:

1. /api/auth/login
2. /api/v1/student/login
3. /api/student/authenticate
4. /authenticate
5. /api/login
6. /student/login
7. /auth/student/login
8. /v1/authenticate

Your Acharya ERP might use any of these.
The Network tab will show the REAL one!

─────────────────────────────────────────────────────
STILL STUCK? TRY THIS
─────────────────────────────────────────────────────

1. Chrome DevTools > Network > clear
2. Login manually
3. Look for any POST request (might be multiple)
4. Sort by "Type" - look for one labeled "xhr" or "fetch"
5. If still unclear, check the largest response (likely login)
6. That's your endpoint!

Still can't find it? Maybe:
  - You're not logged in yet (try again)
  - Their frontend uses session tokens (check cookies tab)
  - Login redirects to another page (scroll down in Network)
  - They use WebSocket (look for "ws" requests)
"""

print(__doc__)
