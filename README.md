# HELP-me-BUNK

A Python tool to scrape attendance data from Acharya ERP and calculate safe bunking strategies.

## Features

- **Attendance Scraper**: Automatically logs into Acharya ERP and extracts attendance data
- **Bunk Calculator**: Analyzes your attendance and tells you:
  - Which subjects are safe to bunk
  - How many classes you can skip while staying above 75%
  - Which subjects need urgent attention

## Requirements

- Python 3.10+
- Chrome or Chromium browser
- Acharya ERP student account

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/attendance-project.git
cd attendance-project

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install selenium webdriver-manager colorama
```

## Usage

### Step 1: Scrape Attendance

```bash
source venv/bin/activate
python3 attendance_scraper.py
```

Enter your ERP credentials when prompted. The scraper will:
1. Open a browser window
2. Login to your ERP account
3. Navigate to the attendance page
4. Extract and save attendance data to a JSON file

### Step 2: Calculate Bunks

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
