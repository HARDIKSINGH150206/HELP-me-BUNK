# Contributing to HELP-me-BUNK

We appreciate contributions! Here's how to get involved.

## 📋 Code of Conduct

- Be respectful and inclusive
- Focus on the project goals
- Provide constructive feedback
- Help others learn and grow

## 🔧 Development Setup

### Prerequisites
- Python 3.10+
- Chrome/Chromium
- Git

### Setup Steps
```bash
# Clone and setup
git clone https://github.com/HARDIKSINGH150206/HELP-me-BUNK.git
cd HELP-me-BUNK

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values (at minimum SECRET_KEY)

# Run validation
python3 startup_check.py

# Start dev server
python3 app.py
```

## 📁 Project Structure

```
HELP-me-BUNK/
├── app.py                          # Main Flask application
├── attendance_scraper.py           # Selenium ERP scraper
├── attendance_calculator.py        # Smart bunk logic
├── database.py                     # DB abstraction (MongoDB/JSON)
├── scheduler.py                    # Background task scheduling
├── startup_check.py                # Pre-flight validation
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker configuration
├── render.yaml                     # Render.com deployment config
├── templates/
│   ├── login.html                  # Login page
│   ├── dashboard.html              # Main dashboard (3800+ lines)
│   └── playground-*.js            # MongoDB test files
├── frontend/                       # (Optional) React/Vue setup
└── README.md                       # Project documentation
```

## 🎯 Key Components

### 1. **app.py** (Flask Server)
- Login/logout handling
- API endpoints for attendance, timetable, config
- Auto-sync scheduling
- Session management

**Key Routes:**
```python
GET    /api/latest-data             # Attendance data
GET    /api/timetable               # Weekly schedule
POST   /api/timetable/add           # Add class
POST   /api/auto-sync               # Manual sync
```

### 2. **attendance_scraper.py** (Selenium)
- Logs into Acharya ERP
- Extracts attendance data
- Scrapes calendar for weekly timetable
- Returns structured data

**Key Methods:**
```python
scraper.login(username, password)
scraper.extract_attendance_data()     # Returns dict with subjects
scraper.extract_timetable_data()      # Returns list of classes
```

### 3. **attendance_calculator.py** (Logic)
- Calculates if safe to bunk
- Predicts final percentage
- Determines classes needed for target

**Key Methods:**
```python
calc.can_bunk_class(subject, present, total)
calc.can_reach_target(present, total)
calc.remaining_after(skip_count)
```

### 4. **database.py** (Data Layer)
- MongoDB primary, JSON fallback
- CRUD operations for attendance, users, timetable
- Automatic fallback if MongoDB unavailable

**Key Functions:**
```python
db.save_attendance(user_id, subjects)
db.get_timetable(user_id)
db.save_erp_overall(user_id, data)
```

## 🔐 Security Considerations

### Input Validation
All user input must be sanitized:
```python
from app import sanitize_string, validate_integer

# In your route:
subject = sanitize_string(request.json.get('subject'))
day = validate_day_of_week(request.json.get('day'))
if not subject or day is None:
    return jsonify({'error': 'Invalid input'}), 400
```

### Authentication
- Session-based (Flask session)
- Password stored encrypted (Fernet)
- Login required decorator: `@login_required`

### Environment Variables
- Never commit `.env` file
- Use `.env.example` for documentation
- Access via `os.getenv('VAR_NAME')`

## 🐛 Common Issues & Fixes

### Chrome/Chromium Not Found
```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser

# macOS
brew install chromium

# Windows
# Download from https://www.chromium.org/getting-involved/download-chromium
```

### MongoDB Connection Failed
```bash
# Falls back to JSON automatically
# Check MONGODB_URI in .env
# Ensure IP whitelist includes your connection
```

### Port Already in Use
```bash
# Change port in app.py:
if __name__ == '__main__':
    app.run(port=5000)  # Change from 10000
```

## 📝 Coding Standards

### Style Guide
- Use 4-space indentation
- Name functions/variables `like_this`
- Name constants `LIKE_THIS`
- Use type hints where possible

### Example Function
```python
def validate_attendance(subject: str, present: int, total: int) -> bool:
    """
    Validate attendance data format.
    
    Args:
        subject: Subject name (max 255 chars)
        present: Classes attended (0-999)
        total: Total classes (1-999)
    
    Returns:
        True if valid, False otherwise
    """
    subject = sanitize_string(subject)
    present = validate_integer(present, min_val=0, max_val=999)
    total = validate_integer(total, min_val=1, max_val=999)
    
    return subject is not None and present is not None and total is not None
```

### Docstrings
```python
def my_function(param1, param2):
    """
    Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this happens
    """
```

## 🧪 Testing

### Manual Testing
```bash
# Test login flow
curl -X POST http://localhost:10000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'

# Test API
curl http://localhost:10000/api/latest-data \
  -H "Cookie: session=your_session_id"
```

### Adding Unit Tests
```python
# tests/test_calculator.py
import unittest
from attendance_calculator import AttendanceCalculator

class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = AttendanceCalculator()
    
    def test_can_bunk_when_safe(self):
        # Arrange: 90% attendance, total 10 classes
        # Act: Check if can bunk
        # Assert: Should return True
        pass
```

## 📚 API Response Format

### Success Response
```json
{
  "success": true,
  "data": {...}
}
```

### Error Response
```json
{
  "error": "Descriptive error message",
  "status": 400
}
```

## 🚀 Making a Pull Request

1. **Fork & Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/HELP-me-BUNK.git
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Changes**
   - Keep commits focused and atomic
   - Write clear commit messages
   - Test locally: `python3 startup_check.py && python3 app.py`

4. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: Add amazing new feature"
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Clear title and description
   - Link related issues
   - Include testing notes

## 🐛 Reporting Issues

When reporting bugs, include:
- **Description**: What's not working?
- **Steps to Reproduce**: How to trigger the bug
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, Python version, Chrome version, etc.
- **Logs**: Error messages from console/startup_check.py

## 📦 Release Process

1. Update version in `app.py` (if applicable)
2. Update `CHANGELOG.md` (if exists)
3. Create git tag: `git tag v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. Create GitHub release with notes

## 📞 Getting Help

- Open an issue for bugs
- Start discussions for features
- Email: hardiksingh150206@gmail.com

## 📄 License

[Your License Here - e.g., MIT]

---

**Happy Contributing!** 🎉
