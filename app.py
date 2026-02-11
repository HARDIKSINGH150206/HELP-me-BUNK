#!/usr/bin/env python3
"""
HELP-me-BUNK Web Dashboard
Flask web application for monitoring college attendance
Multi-user support with MongoDB database
"""

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import json
import os
from datetime import datetime, timedelta
import glob
from attendance_calculator import AttendanceCalculator
import threading
import time
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.permanent_session_lifetime = timedelta(days=7)

# Initialize database
try:
    db.init_db()
except Exception as e:
    print(f"⚠ Database initialization failed: {e}")
    print("  Make sure MONGODB_URI environment variable is set correctly")

# Store scraper status per user
scraper_status = {}


def get_scraper_status(user_id):
    """Get scraper status for a specific user"""
    if user_id not in scraper_status:
        scraper_status[user_id] = {
            'running': False,
            'progress': '',
            'error': None,
            'complete': False
        }
    return scraper_status[user_id]


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Not logged in'}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def run_scraper_background(user_id, username, password):
    """Run scraper in background thread"""
    from attendance_scraper import AcharyaERPScraper
    
    status = get_scraper_status(user_id)
    status['running'] = True
    status['progress'] = 'Initializing...'
    status['error'] = None
    status['complete'] = False
    
    try:
        scraper = AcharyaERPScraper(username, password)
        
        status['progress'] = 'Setting up browser...'
        scraper.setup_driver()
        
        status['progress'] = 'Logging in...'
        if not scraper.login():
            status['error'] = 'Login failed'
            status['running'] = False
            return
        
        status['progress'] = 'Navigating to attendance...'
        if not scraper.navigate_to_attendance():
            status['error'] = 'Navigation failed'
            status['running'] = False
            return
        
        status['progress'] = 'Extracting data...'
        data = scraper.extract_attendance_data()
        
        if data and len(data) > 0:
            status['progress'] = 'Saving data...'
            # Save to database instead of file
            subjects = []
            for item in data:
                subjects.append({
                    'subject': item.get('subject'),
                    'present': item.get('present', 0),
                    'total': item.get('total', 0)
                })
            db.save_attendance(user_id, subjects)
            status['progress'] = 'Complete!'
            status['complete'] = True
        else:
            status['error'] = 'No data found'
        
        if scraper.driver:
            scraper.driver.quit()
            
    except Exception as e:
        status['error'] = str(e)
    finally:
        status['running'] = False


def get_user_config(user_id):
    """Get configuration for a user from database"""
    user = db.get_user(user_id)
    if user:
        return {
            'erp_username': user.get('erp_username'),
            'semester_start': user.get('semester_start'),
            'semester_end': user.get('semester_end'),
            'target_percentage': user.get('target_percentage', 75),
            'setup_complete': bool(user.get('semester_start') and user.get('semester_end'))
        }
    return None


# ============== ROUTES ==============

@app.route('/')
def index():
    """Main entry - redirect to dashboard if logged in, else login page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """Serve the dashboard page"""
    return render_template('dashboard.html')


@app.route('/logout')
def logout():
    """Log out the current user"""
    session.clear()
    return redirect(url_for('index'))


# ============== AUTH ROUTES ==============

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if len(password) < 4:
            return jsonify({'error': 'Password must be at least 4 characters'}), 400
        
        result = db.create_user(username, password)
        
        if result['success']:
            # Auto-login after registration
            session.permanent = True
            session['user_id'] = result['user_id']
            session['username'] = username
            return jsonify({'success': True, 'message': 'Account created'})
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Log in a user"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        result = db.verify_user(username, password)
        
        if result['success']:
            session.permanent = True
            session['user_id'] = result['user_id']
            session['username'] = result['username']
            
            # Check if user has setup complete
            config = get_user_config(result['user_id'])
            has_setup = config and config.get('setup_complete')
            
            return jsonify({
                'success': True, 
                'message': 'Logged in',
                'has_setup': has_setup
            })
        else:
            return jsonify({'error': result['error']}), 401
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/setup', methods=['POST'])
@login_required
def setup():
    """Save user configuration from setup wizard"""
    try:
        data = request.json
        user_id = session['user_id']
        
        # Update user config in database
        db.update_user_config(
            user_id,
            erp_username=data.get('username'),
            semester_start=data.get('semester_start'),
            semester_end=data.get('semester_end')
        )
        
        # Optionally scrape initial data
        erp_username = data.get('username')
        password = data.get('password')
        if password and erp_username:
            thread = threading.Thread(
                target=run_scraper_background, 
                args=(user_id, erp_username, password)
            )
            thread.daemon = True
            thread.start()
        
        return jsonify({'success': True, 'message': 'Setup complete!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
@login_required
def get_config():
    """Get user configuration (without sensitive data)"""
    user_id = session['user_id']
    config = get_user_config(user_id)
    if config:
        return jsonify({
            'semester_start': config.get('semester_start'),
            'semester_end': config.get('semester_end'),
            'target_percentage': config.get('target_percentage', 75),
            'setup_complete': config.get('setup_complete', False),
            'username': session.get('username')
        })
    return jsonify({'setup_complete': False})


@app.route('/api/reset-config', methods=['POST'])
@login_required
def reset_config():
    """Reset user configuration to start fresh"""
    try:
        user_id = session['user_id']
        # Clear user's attendance data
        attendance = db.get_attendance(user_id)
        for subject in attendance:
            db.delete_subject(user_id, subject['subject'])
        # Reset user config
        db.update_user_config(user_id, semester_start=None, semester_end=None)
        return jsonify({'success': True, 'message': 'Configuration reset'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/latest-data')
@login_required
def get_latest_data():
    """Get the most recent attendance data for the logged-in user"""
    try:
        user_id = session['user_id']
        
        # Get attendance from database
        attendance_data = db.get_attendance(user_id)
        
        if not attendance_data:
            return jsonify({'error': 'No data found. Please add subjects or scrape from ERP.'}), 404
        
        # Load config for semester info
        config = get_user_config(user_id)
        target_pct = config.get('target_percentage', 75) if config else 75
        
        # Enhance subject data
        enhanced_subjects = []
        for subject in attendance_data:
            enhanced = {
                'subject': subject.get('subject'),
                'present': subject.get('present', 0),
                'total': subject.get('total', 0),
                'percentage': subject.get('percentage', 0)
            }
            
            present = enhanced['present']
            total = enhanced['total']
            current_pct = enhanced['percentage']
            
            # Basic calculations (no timetable in multi-user version for simplicity)
            enhanced['remaining_classes'] = 0
            enhanced['classes_needed_75'] = 0
            enhanced['can_skip'] = 0
            enhanced['projected_percentage'] = current_pct
            enhanced['expected_total_semester'] = 0
            
            enhanced_subjects.append(enhanced)
        
        # Calculate statistics
        total_subjects = len(enhanced_subjects)
        safe_subjects = sum(1 for s in enhanced_subjects if s['percentage'] >= target_pct)
        danger_subjects = sum(1 for s in enhanced_subjects if s['percentage'] < target_pct)
        
        # Calculate OVERALL attendance (total present / total classes)
        total_present_all = sum(s['present'] for s in enhanced_subjects)
        total_classes_all = sum(s['total'] for s in enhanced_subjects)
        overall_attendance = (total_present_all / total_classes_all * 100) if total_classes_all > 0 else 0
        
        # Get last scrape time
        last_scrape = db.get_last_scrape(user_id)
        
        # Semester info
        semester_info = None
        if config and config.get('setup_complete'):
            semester_info = {
                'start': config.get('semester_start'),
                'end': config.get('semester_end'),
                'has_timetable': False
            }
        
        return jsonify({
            'success': True,
            'timestamp': last_scrape or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
@login_required
def calculate_bunks():
    """Calculate bunk strategy"""
    try:
        user_id = session['user_id']
        future_classes = int(request.json.get('future_classes', 20))
        
        # Get attendance from database
        attendance_data = db.get_attendance(user_id)
        if not attendance_data:
            return jsonify({'error': 'No data found'}), 404
        
        calculator = AttendanceCalculator(target_percentage=75.0, safety_buffer=1.0)
        
        results = []
        for subject in attendance_data:
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
@login_required
def start_scrape():
    """Start scraping process"""
    try:
        user_id = session['user_id']
        username = request.json.get('username')
        password = request.json.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Start scraper in background thread
        thread = threading.Thread(target=run_scraper_background, args=(user_id, username, password))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Scraping started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scrape-status')
@login_required
def scrape_status_route():
    """Get current scraping status"""
    user_id = session['user_id']
    return jsonify(get_scraper_status(user_id))


@app.route('/api/update-attendance', methods=['POST'])
@login_required
def update_attendance():
    """Manually update attendance data for a subject"""
    try:
        user_id = session['user_id']
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
        
        # Update in database
        db.update_subject(user_id, subject_name, new_present, new_total)
        
        return jsonify({'success': True, 'message': f'Updated {subject_name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add-subject', methods=['POST'])
@login_required
def add_subject_route():
    """Add a new subject to attendance data"""
    try:
        user_id = session['user_id']
        data = request.json
        subject_name = data.get('subject')
        present = int(data.get('present', 0))
        total = int(data.get('total', 0))
        
        if not subject_name or total <= 0:
            return jsonify({'error': 'Valid subject name and total required'}), 400
        
        result = db.add_subject(user_id, subject_name, present, total)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'Added {subject_name}'})
        else:
            return jsonify({'error': result['error']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-subject', methods=['POST'])
@login_required
def delete_subject_route():
    """Delete a subject from attendance data"""
    try:
        user_id = session['user_id']
        subject_name = request.json.get('subject')
        
        if not subject_name:
            return jsonify({'error': 'Subject name required'}), 400
        
        deleted = db.delete_subject(user_id, subject_name)
        
        if deleted:
            return jsonify({'success': True, 'message': f'Deleted {subject_name}'})
        else:
            return jsonify({'error': f'Subject "{subject_name}" not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============== TIMETABLE ROUTES ==============

@app.route('/api/timetable')
@login_required
def get_timetable_route():
    """Get user's timetable with bunkability info"""
    try:
        user_id = session['user_id']
        
        # Get timetable entries
        timetable = db.get_timetable(user_id)
        
        # Get attendance data to calculate bunkability
        attendance = db.get_attendance(user_id)
        attendance_map = {s['subject']: s for s in attendance}
        
        # Get user's target percentage
        config = get_user_config(user_id)
        target_pct = config.get('target_percentage', 75) if config else 75
        
        # Enhance timetable with bunkability
        enhanced_timetable = []
        for entry in timetable:
            subject = entry.get('subject', '')
            
            # Find matching attendance record
            att = None
            for att_subject, att_data in attendance_map.items():
                if subject.lower() in att_subject.lower() or att_subject.lower() in subject.lower():
                    att = att_data
                    break
            
            can_bunk = False
            current_pct = 0
            classes_to_spare = 0
            
            if att:
                present = att.get('present', 0)
                total = att.get('total', 0)
                current_pct = att.get('percentage', 0)
                
                # Calculate if can bunk: (present / total+1) >= target
                if total > 0:
                    pct_if_skip = (present / (total + 1)) * 100
                    can_bunk = pct_if_skip >= target_pct
                    
                    # Calculate how many classes can be skipped
                    # present / (total + x) >= target/100
                    # present >= (target/100) * (total + x)
                    # x <= (present * 100 / target) - total
                    if target_pct > 0:
                        classes_to_spare = int((present * 100 / target_pct) - total)
                        classes_to_spare = max(0, classes_to_spare)
            
            enhanced_timetable.append({
                'subject': subject,
                'day': entry.get('day'),
                'day_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][entry.get('day', 0)] if entry.get('day') is not None else 'Unknown',
                'start_time': entry.get('start_time'),
                'end_time': entry.get('end_time'),
                'can_bunk': can_bunk,
                'current_pct': current_pct,
                'classes_to_spare': classes_to_spare
            })
        
        return jsonify({
            'success': True,
            'timetable': enhanced_timetable,
            'target_percentage': target_pct
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable/add', methods=['POST'])
@login_required
def add_timetable_entry_route():
    """Add a timetable entry manually"""
    try:
        user_id = session['user_id']
        data = request.json
        
        subject = data.get('subject', '').strip()
        day = data.get('day')  # 0-6
        start_time = data.get('start_time', '').strip()
        end_time = data.get('end_time', '').strip()
        
        if not subject or day is None or not start_time or not end_time:
            return jsonify({'error': 'All fields required: subject, day, start_time, end_time'}), 400
        
        result = db.add_timetable_entry(user_id, subject, day, start_time, end_time)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable/delete', methods=['POST'])
@login_required
def delete_timetable_entry_route():
    """Delete a timetable entry"""
    try:
        user_id = session['user_id']
        data = request.json
        
        subject = data.get('subject')
        day = data.get('day')
        start_time = data.get('start_time')
        
        if not all([subject, day is not None, start_time]):
            return jsonify({'error': 'Subject, day, and start_time required'}), 400
        
        deleted = db.delete_timetable_entry(user_id, subject, day, start_time)
        
        if deleted:
            return jsonify({'success': True, 'message': 'Entry deleted'})
        else:
            return jsonify({'error': 'Entry not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable/clear', methods=['POST'])
@login_required
def clear_timetable_route():
    """Clear all timetable entries"""
    try:
        user_id = session['user_id']
        db.clear_timetable(user_id)
        return jsonify({'success': True, 'message': 'Timetable cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable/save', methods=['POST'])
@login_required
def save_timetable_route():
    """Save multiple timetable entries (bulk save)"""
    try:
        user_id = session['user_id']
        data = request.json
        
        entries = data.get('entries', [])
        
        if not entries:
            return jsonify({'error': 'No entries provided'}), 400
        
        db.save_timetable(user_id, entries)
        return jsonify({'success': True, 'message': f'Saved {len(entries)} entries'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("="*70)
    print("HELP-me-BUNK WEB DASHBOARD")
    print("="*70)
    print("\nStarting server...")
    print("Open your browser and go to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("="*70)
    app.run(debug=True, host='0.0.0.0', port=5000)
