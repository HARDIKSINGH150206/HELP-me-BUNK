# HELP-me-BUNK 📊

> Smart attendance management for college students. Track, analyze, and optimize your bunk strategies.

A modern web dashboard that scrapes **Acharya ERP** attendance data and provides intelligent recommendations on which classes are safe to skip while maintaining your target attendance.

## ✨ Features

### 📈 **Attendance Analytics**
- Real-time attendance tracking from Acharya ERP
- Subject-wise detailed breakdown (Present/Absent/Total)
- Overall attendance percentage with circular progress visualization
- Smart risk alerts for subjects below 75%

### 🎯 **Intelligent Bunk Calculator**
- Smart recommendations based on your timetable:
  - ✅ Which classes you can safely skip
  - ⚠️ How many classes you need to attend to reach 75%
  - 📊 Projected percentage if you attend/skip
- Safety buffer calculations (default 1% to ensure you stay above target)
- Status zones: Safe (≥85%), Warning (75-84%), At Risk (<75%)

### 📅 **Color-Coded Timetable**
- Automatic weekly schedule extraction from ERP calendar
- **12-color subject palette** for visual differentiation
- Event type indicators (Lecture/Lab/Tutorial)
- Per-class bunk status (safe to skip or must attend)
- Drag-click to delete classes
- Manual class addition with optional time slots

### 🤖 **Smart Features**
- **Auto-Sync**: Configure automatic ERP syncing (1/2/3 hourly intervals)
- **Timetable Integration**: Optimized recommendations based on remaining classes
- **Today's Schedule**: Prominent display of today's classes with attendance impact
- **Analytics Tabs**: 
  - Predictions (smart bunk analysis)
  - Trends (attendance charts over time)
  - Comparison (subject-wise bar charts)

### 🌙 **Modern UI/UX**
- Dark theme with glass-morphism Design (glassmorphic cards)
- Real-time data refresh without page reload (SPA)
- Responsive design (mobile, tablet, desktop)
- Smooth animations and transitions
- Accessibility-focused (high contrast, semantic HTML)

## 🛠️ Requirements

- **Python 3.10+**
- **Chrome/Chromium** browser (for Selenium scraping)
- **MongoDB** (optional - falls back to JSON storage)
- **Acharya ERP** student account
- **Node.js 14+** (optional - for frontend development)

## 📦 Installation

### 1. Clone & Setup
```bash
git clone https://github.com/HARDIKSINGH150206/HELP-me-BUNK.git
cd HELP-me-BUNK

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy and configure
cp .env.example .env

# Edit .env with your settings:
# - MONGODB_URI (optional, if using MongoDB)
# - SECRET_KEY (generate random: python3 -c "import secrets; print(secrets.token_hex(32))")
# - ENCRYPTION_KEY (for storing passwords: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 3. (Optional) MongoDB Setup
If using MongoDB instead of JSON storage:
```bash
# Create MongoDB Atlas cluster at https://www.mongodb.com/cloud/atlas
# Get connection string and add to .env as MONGODB_URI
# If no MongoDB, app automatically falls back to JSON storage (/local_db.json)
```

### 4. Run the Application
```bash
python3 app.py
# Opens at http://localhost:10000
```

## 🚀 Usage

### Web Dashboard
1. **Login**: Enter ERP username/password
2. **View Attendance**: Dashboard shows all subjects with status
3. **Sync with ERP**: Click "Refresh" to scrape latest attendance & timetable
4. **Check Calendar**: Switch to Calendar tab to see your weekly schedule
5. **Get Recommendations**: Read smart suggestions for each subject

### Auto-Sync Setup
1. Click "Auto" button in top-right
2. Toggle "Enable auto-sync"
3. Select interval (1hr, 2hrs, 3hrs)
4. System will automatically sync in background

### Manual Timetable Management
**Calendar → Add Class:**
- Subject name (required)
- Day of week (required)
- Class type: Lecture/Lab/Tutorial
- Start & end time (optional)

**Calendar → Paste Text:**
```
Monday: Math 9:00-10:00, Physics 10:00-11:00
Tuesday: Chemistry 9-10, English 11-12
```

## 📊 Dashboard Screens

### **Main Dashboard**
- **Circular Progress**: Overall attendance percentage
- **Status Breakdown**: Safe/Warning/At Risk count
- **Subject Grid**: Per-subject cards with:
  - Current percentage
  - Present/Absent/Total counts
  - Smart bunk recommendation
  - Progress bar with status color

### **Calendar View**
- **7-Day Grid** (Mon-Sun) with color-coded classes
- **Today Indicator** (⭐) on current day
- **Today's Schedule** section (if today has classes)
- **Per-Class Card:**
  - Subject name & color
  - Event type badge (LECTURE/LAB)
  - Bunk status (✓ safe to skip / ✗ must attend)
  - Attendance impact stats

### **Analytics Tabs**
- **Predictions**: Smart recommendations per subject
- **Trends**: Line charts of attendance over time
- **Comparison**: Subject-wise attendance bar chart

## 🔧 API Endpoints

Most endpoints require login (session cookie).

```
POST   /login                    → Login with ERP credentials
GET    /api/latest-data          → Get attendance & stats
GET    /api/timetable            → Get weekly schedule
GET    /api/timetable/today      → Get today's classes
POST   /api/timetable/add        → Add manual class
POST   /api/timetable/delete     → Remove class
POST   /api/timetable/paste      → Parse & add from text
POST   /api/auto-sync            → Trigger sync
POST   /api/logout               → Logout session
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -t help-me-bunk .

# Run container
docker run -p 10000:10000 \
  -e MONGODB_URI="your_mongodb_uri" \
  -e SECRET_KEY="your_secret_key" \
  help-me-bunk
```

## ☁️ Render Deployment

```bash
# App auto-deploys on git push to main branch
# Config in render.yaml
# Set environment variables in Render dashboard
```

```bash
python3 attendance_calculator.py
```

This will analyze your attendance and show:
- Current attendance percentage for each subject
- How many classes you can safely skip
- Which subjects need more attendance

## Sample Output

```
ATTENDANCE ANALYSIS & BUNK STRATEGY
======================================================================
Target: 75% (Safe Zone: 76%)

Mathematics for Computer Science
  Current: 23/53 (43.4%) ✗ DANGER
  Buffer: -31.6% from minimum
  → You need to attend 42 more classes to be safe!

ORIENTATION
  Current: 10/10 (100.0%) ✓ SAFE
  Buffer: +25.0% from minimum
  → You can safely bunk 3 more classes
```

## Files

| File | Description |
|------|-------------|
| `attendance_scraper.py` | ERP login and data extraction |
| `attendance_calculator.py` | Attendance analysis and recommendations |
| `attendance_sample.json` | Sample data format |

## Disclaimer

This tool is for educational purposes. Use responsibly - attendance policies exist for a reason!

## License

MIT
