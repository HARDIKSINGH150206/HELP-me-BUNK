#!/usr/bin/env python3
"""
HELP-me-BUNK Web Dashboard
Flask web application for monitoring college attendance
Multi-user support with MongoDB database
"""

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import json
import os
import math
from datetime import datetime, timedelta
import glob
import re
import io
import base64
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
from attendance_calculator import AttendanceCalculator
import threading
import time
import html
import logging

# ===== INPUT VALIDATION & SANITIZATION =====

def sanitize_string(value, max_length=255, allow_unicode=True):
    """Sanitize string input to prevent XSS
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length (truncates if exceeded)
        allow_unicode: Whether to allow Unicode characters
    
    Returns:
        Sanitized string or None if invalid
    """
    if not isinstance(value, str):
        return None
    
    # Remove leading/trailing whitespace
    value = value.strip()
    
    if not value:
        return None
    
    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]
    
    # Check for suspicious patterns BEFORE escaping
    # (so we catch real dangerous code, not escaped versions)
    dangerous_patterns = ['<script', 'javascript:', 'onclick', 'onerror', 'onload', '<%', '%>']
    if any(pattern in value.lower() for pattern in dangerous_patterns):
        return None
    
    # Escape HTML entities
    value = html.escape(value)
    
    return value

def validate_email(email):
    """Validate email format"""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def validate_integer(value, min_val=None, max_val=None):
    """Validate integer input"""
    try:
        val = int(value)
        if min_val is not None and val < min_val:
            return None
        if max_val is not None and val > max_val:
            return None
        return val
    except (TypeError, ValueError):
        return None

def validate_day_of_week(day):
    """Validate day of week (0=Monday, 6=Sunday)"""
    val = validate_integer(day, min_val=0, max_val=6)
    return val

def validate_time_format(time_str):
    """Validate HH:MM time format"""
    if not time_str or not isinstance(time_str, str):
        return False
    pattern = r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$'
    return re.match(pattern, time_str.strip()) is not None

def validate_percentage(value):
    """Validate percentage (0-100)
    
    Args:
        value: Value to validate as percentage
    
    Returns:
        Integer value (0-100) if valid, None otherwise
    """
    return validate_integer(value, min_val=0, max_val=100)

def require_json(f):
    """Decorator to ensure request has JSON content-type"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        return f(*args, **kwargs)
    return decorated_function

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
app.permanent_session_lifetime = timedelta(days=7)

# Enable CORS for Vercel frontend and development
CORS(app, 
    resources={r"/api/*": {
        "origins": [
            os.environ.get('FRONTEND_URL', 'http://localhost:3000'),
            "http://localhost:3000",
            "http://localhost:5000"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": True
    }},
    allow_headers=['Content-Type']
)

# Initialize database
try:
    db.init_db()
except Exception as e:
    print(f"⚠ Database initialization failed: {e}")
    print("  Make sure MONGODB_URI environment variable is set correctly")

# Initialize auto-sync scheduler
from scheduler import init_scheduler, schedule_user_sync, remove_user_sync, get_user_schedule, shutdown_scheduler
try:
    init_scheduler(app)
except Exception as e:
    print(f"⚠ Scheduler initialization failed: {e}")

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
        
        status['progress'] = 'Extracting attendance data...'
        data = scraper.extract_attendance_data()
        
        if data:
            status['progress'] = 'Saving attendance data...'
            # Handle new format: data is now {'subjects': [...], 'overall': {...}}
            if isinstance(data, dict) and 'subjects' in data:
                subjects_data = data['subjects']
                overall_data = data.get('overall')
            else:
                # Backwards compatibility for old format (list of subjects)
                subjects_data = data if isinstance(data, list) else []
                overall_data = None
            
            if subjects_data and len(subjects_data) > 0:
                subjects = []
                for item in subjects_data:
                    subjects.append({
                        'subject': item.get('subject'),
                        'present': item.get('present', 0),
                        'total': item.get('total', 0)
                    })
                db.save_attendance(user_id, subjects, overall=overall_data)
                status['progress'] = 'Attendance saved!'
            else:
                status['error'] = 'No subject data found'
        else:
            status['error'] = 'No attendance data found'
        
        # Now extract and save timetable
        status['progress'] = 'Extracting timetable...'
        if scraper.navigate_to_calendar():
            timetable_data = scraper.extract_timetable_data()
            if timetable_data and len(timetable_data) > 0:
                status['progress'] = f'Saving {len(timetable_data)} timetable entries...'
                try:
                    # Save all timetable entries at once (replaces old data)
                    db.save_timetable(user_id, timetable_data)
                    status['progress'] = 'Timetable saved!'
                except Exception as e:
                    print(f"⚠ Warning: Could not save some timetable entries: {e}")
            else:
                print("⚠ No timetable data found")
        else:
            print("⚠ Could not navigate to calendar page")
        
        status['complete'] = True
        
        if scraper.driver:
            scraper.driver.quit()
            
    except Exception as e:
        status['error'] = str(e)
        print(f"✗ Scraper error: {e}")
        import traceback
        traceback.print_exc()
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


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint to log out"""
    session.clear()
    return jsonify({'success': True})


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
        erp_username = data.get('username')
        password = data.get('password')
        
        # Update user config in database (including encrypted ERP password)
        db.update_user_config(
            user_id,
            erp_username=erp_username,
            erp_password=password,  # Will be encrypted by database layer
            semester_start=data.get('semester_start'),
            semester_end=data.get('semester_end')
        )
        
        # Start initial scrape with provided credentials
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
        # Get auto-sync schedule
        schedule = get_user_schedule(user_id)
        return jsonify({
            'semester_start': config.get('semester_start'),
            'semester_end': config.get('semester_end'),
            'target_percentage': config.get('target_percentage', 75),
            'setup_complete': config.get('setup_complete', False),
            'username': session.get('username'),
            'auto_sync_enabled': schedule.get('enabled', False),
            'auto_sync_interval': schedule.get('interval', 2),
            'auto_sync_next_run': schedule.get('next_run')
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
        # safe: >= 85%, warning: 75-85%, danger: < 75%
        total_subjects = len(enhanced_subjects)
        safe_subjects = sum(1 for s in enhanced_subjects if s['percentage'] >= 85)
        warning_subjects = sum(1 for s in enhanced_subjects if 75 <= s['percentage'] < 85)
        danger_subjects = sum(1 for s in enhanced_subjects if s['percentage'] < 75)
        
        # Calculate OVERALL attendance (same as ERP - total present / total classes)
        total_present_all = sum(s['present'] for s in enhanced_subjects)
        total_classes_all = sum(s['total'] for s in enhanced_subjects)
        
        # ERP formula: (total present across all subjects) / (total classes across all subjects) * 100
        if total_classes_all > 0:
            overall_attendance = (total_present_all / total_classes_all) * 100
        else:
            overall_attendance = 0
        
        # Get ERP overall attendance if available (scraped directly from ERP)
        erp_overall = db.get_erp_overall(user_id)
        
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
                'warning': warning_subjects,
                'danger': danger_subjects,
                'average': round(overall_attendance, 2),
                'total_present': total_present_all,
                'total_classes': total_classes_all
            },
            'erp_overall': {
                'present': erp_overall.get('present') if erp_overall and erp_overall.get('present') is not None else total_present_all,
                'total': erp_overall.get('total') if erp_overall and erp_overall.get('total') is not None else total_classes_all,
                'percentage': erp_overall.get('percentage') if erp_overall and erp_overall.get('percentage') is not None else round(overall_attendance, 2)
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
        
        # Also save/update the ERP credentials for future auto-sync
        db.update_user_config(user_id, erp_username=username, erp_password=password)
        
        # Start scraper in background thread
        thread = threading.Thread(target=run_scraper_background, args=(user_id, username, password))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Scraping started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auto-sync', methods=['POST'])
@login_required
def auto_sync():
    """Auto-sync with ERP using stored credentials"""
    try:
        user_id = session['user_id']
        
        # Get stored ERP credentials
        credentials = db.get_erp_credentials(user_id)
        
        if not credentials:
            return jsonify({
                'error': 'ERP credentials not configured',
                'needs_credentials': True
            }), 400
        
        # Check if scraper is already running
        status = get_scraper_status(user_id)
        if status.get('running'):
            return jsonify({'success': True, 'message': 'Sync already in progress'})
        
        # Start scraper in background thread
        thread = threading.Thread(
            target=run_scraper_background, 
            args=(user_id, credentials['username'], credentials['password'])
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Syncing with ERP...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auto-sync-schedule', methods=['GET'])
@login_required
def get_auto_sync_schedule():
    """Get current auto-sync schedule settings"""
    user_id = session['user_id']
    schedule = get_user_schedule(user_id)
    return jsonify(schedule)


@app.route('/api/auto-sync-schedule', methods=['POST'])
@login_required
def set_auto_sync_schedule():
    """Set auto-sync schedule (enable/disable, change interval)"""
    try:
        user_id = session['user_id']
        data = request.json
        enabled = data.get('enabled')
        interval = data.get('interval')  # hours: 1, 2, or 3

        if enabled is None:
            return jsonify({'error': 'enabled field is required'}), 400

        if enabled:
            # Check if ERP credentials exist
            credentials = db.get_erp_credentials(user_id)
            if not credentials:
                return jsonify({
                    'error': 'ERP credentials not configured. Set up your ERP credentials first.',
                    'needs_credentials': True
                }), 400

            interval = int(interval) if interval else 2
            if interval not in (1, 2, 3):
                return jsonify({'error': 'Interval must be 1, 2, or 3 hours'}), 400

            schedule_user_sync(user_id, interval)
            schedule = get_user_schedule(user_id)
            return jsonify({
                'success': True,
                'message': f'Auto-sync enabled every {interval} hours',
                **schedule
            })
        else:
            remove_user_sync(user_id)
            return jsonify({
                'success': True,
                'message': 'Auto-sync disabled',
                'enabled': False,
                'interval': 12,
                'next_run': None
            })
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
        data = request.json or {}
        
        # Validate and sanitize input
        subject_name = sanitize_string(data.get('subject', '').strip(), max_length=255)
        new_present = validate_integer(data.get('present'), min_val=0, max_val=999)
        new_total = validate_integer(data.get('total'), min_val=1, max_val=999)
        
        # Validate required fields
        if not subject_name:
            return jsonify({'error': 'Subject name is required'}), 400
        
        if new_present is None:
            return jsonify({'error': 'Present must be a valid integer (0-999)'}), 400
        
        if new_total is None:
            return jsonify({'error': 'Total must be a valid integer (1-999)'}), 400
        
        if new_total <= 0:
            return jsonify({'error': 'Total must be greater than 0'}), 400
        
        if new_present > new_total:
            return jsonify({'error': 'Present classes cannot exceed total classes'}), 400
        
        # Log the action
        app.logger.info(f"User {user_id} updating attendance for {subject_name}: {new_present}/{new_total}")
        
        # Update in database
        db.update_subject(user_id, subject_name, new_present, new_total)
        
        return jsonify({'success': True, 'message': f'Updated {subject_name}'})
    except Exception as e:
        app.logger.error(f"Error updating attendance: {e}")
        return jsonify({'error': 'Failed to update attendance'}), 500


@app.route('/api/add-subject', methods=['POST'])
@login_required
def add_subject_route():
    """Add a new subject to attendance data"""
    try:
        user_id = session['user_id']
        data = request.json or {}
        
        # Validate and sanitize input
        subject_name = sanitize_string(data.get('subject', '').strip(), max_length=255)
        present = validate_integer(data.get('present', 0), min_val=0, max_val=999)
        total = validate_integer(data.get('total', 0), min_val=1, max_val=999)
        
        # Validate required fields
        if not subject_name:
            return jsonify({'error': 'Subject name is required and must be 1-255 characters'}), 400
        
        if present is None or total is None:
            return jsonify({'error': 'Present and total must be valid integers (0-999)'}), 400
        
        if total <= 0:
            return jsonify({'error': 'Total classes must be greater than 0'}), 400
        
        if present > total:
            return jsonify({'error': 'Present classes cannot exceed total classes'}), 400
        
        # Log the action
        app.logger.info(f"User {user_id} adding subject: {subject_name} ({present}/{total})")
        
        result = db.add_subject(user_id, subject_name, present, total)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'Added {subject_name}'})
        else:
            return jsonify({'error': result['error']}), 400
    except Exception as e:
        app.logger.error(f"Error adding subject: {e}")
        return jsonify({'error': 'Failed to add subject'}), 500


@app.route('/api/delete-subject', methods=['POST'])
@login_required
def delete_subject_route():
    """Delete a subject from attendance data"""
    try:
        user_id = session['user_id']
        data = request.json or {}
        subject_name = sanitize_string(data.get('subject', '').strip(), max_length=255)
        
        if not subject_name:
            return jsonify({'error': 'Subject name is required'}), 400
        
        # Log the action
        app.logger.info(f"User {user_id} deleting subject: {subject_name}")
        
        deleted = db.delete_subject(user_id, subject_name)
        
        if deleted:
            return jsonify({'success': True, 'message': f'Deleted {subject_name}'})
        else:
            return jsonify({'error': f'Subject "{subject_name}" not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting subject: {e}")
        return jsonify({'error': 'Failed to delete subject'}), 500


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
                'event_type': entry.get('event_type', 'Lecture'),
                'color_class': entry.get('color_class', 'chart-7'),
                'order': entry.get('order', 0),
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


@app.route('/api/timetable/today')
@login_required
def get_today_schedule():
    """Get today's schedule with detailed bunk status for each class"""
    try:
        from datetime import datetime
        user_id = session['user_id']
        
        # Get today's day of week (0=Monday, 6=Sunday)
        today_day = datetime.now().weekday()
        
        # Get timetable entries for today
        timetable = db.get_timetable(user_id)
        today_classes = [t for t in timetable if t.get('day') == today_day]
        
        # Get attendance data
        attendance = db.get_attendance(user_id)
        attendance_map = {s['subject']: s for s in attendance}
        
        # Get user's target percentage
        config = get_user_config(user_id)
        target_pct = config.get('target_percentage', 75) if config else 75
        
        # Initialize calculator
        calculator = AttendanceCalculator(target_percentage=target_pct, safety_buffer=1.0)
        
        # Enhance with bunk analysis
        today_schedule = []
        for class_entry in today_classes:
            subject_name = class_entry.get('subject', '')
            
            # Find matching attendance record
            att = None
            for att_subject, att_data in attendance_map.items():
                if subject_name.lower() in att_subject.lower() or att_subject.lower() in subject_name.lower():
                    att = att_data
                    break
            
            if att:
                present = att.get('present', 0)
                total = att.get('total', 0)
                current_pct = att.get('percentage', 0)
                
                # Use the calculator to determine bunk status
                bunk_info = calculator.can_bunk_class(subject_name, present, total)
                
                today_schedule.append({
                    'subject': subject_name,
                    'start_time': class_entry.get('start_time'),
                    'end_time': class_entry.get('end_time'),
                    'event_type': class_entry.get('event_type', 'Lecture'),
                    'color_class': class_entry.get('color_class', 'chart-7'),
                    'order': class_entry.get('order', 0),
                    'current_percentage': bunk_info['current_percentage'],
                    'projected_percentage': bunk_info['projected_percentage'],
                    'can_bunk': bunk_info['can_bunk'],
                    'status': bunk_info['status'],  # SAFE, WARNING, or DANGER
                    'reason': bunk_info['reason'],
                    'buffer': bunk_info['buffer'],
                    'present': present,
                    'total': total
                })
            else:
                # No attendance data for this subject yet
                today_schedule.append({
                    'subject': subject_name,
                    'start_time': class_entry.get('start_time'),
                    'end_time': class_entry.get('end_time'),
                    'event_type': class_entry.get('event_type', 'Lecture'),
                    'color_class': class_entry.get('color_class', 'chart-7'),
                    'order': class_entry.get('order', 0),
                    'current_percentage': 0,
                    'projected_percentage': 0,
                    'can_bunk': False,
                    'status': 'NO_DATA',
                    'reason': 'No attendance data available for this subject',
                    'buffer': 0,
                    'present': 0,
                    'total': 0
                })
        
        # Sort by order (position in day), fallback to start_time
        today_schedule.sort(key=lambda x: (x.get('order', 0), x.get('start_time') or '00:00'))
        
        # Get summary stats for today
        safe_count = sum(1 for c in today_schedule if c['can_bunk'])
        danger_count = sum(1 for c in today_schedule if c['status'] == 'DANGER')
        warning_count = sum(1 for c in today_schedule if c['status'] == 'WARNING')
        no_data_count = sum(1 for c in today_schedule if c['status'] == 'NO_DATA')
        
        return jsonify({
            'success': True,
            'today': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'day_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][today_day],
                'day_of_week': today_day
            },
            'schedule': today_schedule,
            'summary': {
                'total_classes': len(today_schedule),
                'safe_to_bunk': safe_count,
                'dangerous_to_skip': danger_count,
                'warning_zone': warning_count,
                'no_data': no_data_count
            },
            'target_percentage': target_pct
        })
        
    except Exception as e:
        print(f"Error in get_today_schedule: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/timetable/add', methods=['POST'])
@login_required
def add_timetable_entry_route():
    """Add a timetable entry manually"""
    try:
        user_id = session['user_id']
        data = request.json or {}
        
        # Validate and sanitize input
        subject = sanitize_string(data.get('subject', '').strip(), max_length=255)
        day = validate_day_of_week(data.get('day'))
        start_time = data.get('start_time', '').strip() or None
        end_time = data.get('end_time', '').strip() or None
        event_type = sanitize_string(data.get('event_type', 'Lecture'), max_length=50)
        color_class = sanitize_string(data.get('color_class', 'chart-7'), max_length=50)
        order = validate_integer(data.get('order', 0), min_val=0, max_val=999)
        
        # Validate required fields
        if not subject:
            return jsonify({'error': 'Subject name is required and must be 1-255 characters'}), 400
        
        if day is None:
            return jsonify({'error': 'Day must be 0-6 (Monday-Sunday)'}), 400
        
        # Validate time formats if provided
        if start_time and not validate_time_format(start_time):
            return jsonify({'error': 'Invalid start_time format. Use HH:MM'}), 400
        
        if end_time and not validate_time_format(end_time):
            return jsonify({'error': 'Invalid end_time format. Use HH:MM'}), 400
        
        # Log the action
        app.logger.info(f"User {user_id} adding timetable entry: {subject} on day {day}")
        
        result = db.add_timetable_entry(user_id, subject, day, start_time, end_time,
                                         event_type=event_type, color_class=color_class, order=order)
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error adding timetable entry: {e}")
        return jsonify({'error': 'Failed to add timetable entry'}), 500


@app.route('/api/timetable/delete', methods=['POST'])
@login_required
def delete_timetable_entry_route():
    """Delete a timetable entry"""
    try:
        user_id = session['user_id']
        data = request.json or {}
        
        # Validate and sanitize input
        subject = sanitize_string(data.get('subject', '').strip(), max_length=255)
        day = validate_day_of_week(data.get('day'))
        order = validate_integer(data.get('order'), min_val=0, max_val=999)
        
        # Validate required fields
        if not subject:
            return jsonify({'error': 'Subject name is required'}), 400
        
        if day is None:
            return jsonify({'error': 'Day must be 0-6 (Monday-Sunday)'}), 400
        
        if order is None:
            return jsonify({'error': 'Order must be a valid number (0-999)'}), 400
        
        # Log the action
        app.logger.info(f"User {user_id} deleting timetable entry: {subject} on day {day}")
        
        deleted = db.delete_timetable_entry(user_id, subject, day, order=order)
        
        if deleted:
            return jsonify({'success': True, 'message': 'Entry deleted'})
        else:
            return jsonify({'error': 'Entry not found'}), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting timetable entry: {e}")
        return jsonify({'error': 'Failed to delete timetable entry'}), 500


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


@app.route('/api/timetable/paste', methods=['POST'])
@login_required
def paste_timetable():
    """Parse timetable from pasted text format.
    
    Supported formats:
    - Monday: Math 9:00-10:00, Physics 10:00-11:00
    - Mon: Math 9-10, Physics 10-11
    - Monday 9:00 Math
    """
    try:
        user_id = session['user_id']
        data = request.json
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text'].strip()
        entries = parse_pasted_timetable(text)
        
        # Save entries
        saved_count = 0
        for entry in entries:
            try:
                db.add_timetable_entry(
                    user_id,
                    entry['subject'],
                    entry['day'],
                    entry['start_time'],
                    entry['end_time']
                )
                saved_count += 1
            except:
                pass  # Skip duplicates
        
        return jsonify({
            'success': True,
            'entries_found': len(entries),
            'entries_saved': saved_count,
            'entries': entries
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def parse_pasted_timetable(text):
    """Parse user-pasted timetable text."""
    entries = []
    lines = text.strip().split('\n')
    
    day_map = {
        'monday': 0, 'mon': 0, 'm': 0,
        'tuesday': 1, 'tue': 1, 'tu': 1,
        'wednesday': 2, 'wed': 2, 'w': 2,
        'thursday': 3, 'thu': 3, 'th': 3,
        'friday': 4, 'fri': 4, 'f': 4,
        'saturday': 5, 'sat': 5, 's': 5,
        'sunday': 6, 'sun': 6
    }
    
    # Time pattern: 9:00, 09:00, 9, 9am, 9:00am
    time_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', re.IGNORECASE)
    # Time range pattern: 9:00-10:00, 9-10, 9am-10am
    range_pattern = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-–to]+\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', re.IGNORECASE)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Find day in line
        current_day = None
        line_lower = line.lower()
        
        for day_name, day_idx in day_map.items():
            # Check if line starts with day name or has day: format
            if line_lower.startswith(day_name) or re.match(r'\b' + day_name + r'\b\s*[:\-]?', line_lower):
                current_day = day_idx
                # Remove day from line
                line = re.sub(r'(?i)^\s*' + day_name + r'\s*[:\-]?\s*', '', line)
                break
        
        if current_day is None:
            continue
        
        # Split by comma for multiple classes on same day
        parts = re.split(r'[,;]', line)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Find time range
            range_match = range_pattern.search(part)
            if range_match:
                start_h = int(range_match.group(1))
                start_m = range_match.group(2) or '00'
                start_ampm = range_match.group(3)
                end_h = int(range_match.group(4))
                end_m = range_match.group(5) or '00'
                end_ampm = range_match.group(6)
                
                # Handle AM/PM
                if start_ampm and start_ampm.lower() == 'pm' and start_h < 12:
                    start_h += 12
                elif start_ampm and start_ampm.lower() == 'am' and start_h == 12:
                    start_h = 0
                if end_ampm and end_ampm.lower() == 'pm' and end_h < 12:
                    end_h += 12
                elif end_ampm and end_ampm.lower() == 'am' and end_h == 12:
                    end_h = 0
                
                start_time = f"{start_h:02d}:{start_m}"
                end_time = f"{end_h:02d}:{end_m}"
                
                # Extract subject - remove time from part
                subject = range_pattern.sub('', part).strip()
                subject = re.sub(r'[^\w\s&\-/]', '', subject).strip()
                
                if subject and len(subject) >= 2:
                    entries.append({
                        'subject': subject[:50],
                        'day': current_day,
                        'start_time': start_time,
                        'end_time': end_time
                    })
            else:
                # Try single time pattern (assume 1 hour duration)
                time_match = time_pattern.search(part)
                if time_match:
                    start_h = int(time_match.group(1))
                    start_m = time_match.group(2) or '00'
                    ampm = time_match.group(3)
                    
                    if ampm and ampm.lower() == 'pm' and start_h < 12:
                        start_h += 12
                    elif ampm and ampm.lower() == 'am' and start_h == 12:
                        start_h = 0
                    
                    start_time = f"{start_h:02d}:{start_m}"
                    end_time = f"{start_h + 1:02d}:{start_m}"
                    
                    subject = time_pattern.sub('', part).strip()
                    subject = re.sub(r'[^\w\s&\-/]', '', subject).strip()
                    
                    if subject and len(subject) >= 2:
                        entries.append({
                            'subject': subject[:50],
                            'day': current_day,
                            'start_time': start_time,
                            'end_time': end_time
                        })
    
    return entries


@app.route('/api/timetable/ocr', methods=['POST'])
@login_required
def ocr_timetable():
    """Extract timetable from uploaded image using OCR"""
    if not OCR_AVAILABLE:
        return jsonify({'error': 'OCR not available. Install pytesseract and Pillow.'}), 500
    
    try:
        user_id = session['user_id']
        data = request.json
        
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Decode base64 image
        image_data = data['image']
        if ',' in image_data:
            image_data = image_data.split(',')[1]  # Remove data:image/...;base64, prefix
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Run OCR
        text = pytesseract.image_to_string(image)
        
        # Parse the text to extract timetable entries
        entries = parse_timetable_text(text)
        
        # Save entries if any found
        if entries:
            for entry in entries:
                db.add_timetable_entry(
                    user_id,
                    entry['subject'],
                    entry['day'],
                    entry.get('start_time', '09:00'),
                    entry.get('end_time', '10:00')
                )
        
        return jsonify({
            'success': True,
            'extracted_text': text,
            'entries_found': len(entries),
            'entries': entries
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def parse_timetable_text(text):
    """
    Parse OCR text to extract timetable entries.
    Handles multiple timetable formats:
    - Tabular format with days as headers
    - Row-based format with day: subject time
    - Grid format with times and subjects
    """
    entries = []
    lines = text.strip().split('\n')
    
    day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    
    # Common subject keywords to help identify subjects
    subject_keywords = [
        'math', 'maths', 'mathematics', 'physics', 'chemistry', 'biology', 'english',
        'hindi', 'computer', 'science', 'history', 'geography', 'economics', 'accounts',
        'programming', 'lab', 'practical', 'tutorial', 'lecture', 'class', 'session',
        'dbms', 'os', 'dsa', 'java', 'python', 'c++', 'web', 'network', 'data',
        'machine', 'learning', 'ai', 'ml', 'electronics', 'digital', 'signal',
        'communication', 'control', 'systems', 'software', 'engineering', 'design',
        'analysis', 'algorithms', 'discrete', 'statistics', 'probability', 'calculus',
        'linear', 'algebra', 'differential', 'equations', 'mechanics', 'thermodynamics',
        'optics', 'quantum', 'electric', 'magnetic', 'waves', 'modern', 'classical',
        'organic', 'inorganic', 'physical', 'analytical', 'biochemistry', 'microbiology',
        'botany', 'zoology', 'genetics', 'ecology', 'environmental', 'management',
        'marketing', 'finance', 'hr', 'business', 'operations', 'strategy', 'law'
    ]
    
    # Time patterns
    time_range_pattern = re.compile(r'(\d{1,2})[\.:,]?(\d{2})?\s*(am|pm)?\s*[-–to]+\s*(\d{1,2})[\.:,]?(\d{2})?\s*(am|pm)?', re.IGNORECASE)
    single_time_pattern = re.compile(r'(\d{1,2})[\.:,](\d{2})\s*(am|pm)?', re.IGNORECASE)
    hour_only_pattern = re.compile(r'\b(\d{1,2})\s*(am|pm)\b', re.IGNORECASE)
    
    # First pass: Check for tabular format with day headers
    header_line = None
    day_columns = {}
    
    for idx, line in enumerate(lines[:5]):  # Check first 5 lines for headers
        line_lower = line.lower()
        days_found = []
        for day_idx, day in enumerate(day_names):
            if day in line_lower:
                pos = line_lower.find(day)
                days_found.append((day_idx, pos))
        for day_idx, abbrev in enumerate(day_abbrevs):
            if re.search(r'\b' + abbrev + r'\b', line_lower):
                pos = line_lower.find(abbrev)
                days_found.append((day_idx, pos))
        
        if len(days_found) >= 3:  # Found at least 3 days - likely a header
            header_line = idx
            for day_idx, pos in days_found:
                day_columns[pos] = day_idx
            break
    
    current_day = None
    current_time = None
    
    for line_idx, line in enumerate(lines):
        line_lower = line.lower().strip()
        if not line_lower or len(line_lower) < 3:
            continue
        
        # Skip the header line
        if header_line is not None and line_idx == header_line:
            continue
        
        # Check if line starts with time (time column on left)
        time_match = time_range_pattern.match(line.strip())
        if time_match:
            start_h = int(time_match.group(1))
            start_m = time_match.group(2) or '00'
            end_h = int(time_match.group(4))
            end_m = time_match.group(5) or '00'
            
            # Handle AM/PM
            start_pm = time_match.group(3)
            end_pm = time_match.group(6)
            if start_pm and start_pm.lower() == 'pm' and start_h < 12:
                start_h += 12
            if end_pm and end_pm.lower() == 'pm' and end_h < 12:
                end_h += 12
            
            current_time = (f"{start_h:02d}:{start_m}", f"{end_h:02d}:{end_m}")
        
        # Check for day name in this line
        for idx, day in enumerate(day_names):
            if day in line_lower:
                current_day = idx
                break
        for idx, abbrev in enumerate(day_abbrevs):
            if re.search(r'\b' + abbrev + r'\b', line_lower):
                current_day = idx
                break
        
        # Extract potential subject names
        # Remove time patterns from line
        subject_text = re.sub(time_range_pattern, ' ', line)
        subject_text = re.sub(single_time_pattern, ' ', subject_text)
        subject_text = re.sub(hour_only_pattern, ' ', subject_text)
        
        # Remove day names
        for day in day_names + day_abbrevs:
            subject_text = re.sub(r'\b' + day + r'\b', ' ', subject_text, flags=re.IGNORECASE)
        
        # Clean up
        subject_text = re.sub(r'[^\w\s&\-/]', ' ', subject_text)
        subject_text = ' '.join(subject_text.split())  # Normalize whitespace
        
        # Look for subject keywords or any word that could be a subject
        words = subject_text.split()
        subject_parts = []
        
        for word in words:
            word_lower = word.lower()
            # Include if it's a known subject keyword or a reasonable word (not too short)
            if len(word) >= 2 and (word_lower in subject_keywords or 
                                    (len(word) >= 3 and word[0].isupper()) or
                                    len(word) >= 4):
                subject_parts.append(word)
        
        if subject_parts and (current_day is not None or header_line is not None):
            subject = ' '.join(subject_parts[:4])  # Take up to 4 words
            
            if len(subject) >= 2:
                # If we have tabular format, try to match position to day
                if header_line is not None and day_columns:
                    # Find closest day column
                    text_pos = line.lower().find(subject_parts[0].lower())
                    if text_pos >= 0:
                        closest_day = None
                        min_dist = float('inf')
                        for pos, day_idx in day_columns.items():
                            dist = abs(text_pos - pos)
                            if dist < min_dist:
                                min_dist = dist
                                closest_day = day_idx
                        if closest_day is not None:
                            current_day = closest_day
                
                # Set default time if not found
                start_time = current_time[0] if current_time else '09:00'
                end_time = current_time[1] if current_time else '10:00'
                
                # Check for time in this specific line
                time_in_line = time_range_pattern.search(line)
                if time_in_line:
                    start_h = int(time_in_line.group(1))
                    start_m = time_in_line.group(2) or '00'
                    end_h = int(time_in_line.group(4))
                    end_m = time_in_line.group(5) or '00'
                    if time_in_line.group(3) and time_in_line.group(3).lower() == 'pm' and start_h < 12:
                        start_h += 12
                    if time_in_line.group(6) and time_in_line.group(6).lower() == 'pm' and end_h < 12:
                        end_h += 12
                    start_time = f"{start_h:02d}:{start_m}"
                    end_time = f"{end_h:02d}:{end_m}"
                
                if current_day is not None:
                    # Check for duplicates
                    is_dup = False
                    for e in entries:
                        if e['subject'].lower() == subject.lower() and e['day'] == current_day and e['start_time'] == start_time:
                            is_dup = True
                            break
                    
                    if not is_dup:
                        entries.append({
                            'subject': subject[:50],
                            'day': current_day,
                            'start_time': start_time,
                            'end_time': end_time
                        })
    
    return entries


# ============== PREDICTIVE ANALYTICS & TRENDS ==============

@app.route('/api/predictions')
@login_required
def get_predictions():
    """Get predictive analytics for attendance"""
    try:
        user_id = session['user_id']
        config = get_user_config(user_id)
        target_pct = config.get('target_percentage', 75) if config else 75
        
        # Get current attendance
        attendance_data = db.get_attendance(user_id)
        if not attendance_data:
            return jsonify({'error': 'No attendance data'}), 404
        
        # Get semester info for remaining days calculation
        semester_end = None
        if config and config.get('semester_end'):
            try:
                semester_end = datetime.strptime(config['semester_end'], '%Y-%m-%d')
            except:
                pass
        
        # Calculate remaining working days (approximate)
        if semester_end:
            today = datetime.now()
            remaining_days = (semester_end - today).days
            # Assume ~5 working days per week
            remaining_weeks = max(0, remaining_days // 7)
        else:
            remaining_weeks = 8  # Default assumption
        
        predictions = []
        risk_alerts = []
        
        for subject in attendance_data:
            name = subject.get('subject')
            present = subject.get('present', 0)
            total = subject.get('total', 0)
            current_pct = subject.get('percentage', 0)
            
            # Estimate remaining classes for this subject (assume 2-3 classes per week per subject)
            classes_per_week = 2
            remaining_classes = remaining_weeks * classes_per_week
            
            # Prediction 1: If attend all remaining
            if_attend_all_present = present + remaining_classes
            if_attend_all_total = total + remaining_classes
            if_attend_all_pct = round((if_attend_all_present / if_attend_all_total) * 100, 2) if if_attend_all_total > 0 else 0
            
            # Prediction 2: Classes needed to reach 75%
            future_total = total + remaining_classes
            needed_for_75 = max(0, math.ceil(0.75 * future_total) - present)
            can_skip = max(0, remaining_classes - needed_for_75)
            
            # Prediction 3: At current rate (same attendance pattern)
            if total > 0:
                attend_rate = present / total
                projected_present = present + int(remaining_classes * attend_rate)
                projected_total = total + remaining_classes
                projected_pct = round((projected_present / projected_total) * 100, 2)
            else:
                projected_pct = 0
            
            # Risk assessment: safe >= 85%, warning 75-85%, danger < 75%
            risk_level = 'safe'
            risk_message = None
            
            if current_pct < 75:
                if needed_for_75 > remaining_classes:
                    risk_level = 'critical'
                    risk_message = f"Cannot reach 75% even if you attend all remaining classes!"
                else:
                    risk_level = 'danger'
                    risk_message = f"Must attend {needed_for_75} of next {remaining_classes} classes to reach 75%"
            elif current_pct < 85:
                risk_level = 'warning'
                risk_message = f"Between 75-85%. Can skip max {can_skip} classes."
            else:
                risk_level = 'safe'
                risk_message = f"Safe (above 85%)! Can skip up to {can_skip} classes."
            
            predictions.append({
                'subject': name,
                'current': {
                    'present': present,
                    'total': total,
                    'percentage': current_pct
                },
                'remaining_classes': remaining_classes,
                'if_attend_all': if_attend_all_pct,
                'at_current_rate': projected_pct,
                'classes_needed_75': needed_for_75,
                'can_skip': can_skip,
                'risk_level': risk_level,
                'risk_message': risk_message
            })
            
            if risk_level in ['danger', 'critical']:
                risk_alerts.append({
                    'subject': name,
                    'level': risk_level,
                    'message': risk_message,
                    'current_pct': current_pct
                })
        
        # Overall predictions
        total_present = sum(s.get('present', 0) for s in attendance_data)
        total_classes = sum(s.get('total', 0) for s in attendance_data)
        overall_remaining = remaining_weeks * 2 * len(attendance_data)
        
        overall_if_attend_all = round(((total_present + overall_remaining) / (total_classes + overall_remaining)) * 100, 2) if (total_classes + overall_remaining) > 0 else 0
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'risk_alerts': risk_alerts,
            'overall': {
                'current_pct': round((total_present / total_classes) * 100, 2) if total_classes > 0 else 0,
                'if_attend_all': overall_if_attend_all,
                'remaining_weeks': remaining_weeks
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trends')
@login_required
def get_trends():
    """Get attendance trends and history"""
    try:
        user_id = session['user_id']
        days = int(request.args.get('days', 30))
        
        # Get attendance history
        history = db.get_attendance_history(user_id, days)
        
        if not history:
            return jsonify({'error': 'No history data available'}), 404
        
        # Format for charts
        overall_trend = []
        for record in history:
            overall_trend.append({
                'date': record['scraped_at'].strftime('%Y-%m-%d'),
                'percentage': record.get('overall_percentage', 0),
                'present': record.get('total_present', 0),
                'total': record.get('total_classes', 0)
            })
        
        # Get current attendance for subject comparison
        attendance_data = db.get_attendance(user_id)
        subject_comparison = []
        for subject in attendance_data:
            subject_comparison.append({
                'subject': subject.get('subject'),
                'percentage': subject.get('percentage', 0),
                'present': subject.get('present', 0),
                'total': subject.get('total', 0)
            })
        
        # Sort by percentage (lowest first for quick view of at-risk)
        subject_comparison.sort(key=lambda x: x['percentage'])
        
        # Calculate weekly stats
        weekly_stats = {}
        for record in history:
            week = record['scraped_at'].strftime('%Y-W%W')
            if week not in weekly_stats:
                weekly_stats[week] = {'records': [], 'avg_pct': 0}
            weekly_stats[week]['records'].append(record.get('overall_percentage', 0))
        
        for week in weekly_stats:
            records = weekly_stats[week]['records']
            weekly_stats[week]['avg_pct'] = round(sum(records) / len(records), 2) if records else 0
        
        weekly_trend = [{'week': k, 'percentage': v['avg_pct']} for k, v in sorted(weekly_stats.items())]
        
        return jsonify({
            'success': True,
            'overall_trend': overall_trend,
            'subject_comparison': subject_comparison,
            'weekly_trend': weekly_trend,
            'period_days': days
        })
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
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        raise
