# Changelog

All notable changes to HELP-me-BUNK project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Input validation framework with sanitization and format checking
- Startup validation script (`startup_check.py`) with 7 comprehensive checks
- Comprehensive CONTRIBUTING.md guide for developers
- Enhanced README.md with emoji markers and feature categories
- Detailed .env.example with configuration guide
- Logging framework for audit trail
- Request content-type validation decorator (`@require_json`)

### Changed
- Input validation functions: `sanitize_string()`, `validate_email()`, `validate_integer()`, `validate_day_of_week()`, `validate_time_format()`, `validate_percentage()`
- Enhanced .env.example documentation with detailed comments
- Improved README with installation, usage, API, and deployment sections

### Fixed
- Null/null attendance display issue (backend null checks + frontend null comparison)

---

## [1.0.0] - 2025-02-11

### Added

#### Timetable & Calendar Feature
- Complete rewrite of `extract_timetable_data()` in `attendance_scraper.py`
  - Properly parses Acharya ERP 7-column calendar grid
  - Extracts event metadata: type (Lecture/Lab/Holiday), color class, order
  - Returns structured data: {subject, event_type, day, order, color_class, start_time, end_time}
- Updated database schema for timetable entries
  - New fields: `event_type`, `color_class`, `order`
  - Better sorting by (day, order, start_time)
- New timetable routes in `app.py`:
  - `GET /api/timetable` - fetch weekly schedule
  - `GET /api/timetable/today` - today's classes
  - `POST /api/timetable/add` - add class manually
  - `POST /api/timetable/delete` - remove class
- Comprehensive calendar UI redesign in `dashboard.html`
  - 12-color subject palette for visual distinction
  - Event type badges (Lecture/Lab/Tutorial indicators)
  - Today highlighting with accent colors
  - Weekly grid view with subject colors
  - Dynamic color legend
  - Today's schedule sidebar
- Calendar rendering functions in JS:
  - `buildSubjectColorMap()` - create consistent color mapping
  - `renderSubjectLegend()` - dynamic legend with subjects and colors
  - `renderCalendar()` - 7-day grid layout
  - `renderTodaySchedule()` - formatted today's classes

#### Bug Fixes
- Fixed null/null attendance display
  - Backend: Added explicit `is not None` checks for attendance data
  - Frontend: Changed null/undefined comparison to `!= null`

#### Documentation
- Created comprehensive README.md
  - Feature overview with emoji categories
  - Requirements and installation guide
  - Usage instructions
  - Dashboard screen descriptions
  - API endpoint listing
  - Docker & Render deployment guides
- Created .env.example with detailed configuration
  - Database settings (MongoDB URI)
  - Security settings (SECRET_KEY, ENCRYPTION_KEY)
  - Application settings (FLASK_ENV, SESSION_TIMEOUT)
  - Auto-sync defaults
  - Target attendance configuration
  - Logging level selection
  - Deployment URL

#### Infrastructure
- Docker support
- Render.com deployment configuration
- Requirements.txt with all dependencies

### Changed
- Database functions updated for new timetable fields
- App.py routes now return event_type, color_class, order
- Calendar UI completely redesigned (CSS + HTML + JS)
- Improved visual hierarchy with glass-morphism components

### Fixed
- ERP calendar parsing (was using generic selectors)
- Calendar event display in dashboard
- Attendance calculation with null handling

### Initially Implemented (Prior Session)
- Flask authentication with session management
- Selenium-based ERP scraper
- Acharya ERP attendance extraction
- Smart bunk calculator
- Dark theme UI with glass-morphism
- Auto-sync scheduling
- MongoDB/JSON database abstraction
- Subject management features
- Responsive design

---

## [0.5.0] - Early Development

- Initial project scaffolding
- Basic authentication
- Attendance display
- Placeholder timetable feature
- Basic styling

---

## Notes

- All dates in format YYYY-MM-DD
- Version format: Major.Minor.Patch
  - Major: Breaking changes
  - Minor: New features (backward compatible)
  - Patch: Bug fixes
- Unreleased section tracks ongoing work
