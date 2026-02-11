#!/usr/bin/env python3
"""
Database module for HELP-me-BUNK
SQLite database for multi-user support
"""

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os

DATABASE_PATH = 'help_me_bunk.db'


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            erp_username TEXT,
            semester_start TEXT,
            semester_end TEXT,
            target_percentage INTEGER DEFAULT 75,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Attendance data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            present INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            percentage REAL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, subject)
        )
    ''')
    
    # Scrape history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scrape_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subject_count INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Database initialized")


# ============== USER FUNCTIONS ==============

def create_user(username, password, erp_username=None):
    """Create a new user"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, erp_username)
            VALUES (?, ?, ?)
        ''', (username, password_hash, erp_username))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {'success': True, 'user_id': user_id}
    except sqlite3.IntegrityError:
        conn.close()
        return {'success': False, 'error': 'Username already exists'}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def verify_user(username, password):
    """Verify user credentials"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        # Update last login
        cursor.execute('''
            UPDATE users SET last_login = ? WHERE id = ?
        ''', (datetime.now(), user['id']))
        conn.commit()
        conn.close()
        return {'success': True, 'user_id': user['id'], 'username': user['username']}
    
    conn.close()
    return {'success': False, 'error': 'Invalid username or password'}


def get_user(user_id):
    """Get user by ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None


def update_user_config(user_id, erp_username=None, semester_start=None, semester_end=None, target_percentage=None):
    """Update user configuration"""
    conn = get_db()
    cursor = conn.cursor()
    
    updates = []
    values = []
    
    if erp_username is not None:
        updates.append('erp_username = ?')
        values.append(erp_username)
    if semester_start is not None:
        updates.append('semester_start = ?')
        values.append(semester_start)
    if semester_end is not None:
        updates.append('semester_end = ?')
        values.append(semester_end)
    if target_percentage is not None:
        updates.append('target_percentage = ?')
        values.append(target_percentage)
    
    if updates:
        values.append(user_id)
        cursor.execute(f'''
            UPDATE users SET {', '.join(updates)} WHERE id = ?
        ''', values)
        conn.commit()
    
    conn.close()
    return True


# ============== ATTENDANCE FUNCTIONS ==============

def save_attendance(user_id, subjects):
    """Save or update attendance data for a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    for subject in subjects:
        name = subject.get('subject')
        present = subject.get('present', 0)
        total = subject.get('total', 0)
        percentage = round((present / total) * 100, 2) if total > 0 else 0
        
        cursor.execute('''
            INSERT INTO attendance (user_id, subject, present, total, percentage, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, subject) DO UPDATE SET
                present = excluded.present,
                total = excluded.total,
                percentage = excluded.percentage,
                last_updated = excluded.last_updated
        ''', (user_id, name, present, total, percentage, datetime.now()))
    
    # Record scrape history
    cursor.execute('''
        INSERT INTO scrape_history (user_id, subject_count)
        VALUES (?, ?)
    ''', (user_id, len(subjects)))
    
    conn.commit()
    conn.close()
    return True


def get_attendance(user_id):
    """Get all attendance data for a user"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT subject, present, total, percentage, last_updated
        FROM attendance WHERE user_id = ?
        ORDER BY subject
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def update_subject(user_id, subject_name, present, total):
    """Update a single subject's attendance"""
    conn = get_db()
    cursor = conn.cursor()
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
    cursor.execute('''
        UPDATE attendance 
        SET present = ?, total = ?, percentage = ?, last_updated = ?
        WHERE user_id = ? AND subject = ?
    ''', (present, total, percentage, datetime.now(), user_id, subject_name))
    
    if cursor.rowcount == 0:
        # Subject doesn't exist, insert it
        cursor.execute('''
            INSERT INTO attendance (user_id, subject, present, total, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, subject_name, present, total, percentage))
    
    conn.commit()
    conn.close()
    return True


def add_subject(user_id, subject_name, present, total):
    """Add a new subject"""
    conn = get_db()
    cursor = conn.cursor()
    
    percentage = round((present / total) * 100, 2) if total > 0 else 0
    
    try:
        cursor.execute('''
            INSERT INTO attendance (user_id, subject, present, total, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, subject_name, present, total, percentage))
        conn.commit()
        conn.close()
        return {'success': True}
    except sqlite3.IntegrityError:
        conn.close()
        return {'success': False, 'error': 'Subject already exists'}


def delete_subject(user_id, subject_name):
    """Delete a subject"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM attendance WHERE user_id = ? AND subject = ?
    ''', (user_id, subject_name))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted


def get_last_scrape(user_id):
    """Get last scrape timestamp"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT scraped_at FROM scrape_history 
        WHERE user_id = ? 
        ORDER BY scraped_at DESC LIMIT 1
    ''', (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    return row['scraped_at'] if row else None


# Initialize database when module is imported
if not os.path.exists(DATABASE_PATH):
    init_db()
