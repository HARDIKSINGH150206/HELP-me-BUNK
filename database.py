#!/usr/bin/env python3
"""
Database module for HELP-me-BUNK
MongoDB database for multi-user support
"""

from pymongo import MongoClient
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import os

# MongoDB Atlas connection string - MUST set as environment variable
# Example: export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/?appName=HELPmeBUNK"
MONGODB_URI = os.environ.get('MONGODB_URI')
DATABASE_NAME = 'help_me_bunk'

if not MONGODB_URI:
    print("⚠ MONGODB_URI environment variable not set!")
    print("  Set it with: export MONGODB_URI='your-connection-string'")

# Global client connection
_client = None
_db = None


def get_db():
    """Get database connection"""
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGODB_URI)
        _db = _client[DATABASE_NAME]
    return _db


def init_db():
    """Initialize database collections and indexes"""
    db = get_db()
    
    # Create indexes for better query performance
    db.users.create_index('username', unique=True)
    db.attendance.create_index([('user_id', 1), ('subject', 1)], unique=True)
    db.scrape_history.create_index('user_id')
    
    print("✓ MongoDB initialized")


# ============== USER FUNCTIONS ==============

def create_user(username, password, erp_username=None):
    """Create a new user"""
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
    db = get_db()
    
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
    db = get_db()
    
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if user:
            user['id'] = str(user['_id'])
            del user['_id']
            return user
    except:
        pass
    return None


def update_user_config(user_id, erp_username=None, semester_start=None, semester_end=None, target_percentage=None):
    """Update user configuration"""
    db = get_db()
    
    updates = {}
    
    if erp_username is not None:
        updates['erp_username'] = erp_username
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


# ============== ATTENDANCE FUNCTIONS ==============

def save_attendance(user_id, subjects):
    """Save or update attendance data for a user"""
    db = get_db()
    
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
    
    # Record scrape history
    db.scrape_history.insert_one({
        'user_id': user_id,
        'scraped_at': datetime.now(),
        'subject_count': len(subjects)
    })
    
    return True


def get_attendance(user_id):
    """Get all attendance data for a user"""
    db = get_db()
    
    subjects = list(db.attendance.find(
        {'user_id': user_id},
        {'_id': 0, 'user_id': 0}
    ).sort('subject', 1))
    
    return subjects


def update_subject(user_id, subject_name, present, total):
    """Update a single subject's attendance"""
    db = get_db()
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
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
    db = get_db()
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
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
    db = get_db()
    
    result = db.attendance.delete_one({
        'user_id': user_id,
        'subject': subject_name
    })
    
    return result.deleted_count > 0


def get_last_scrape(user_id):
    """Get last scrape timestamp"""
    db = get_db()
    
    record = db.scrape_history.find_one(
        {'user_id': user_id},
        sort=[('scraped_at', -1)]
    )
    
    if record:
        return record['scraped_at'].strftime("%Y-%m-%d %H:%M:%S")
    return None


# Initialize database when module is imported
try:
    init_db()
except Exception as e:
    print(f"⚠ MongoDB connection pending - set MONGODB_URI environment variable")
    print(f"  Error: {e}")
