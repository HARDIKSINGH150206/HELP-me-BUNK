#!/usr/bin/env python3
"""
Attendance Tracker Web Dashboard
Flask web application for monitoring college attendance
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import os
from datetime import datetime, timedelta
import glob
from attendance_calculator import AttendanceCalculator
import threading
import time

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Configuration file path
CONFIG_FILE = 'user_config.json'

# Store scraper status
scraper_status = {
    'running': False,
    'progress': '',
    'error': None,
    'complete': False
}

def run_scraper_background(username, password):
    """Run scraper in background thread"""
    global scraper_status
    from attendance_scraper import AcharyaERPScraper
    
    scraper_status['running'] = True
    scraper_status['progress'] = 'Initializing...'
    scraper_status['error'] = None
    scraper_status['complete'] = False
    
    try:
        scraper = AcharyaERPScraper(username, password)
        
        scraper_status['progress'] = 'Setting up browser...'
        scraper.setup_driver()
        
        scraper_status['progress'] = 'Logging in...'
        if not scraper.login():
            scraper_status['error'] = 'Login failed'
            scraper_status['running'] = False
            return
        
        scraper_status['progress'] = 'Navigating to attendance...'
        if not scraper.navigate_to_attendance():
            scraper_status['error'] = 'Navigation failed'
            scraper_status['running'] = False
            return
        
        scraper_status['progress'] = 'Extracting data...'
        data = scraper.extract_attendance_data()
        
        if data and len(data) > 0:
            scraper_status['progress'] = 'Saving data...'
            scraper.save_data(data)
            scraper_status['progress'] = 'Complete!'
            scraper_status['complete'] = True
        else:
            scraper_status['error'] = 'No data found'
        
        if scraper.driver:
            scraper.driver.quit()
            
    except Exception as e:
        scraper_status['error'] = str(e)
    finally:
        scraper_status['running'] = False


def load_config():
    """Load user configuration"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None


def save_config(config):
    """Save user configuration"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def calculate_working_days(start_date, end_date, enabled_days):
    """Calculate number of each weekday between two dates"""
    day_mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    enabled_weekdays = [day_mapping[day] for day in enabled_days]
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    day_counts = {day: 0 for day in enabled_days}
    
    current = start
    while current <= end:
        weekday = current.weekday()
        for day_name, day_num in day_mapping.items():
            if day_num == weekday and day_name in enabled_days:
                day_counts[day_name] += 1
        current += timedelta(days=1)
    
    return day_counts


def calculate_expected_classes(config):
    """Calculate expected total classes for each subject based on timetable"""
    timetable = config.get('timetable', {})
    start_date = config.get('semester_start')
    end_date = config.get('semester_end')
    
    if not timetable or not start_date or not end_date:
        return {}
    
    enabled_days = list(timetable.keys())
    day_counts = calculate_working_days(start_date, end_date, enabled_days)
    
    subject_classes = {}
    
    for day, subjects in timetable.items():
        if day not in day_counts:
            continue
        num_days = day_counts[day]
        for subject_info in subjects:
            subject_name = subject_info['subject']
            classes_per_day = subject_info['classes']
            
            if subject_name not in subject_classes:
                subject_classes[subject_name] = 0
            subject_classes[subject_name] += classes_per_day * num_days
    
    return subject_classes


def calculate_remaining_classes(config, today=None):
    """Calculate remaining classes from today to semester end"""
    if today is None:
        today = datetime.now().strftime('%Y-%m-%d')
    
    timetable = config.get('timetable', {})
    end_date = config.get('semester_end')
    
    if not timetable or not end_date:
        return {}
    
    enabled_days = list(timetable.keys())
    day_counts = calculate_working_days(today, end_date, enabled_days)
    
    subject_remaining = {}
    
    for day, subjects in timetable.items():
        if day not in day_counts:
            continue
        num_days = day_counts[day]
        for subject_info in subjects:
            subject_name = subject_info['subject']
            classes_per_day = subject_info['classes']
            
            if subject_name not in subject_remaining:
                subject_remaining[subject_name] = 0
            subject_remaining[subject_name] += classes_per_day * num_days
    
    return subject_remaining


@app.route('/')
def index():
    """Main entry - redirect to setup if not configured, else dashboard"""
    config = load_config()
    if config and config.get('setup_complete'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """Serve the dashboard page"""
    config = load_config()
    if not config or not config.get('setup_complete'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')


@app.route('/api/setup', methods=['POST'])
def setup():
    """Save user configuration from setup wizard"""
    try:
        data = request.json
        
        config = {
            'username': data.get('username'),
            'semester_start': data.get('semester_start'),
            'semester_end': data.get('semester_end'),
            'timetable': data.get('timetable', {}),
            'setup_complete': True,
            'created_at': datetime.now().isoformat()
        }
        
        save_config(config)
        
        # Optionally scrape initial data
        password = data.get('password')
        if password and config['username']:
            thread = threading.Thread(
                target=run_scraper_background, 
                args=(config['username'], password)
            )
            thread.daemon = True
            thread.start()
        
        return jsonify({'success': True, 'message': 'Setup complete!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
def get_config():
    """Get user configuration (without sensitive data)"""
    config = load_config()
    if config:
        # Remove sensitive fields
        safe_config = {
            'semester_start': config.get('semester_start'),
            'semester_end': config.get('semester_end'),
            'timetable': config.get('timetable', {}),
            'setup_complete': config.get('setup_complete', False)
        }
        return jsonify(safe_config)
    return jsonify({'setup_complete': False})


@app.route('/api/reset-config', methods=['POST'])
def reset_config():
    """Reset user configuration to start fresh"""
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        return jsonify({'success': True, 'message': 'Configuration reset'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/latest-data')
def get_latest_data():
    """Get the most recent attendance data with smart calculations"""
    try:
        # Find most recent attendance file
        files = glob.glob('attendance_*.json')
        if not files:
            return jsonify({'error': 'No data found. Please scrape first.'}), 404
        
        latest_file = max(files, key=os.path.getctime)
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # Load config for smart calculations
        config = load_config()
        expected_classes = {}
        remaining_classes = {}
        
        if config and config.get('setup_complete'):
            expected_classes = calculate_expected_classes(config)
            remaining_classes = calculate_remaining_classes(config)
        
        # Enhance subject data with smart calculations
        enhanced_subjects = []
        for subject in data['data']:
            enhanced = subject.copy()
            subject_name = subject.get('subject', '')
            present = subject.get('present', 0)
            total = subject.get('total', 0)
            current_pct = subject.get('percentage', 0)
            
            # Get remaining classes for this subject from timetable
            remaining = remaining_classes.get(subject_name, 0)
            expected_total = expected_classes.get(subject_name, 0)
            
            # Calculate classes needed to reach 75%
            # Formula: (present + x) / (total + remaining) >= 0.75
            # Solving: x >= 0.75 * (total + remaining) - present
            if remaining > 0:
                target_attendance = 0.75
                total_future = total + remaining
                needed = int(target_attendance * total_future) - present
                
                # Ensure needed is at least 0 and at most remaining
                needed = max(0, min(needed, remaining))
                
                # Calculate projected percentage if attending all remaining
                projected_pct = ((present + remaining) / total_future) * 100 if total_future > 0 else 0
                
                # Calculate can skip count
                can_skip = remaining - needed if needed <= remaining else 0
                
                enhanced['remaining_classes'] = remaining
                enhanced['classes_needed_75'] = needed
                enhanced['can_skip'] = can_skip
                enhanced['projected_percentage'] = round(projected_pct, 2)
                enhanced['expected_total_semester'] = expected_total
            else:
                enhanced['remaining_classes'] = 0
                enhanced['classes_needed_75'] = 0
                enhanced['can_skip'] = 0
                enhanced['projected_percentage'] = current_pct
                enhanced['expected_total_semester'] = expected_total
            
            enhanced_subjects.append(enhanced)
        
        # Calculate statistics
        total_subjects = len(enhanced_subjects)
        safe_subjects = sum(1 for s in enhanced_subjects if s['percentage'] >= 75)
        danger_subjects = sum(1 for s in enhanced_subjects if s['percentage'] < 75)
        
        # Calculate OVERALL attendance (total present / total classes) - not average of percentages
        total_present_all = sum(s['present'] for s in enhanced_subjects)
        total_classes_all = sum(s['total'] for s in enhanced_subjects)
        overall_attendance = (total_present_all / total_classes_all * 100) if total_classes_all > 0 else 0
        
        # Semester info
        semester_info = None
        if config and config.get('setup_complete'):
            semester_info = {
                'start': config.get('semester_start'),
                'end': config.get('semester_end'),
                'has_timetable': bool(config.get('timetable'))
            }
        
        return jsonify({
            'success': True,
            'timestamp': data.get('date', data.get('timestamp')),
            'subjects': enhanced_subjects,
            'stats': {
                'total': total_subjects,
                'safe': safe_subjects,
                'danger': danger_subjects,
                'average': round(overall_attendance, 2),
                'total_present': total_present_all,
                'total_classes': total_classes_all
            },
            'semester_info': semester_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calculate', methods=['POST'])
def calculate_bunks():
    """Calculate bunk strategy"""
    try:
        future_classes = int(request.json.get('future_classes', 20))
        
        # Find most recent attendance file
        files = glob.glob('attendance_*.json')
        if not files:
            return jsonify({'error': 'No data found'}), 404
        
        latest_file = max(files, key=os.path.getctime)
        
        calculator = AttendanceCalculator(target_percentage=75.0, safety_buffer=1.0)
        calculator.load_data(latest_file)
        
        results = []
        for subject in calculator.attendance_data:
            name = subject.get('subject', 'Unknown')
            present = subject.get('present', 0)
            total = subject.get('total', 0)
            
            analysis = calculator.calculate_bunk_allowance(present, total, future_classes)
            analysis['subject'] = name
            results.append(analysis)
        
        return jsonify({
            'success': True,
            'results': results,
            'future_classes': future_classes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    """Start scraping process"""
    try:
        username = request.json.get('username')
        password = request.json.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Start scraper in background thread
        thread = threading.Thread(target=run_scraper_background, args=(username, password))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Scraping started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape-status')
def scrape_status():
    """Get current scraping status"""
    return jsonify(scraper_status)


@app.route('/api/update-attendance', methods=['POST'])
def update_attendance():
    """Manually update attendance data for a subject"""
    try:
        data = request.json
        subject_name = data.get('subject')
        new_present = data.get('present')
        new_total = data.get('total')
        
        if not subject_name or new_present is None or new_total is None:
            return jsonify({'error': 'Subject name, present, and total are required'}), 400
        
        new_present = int(new_present)
        new_total = int(new_total)
        
        if new_total <= 0:
            return jsonify({'error': 'Total must be greater than 0'}), 400
        
        if new_present < 0 or new_present > new_total:
            return jsonify({'error': 'Present must be between 0 and total'}), 400
        
        # Find the most recent attendance file
        files = glob.glob('attendance_*.json')
        if not files:
            return jsonify({'error': 'No attendance data found'}), 404
        
        latest_file = max(files, key=os.path.getctime)
        
        # Load and update the data
        with open(latest_file, 'r') as f:
            attendance_data = json.load(f)
        
        # Find and update the subject
        found = False
        for subject in attendance_data['data']:
            if subject['subject'] == subject_name:
                subject['present'] = new_present
                subject['total'] = new_total
                subject['percentage'] = round((new_present / new_total) * 100, 2)
                found = True
                break
        
        if not found:
            return jsonify({'error': f'Subject "{subject_name}" not found'}), 404
        
        # Update timestamp
        attendance_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        attendance_data['last_modified'] = 'manual'
        
        # Save the updated data
        with open(latest_file, 'w') as f:
            json.dump(attendance_data, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Updated {subject_name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add-subject', methods=['POST'])
def add_subject():
    """Add a new subject to attendance data"""
    try:
        data = request.json
        subject_name = data.get('subject')
        present = int(data.get('present', 0))
        total = int(data.get('total', 0))
        
        if not subject_name or total <= 0:
            return jsonify({'error': 'Valid subject name and total required'}), 400
        
        files = glob.glob('attendance_*.json')
        if not files:
            # Create new file if none exists
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"attendance_{timestamp}.json"
            attendance_data = {
                'timestamp': timestamp,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'source': 'Manual Entry',
                'data': []
            }
        else:
            latest_file = max(files, key=os.path.getctime)
            with open(latest_file, 'r') as f:
                attendance_data = json.load(f)
            filename = latest_file
        
        # Check if subject already exists
        for subject in attendance_data['data']:
            if subject['subject'].lower() == subject_name.lower():
                return jsonify({'error': 'Subject already exists'}), 400
        
        # Add the new subject
        percentage = round((present / total) * 100, 2) if total > 0 else 0
        attendance_data['data'].append({
            'subject': subject_name,
            'present': present,
            'total': total,
            'percentage': percentage
        })
        
        with open(filename, 'w') as f:
            json.dump(attendance_data, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Added {subject_name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-subject', methods=['POST'])
def delete_subject():
    """Delete a subject from attendance data"""
    try:
        subject_name = request.json.get('subject')
        
        if not subject_name:
            return jsonify({'error': 'Subject name required'}), 400
        
        files = glob.glob('attendance_*.json')
        if not files:
            return jsonify({'error': 'No attendance data found'}), 404
        
        latest_file = max(files, key=os.path.getctime)
        
        with open(latest_file, 'r') as f:
            attendance_data = json.load(f)
        
        # Find and remove the subject
        original_length = len(attendance_data['data'])
        attendance_data['data'] = [s for s in attendance_data['data'] if s['subject'] != subject_name]
        
        if len(attendance_data['data']) == original_length:
            return jsonify({'error': f'Subject "{subject_name}" not found'}), 404
        
        with open(latest_file, 'w') as f:
            json.dump(attendance_data, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Deleted {subject_name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("="*70)
    print("ATTENDANCE TRACKER WEB DASHBOARD")
    print("="*70)
    print("\nStarting server...")
    print("Open your browser and go to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("="*70)
    app.run(debug=True, host='0.0.0.0', port=5000)
