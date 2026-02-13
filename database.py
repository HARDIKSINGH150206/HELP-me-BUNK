#!/usr/bin/env python3
"""
Database module for HELP-me-BUNK
MongoDB database for multi-user support with JSON fallback
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from pathlib import Path
from cryptography.fernet import Fernet

# Encryption key for ERP passwords (generate one if not set)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    # Generate a key silently for local dev
    ENCRYPTION_KEY = Fernet.generate_key().decode()
else:
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY

_fernet = Fernet(ENCRYPTION_KEY if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY.encode())


def encrypt_password(password):
    """Encrypt a password for storage"""
    return _fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted):
    """Decrypt a stored password"""
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except:
        return None


# MongoDB Atlas connection string
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'help_me_bunk'

# Fallback mode flag - set to True immediately for local development
_using_fallback = False
_connection_tested = False
_client = None
_db = None

# JSON fallback storage
_json_storage_path = Path(__file__).parent / 'local_db.json'
_json_data = None

# Quick check: if localhost MongoDB, assume it's not running and use JSON fallback
# This avoids connection timeout on startup
if 'localhost' in MONGODB_URI or '127.0.0.1' in MONGODB_URI:
    import socket
    try:
        # Quick port check (non-blocking)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)  # 100ms timeout
        result = sock.connect_ex(('localhost', 27017))
        sock.close()
        if result != 0:
            _using_fallback = True
            _connection_tested = True
    except:
        _using_fallback = True
        _connection_tested = True


def _load_json_db():
    """Load JSON fallback database"""
    global _json_data
    if _json_data is None:
        if _json_storage_path.exists():
            try:
                with open(_json_storage_path, 'r') as f:
                    _json_data = json.load(f)
            except:
                _json_data = {'users': {}, 'attendance': {}, 'scrape_history': {}, 'timetable': {}}
        else:
            _json_data = {'users': {}, 'attendance': {}, 'scrape_history': {}, 'timetable': {}}
    return _json_data


def _save_json_db():
    """Save JSON fallback database"""
    global _json_data
    if _json_data is not None:
        with open(_json_storage_path, 'w') as f:
            json.dump(_json_data, f, indent=2, default=str)


def _generate_id():
    """Generate a simple unique ID for JSON mode"""
    import uuid
    return str(uuid.uuid4())[:24]


def get_db():
    """Get database connection (MongoDB or fallback)"""
    global _client, _db, _using_fallback
    
    if _using_fallback:
        return None  # Use JSON functions instead
    
    if _db is None:
        try:
            from pymongo import MongoClient
            import certifi
            import ssl
            from bson.objectid import ObjectId
            
            _client = MongoClient(
                MONGODB_URI, 
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                tls=True,
                tlsCAFile=certifi.where()
            )
            _db = _client[DATABASE_NAME]
            # Test connection
            _client.server_info()
        except Exception:
            # Silently fall back to JSON mode
            _using_fallback = True
            _load_json_db()
            return None
    return _db


def init_db():
    """Initialize database collections and indexes"""
    global _using_fallback
    
    db = get_db()
    
    if _using_fallback:
        _load_json_db()
        print("✓ Running in local mode (JSON storage)")
        return
    
    if db is not None:
        from pymongo import MongoClient
        # Create indexes for better query performance
        db.users.create_index('username', unique=True)
        db.attendance.create_index([('user_id', 1), ('subject', 1)], unique=True)
        db.scrape_history.create_index('user_id')
        db.timetable.create_index([('user_id', 1), ('day', 1), ('start_time', 1)])
        print("✓ MongoDB initialized")


# ============== USER FUNCTIONS ==============

def create_user(username, password, erp_username=None):
    """Create a new user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if username in [u.get('username') for u in data['users'].values()]:
            return {'success': False, 'error': 'Username already exists'}
        
        user_id = _generate_id()
        data['users'][user_id] = {
            'username': username,
            'password_hash': generate_password_hash(password),
            'erp_username': erp_username,
            'semester_start': None,
            'semester_end': None,
            'target_percentage': 75,
            'created_at': datetime.now().isoformat(),
            'last_login': None
        }
        _save_json_db()
        return {'success': True, 'user_id': user_id}
    
    db = get_db()
    try:
        password_hash = generate_password_hash(password)
        result = db.users.insert_one({
            'username': username,
            'password_hash': password_hash,
            'erp_username': erp_username,
            'semester_start': None,
            'semester_end': None,
            'target_percentage': 75,
            'created_at': datetime.now(),
            'last_login': None
        })
        return {'success': True, 'user_id': str(result.inserted_id)}
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return {'success': False, 'error': 'Username already exists'}
        return {'success': False, 'error': str(e)}


def verify_user(username, password):
    """Verify user credentials"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        for user_id, user in data['users'].items():
            if user['username'] == username and check_password_hash(user['password_hash'], password):
                user['last_login'] = datetime.now().isoformat()
                _save_json_db()
                return {'success': True, 'user_id': user_id, 'username': user['username']}
        return {'success': False, 'error': 'Invalid username or password'}
    
    db = get_db()
    from bson.objectid import ObjectId
    
    user = db.users.find_one({'username': username})
    
    if user and check_password_hash(user['password_hash'], password):
        # Update last login
        db.users.update_one(
            {'_id': user['_id']},
            {'$set': {'last_login': datetime.now()}}
        )
        return {'success': True, 'user_id': str(user['_id']), 'username': user['username']}
    
    return {'success': False, 'error': 'Invalid username or password'}


def get_user(user_id):
    """Get user by ID"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        user = data['users'].get(user_id)
        if user:
            user_copy = user.copy()
            user_copy['id'] = user_id
            return user_copy
        return None
    
    db = get_db()
    from bson.objectid import ObjectId
    
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if user:
            user['id'] = str(user['_id'])
            del user['_id']
            return user
    except:
        pass
    return None


def update_user_config(user_id, erp_username=None, erp_password=None, semester_start=None, semester_end=None, target_percentage=None):
    """Update user configuration"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if user_id in data['users']:
            if erp_username is not None:
                data['users'][user_id]['erp_username'] = erp_username
            if erp_password is not None:
                data['users'][user_id]['erp_password_encrypted'] = encrypt_password(erp_password)
            if semester_start is not None:
                data['users'][user_id]['semester_start'] = semester_start
            if semester_end is not None:
                data['users'][user_id]['semester_end'] = semester_end
            if target_percentage is not None:
                data['users'][user_id]['target_percentage'] = target_percentage
            _save_json_db()
        return True
    
    db = get_db()
    from bson.objectid import ObjectId
    
    updates = {}
    
    if erp_username is not None:
        updates['erp_username'] = erp_username
    if erp_password is not None:
        # Encrypt ERP password before storing
        updates['erp_password_encrypted'] = encrypt_password(erp_password)
    if semester_start is not None:
        updates['semester_start'] = semester_start
    if semester_end is not None:
        updates['semester_end'] = semester_end
    if target_percentage is not None:
        updates['target_percentage'] = target_percentage
    
    if updates:
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': updates}
        )
    
    return True


def get_erp_credentials(user_id):
    """Get decrypted ERP credentials for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        user = data['users'].get(user_id)
        if user:
            erp_username = user.get('erp_username')
            erp_password_encrypted = user.get('erp_password_encrypted')
            if erp_username and erp_password_encrypted:
                erp_password = decrypt_password(erp_password_encrypted)
                if erp_password:
                    return {'username': erp_username, 'password': erp_password}
        return None
    
    db = get_db()
    from bson.objectid import ObjectId
    user = db.users.find_one({'_id': ObjectId(user_id)})
    
    if user:
        erp_username = user.get('erp_username')
        erp_password_encrypted = user.get('erp_password_encrypted')
        
        if erp_username and erp_password_encrypted:
            erp_password = decrypt_password(erp_password_encrypted)
            if erp_password:
                return {'username': erp_username, 'password': erp_password}
    
    return None


# ============== ATTENDANCE FUNCTIONS ==============

def save_attendance(user_id, subjects, overall=None):
    """Save or update attendance data for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if user_id not in data['attendance']:
            data['attendance'][user_id] = {}
        
        for subject in subjects:
            name = subject.get('subject')
            present = subject.get('present', 0)
            total = subject.get('total', 0)
            percentage = round((present / total) * 100, 2) if total > 0 else 0
            
            data['attendance'][user_id][name] = {
                'subject': name,
                'present': present,
                'total': total,
                'percentage': percentage,
                'last_updated': datetime.now().isoformat()
            }
        
        if overall and user_id in data['users']:
            data['users'][user_id]['erp_overall_present'] = overall.get('present')
            data['users'][user_id]['erp_overall_total'] = overall.get('total')
            data['users'][user_id]['erp_overall_percentage'] = overall.get('percentage')
            data['users'][user_id]['erp_overall_updated'] = datetime.now().isoformat()
        
        # Record scrape history
        if user_id not in data['scrape_history']:
            data['scrape_history'][user_id] = []
        
        total_present = sum(s.get('present', 0) for s in subjects)
        total_classes = sum(s.get('total', 0) for s in subjects)
        overall_pct = round((total_present / total_classes) * 100, 2) if total_classes > 0 else 0
        
        data['scrape_history'][user_id].append({
            'scraped_at': datetime.now().isoformat(),
            'subject_count': len(subjects),
            'total_present': total_present,
            'total_classes': total_classes,
            'overall_percentage': overall.get('percentage') if overall else overall_pct,
            'subjects_snapshot': subjects
        })
        
        _save_json_db()
        return True
    
    db = get_db()
    from bson.objectid import ObjectId
    
    for subject in subjects:
        name = subject.get('subject')
        present = subject.get('present', 0)
        total = subject.get('total', 0)
        percentage = round((present / total) * 100, 2) if total > 0 else 0
        
        db.attendance.update_one(
            {'user_id': user_id, 'subject': name},
            {'$set': {
                'present': present,
                'total': total,
                'percentage': percentage,
                'last_updated': datetime.now()
            }},
            upsert=True
        )
    
    # Save overall attendance from ERP if provided
    if overall:
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'erp_overall_present': overall.get('present'),
                'erp_overall_total': overall.get('total'),
                'erp_overall_percentage': overall.get('percentage'),
                'erp_overall_updated': datetime.now()
            }}
        )
    
    # Record scrape history with full attendance snapshot for trends
    total_present = sum(s.get('present', 0) for s in subjects)
    total_classes = sum(s.get('total', 0) for s in subjects)
    overall_pct = round((total_present / total_classes) * 100, 2) if total_classes > 0 else 0
    
    db.scrape_history.insert_one({
        'user_id': user_id,
        'scraped_at': datetime.now(),
        'subject_count': len(subjects),
        'total_present': total_present,
        'total_classes': total_classes,
        'overall_percentage': overall.get('percentage') if overall else overall_pct,
        'subjects_snapshot': subjects  # Store full snapshot for detailed trends
    })
    
    return True


def get_attendance_history(user_id, days=30):
    """Get attendance history for trends (last N days)"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        history = data['scrape_history'].get(user_id, [])
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        return [h for h in history if datetime.fromisoformat(h['scraped_at']) >= cutoff_date]
    
    db = get_db()
    
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    history = list(db.scrape_history.find(
        {'user_id': user_id, 'scraped_at': {'$gte': cutoff_date}},
        {'_id': 0, 'user_id': 0}
    ).sort('scraped_at', 1))
    
    return history


def get_subject_history(user_id, subject_name, days=30):
    """Get history for a specific subject"""
    global _using_fallback
    
    if _using_fallback:
        history = get_attendance_history(user_id, days)
        subject_history = []
        for record in history:
            snapshot = record.get('subjects_snapshot', [])
            for s in snapshot:
                if s.get('subject') == subject_name:
                    subject_history.append({
                        'date': record['scraped_at'],
                        'present': s.get('present', 0),
                        'total': s.get('total', 0),
                        'percentage': s.get('percentage', 0)
                    })
                    break
        return subject_history
    
    db = get_db()
    
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    history = list(db.scrape_history.find(
        {'user_id': user_id, 'scraped_at': {'$gte': cutoff_date}},
        {'_id': 0, 'scraped_at': 1, 'subjects_snapshot': 1}
    ).sort('scraped_at', 1))
    
    subject_history = []
    for record in history:
        snapshot = record.get('subjects_snapshot', [])
        for s in snapshot:
            if s.get('subject') == subject_name:
                subject_history.append({
                    'date': record['scraped_at'],
                    'present': s.get('present', 0),
                    'total': s.get('total', 0),
                    'percentage': s.get('percentage', 0)
                })
                break
    
    return subject_history


def get_erp_overall(user_id):
    """Get overall attendance from ERP for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        user = data['users'].get(user_id)
        if user and user.get('erp_overall_percentage') is not None:
            return {
                'present': user.get('erp_overall_present'),
                'total': user.get('erp_overall_total'),
                'percentage': user.get('erp_overall_percentage'),
                'updated': user.get('erp_overall_updated')
            }
        return None
    
    db = get_db()
    from bson.objectid import ObjectId
    user = db.users.find_one({'_id': ObjectId(user_id)})
    
    if user and user.get('erp_overall_percentage') is not None:
        return {
            'present': user.get('erp_overall_present'),
            'total': user.get('erp_overall_total'),
            'percentage': user.get('erp_overall_percentage'),
            'updated': user.get('erp_overall_updated')
        }
    return None


def get_attendance(user_id):
    """Get all attendance data for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        user_attendance = data['attendance'].get(user_id, {})
        return sorted(list(user_attendance.values()), key=lambda x: x.get('subject', ''))
    
    db = get_db()
    
    subjects = list(db.attendance.find(
        {'user_id': user_id},
        {'_id': 0, 'user_id': 0}
    ).sort('subject', 1))
    
    return subjects


def update_subject(user_id, subject_name, present, total):
    """Update a single subject's attendance"""
    global _using_fallback
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
    if _using_fallback:
        data = _load_json_db()
        if user_id not in data['attendance']:
            data['attendance'][user_id] = {}
        
        data['attendance'][user_id][subject_name] = {
            'subject': subject_name,
            'present': present,
            'total': total,
            'percentage': percentage,
            'last_updated': datetime.now().isoformat()
        }
        _save_json_db()
        return True
    
    db = get_db()
    
    result = db.attendance.update_one(
        {'user_id': user_id, 'subject': subject_name},
        {'$set': {
            'present': present,
            'total': total,
            'percentage': percentage,
            'last_updated': datetime.now()
        }},
        upsert=True
    )
    
    return True


def add_subject(user_id, subject_name, present, total):
    """Add a new subject"""
    global _using_fallback
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
    if _using_fallback:
        data = _load_json_db()
        if user_id not in data['attendance']:
            data['attendance'][user_id] = {}
        
        if subject_name in data['attendance'][user_id]:
            return {'success': False, 'error': 'Subject already exists'}
        
        data['attendance'][user_id][subject_name] = {
            'subject': subject_name,
            'present': present,
            'total': total,
            'percentage': percentage,
            'last_updated': datetime.now().isoformat()
        }
        _save_json_db()
        return {'success': True}
    
    db = get_db()
    
    # Check if subject already exists
    existing = db.attendance.find_one({'user_id': user_id, 'subject': subject_name})
    if existing:
        return {'success': False, 'error': 'Subject already exists'}
    
    db.attendance.insert_one({
        'user_id': user_id,
        'subject': subject_name,
        'present': present,
        'total': total,
        'percentage': percentage,
        'last_updated': datetime.now()
    })
    
    return {'success': True}


def delete_subject(user_id, subject_name):
    """Delete a subject"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if user_id in data['attendance'] and subject_name in data['attendance'][user_id]:
            del data['attendance'][user_id][subject_name]
            _save_json_db()
            return True
        return False
    
    db = get_db()
    
    result = db.attendance.delete_one({
        'user_id': user_id,
        'subject': subject_name
    })
    
    return result.deleted_count > 0


def get_last_scrape(user_id):
    """Get last scrape timestamp"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        history = data['scrape_history'].get(user_id, [])
        if history:
            return history[-1]['scraped_at']
        return None
    
    db = get_db()
    
    record = db.scrape_history.find_one(
        {'user_id': user_id},
        sort=[('scraped_at', -1)]
    )
    
    if record:
        return record['scraped_at'].strftime("%Y-%m-%d %H:%M:%S")
    return None


# ============== TIMETABLE FUNCTIONS ==============

def save_timetable(user_id, timetable_entries):
    """Save or update timetable data for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        data['timetable'][user_id] = []
        for entry in timetable_entries:
            data['timetable'][user_id].append({
                'subject': entry.get('subject'),
                'day': entry.get('day'),
                'start_time': entry.get('start_time'),
                'end_time': entry.get('end_time'),
                'raw_text': entry.get('raw_text', ''),
                'created_at': datetime.now().isoformat()
            })
        _save_json_db()
        return True
    
    db = get_db()
    
    # Clear existing timetable for user
    db.timetable.delete_many({'user_id': user_id})
    
    # Insert new entries
    for entry in timetable_entries:
        db.timetable.insert_one({
            'user_id': user_id,
            'subject': entry.get('subject'),
            'day': entry.get('day'),  # 0=Monday, 6=Sunday
            'start_time': entry.get('start_time'),
            'end_time': entry.get('end_time'),
            'raw_text': entry.get('raw_text', ''),
            'created_at': datetime.now()
        })
    
    return True


def get_timetable(user_id):
    """Get timetable for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        entries = data['timetable'].get(user_id, [])
        return sorted(entries, key=lambda x: (x.get('day', 0), x.get('start_time', '')))
    
    db = get_db()
    
    entries = list(db.timetable.find(
        {'user_id': user_id},
        {'_id': 0, 'user_id': 0, 'created_at': 0}
    ).sort([('day', 1), ('start_time', 1)]))
    
    return entries


def add_timetable_entry(user_id, subject, day, start_time, end_time):
    """Add a single timetable entry"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if user_id not in data['timetable']:
            data['timetable'][user_id] = []
        
        data['timetable'][user_id].append({
            'subject': subject,
            'day': day,
            'start_time': start_time,
            'end_time': end_time,
            'raw_text': f"{subject} ({start_time}-{end_time})",
            'created_at': datetime.now().isoformat()
        })
        _save_json_db()
        return {'success': True}
    
    db = get_db()
    
    db.timetable.insert_one({
        'user_id': user_id,
        'subject': subject,
        'day': day,
        'start_time': start_time,
        'end_time': end_time,
        'raw_text': f"{subject} ({start_time}-{end_time})",
        'created_at': datetime.now()
    })
    
    return {'success': True}


def delete_timetable_entry(user_id, subject, day, start_time):
    """Delete a timetable entry"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        if user_id in data['timetable']:
            data['timetable'][user_id] = [
                e for e in data['timetable'][user_id]
                if not (e['subject'] == subject and e['day'] == day and e['start_time'] == start_time)
            ]
            _save_json_db()
            return True
        return False
    
    db = get_db()
    
    result = db.timetable.delete_one({
        'user_id': user_id,
        'subject': subject,
        'day': day,
        'start_time': start_time
    })
    
    return result.deleted_count > 0


def clear_timetable(user_id):
    """Clear all timetable entries for a user"""
    global _using_fallback
    
    if _using_fallback:
        data = _load_json_db()
        data['timetable'][user_id] = []
        _save_json_db()
        return True
    
    db = get_db()
    db.timetable.delete_many({'user_id': user_id})
    return True
