#!/usr/bin/env python3
"""
Auto-Sync Scheduler for HELP-me-BUNK
Uses APScheduler to run ERP attendance scraping at user-defined intervals.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

# Suppress noisy APScheduler logs
logging.getLogger('apscheduler').setLevel(logging.WARNING)

scheduler = None
_app = None


def init_scheduler(app):
    """Initialize the background scheduler. Call once at app startup."""
    global scheduler, _app
    _app = app

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()
    print("✓ Auto-sync scheduler started")

    # Restore scheduled jobs for all users who have auto-sync enabled
    _restore_all_schedules()


def _restore_all_schedules():
    """On startup, re-schedule jobs for users with auto-sync enabled."""
    import database as db

    try:
        users = db.get_all_users_with_auto_sync()
        restored = 0
        for user in users:
            user_id = user['id']
            interval = user.get('auto_sync_interval', 2)
            _add_job(user_id, interval)
            restored += 1
        if restored > 0:
            print(f"  ↳ Restored {restored} auto-sync schedule(s)")
    except Exception as e:
        print(f"  ⚠ Could not restore schedules: {e}")


def _sync_job(user_id):
    """The actual job function that runs the ERP scraper for a user."""
    import database as db

    print(f"⏰ Auto-sync triggered for user {user_id} at {datetime.now().strftime('%H:%M:%S')}")

    try:
        credentials = db.get_erp_credentials(user_id)
        if not credentials:
            print(f"  ⚠ No ERP credentials for user {user_id}, skipping")
            return

        # Import here to avoid circular imports
        from app import run_scraper_background, get_scraper_status

        # Don't start if already running
        status = get_scraper_status(user_id)
        if status.get('running'):
            print(f"  ⚠ Scraper already running for user {user_id}, skipping")
            return

        # Run in a thread (same as manual sync)
        import threading
        thread = threading.Thread(
            target=run_scraper_background,
            args=(user_id, credentials['username'], credentials['password'])
        )
        thread.daemon = True
        thread.start()
        print(f"  ✓ Sync started for user {user_id}")
    except Exception as e:
        print(f"  ✗ Auto-sync failed for user {user_id}: {e}")


def _get_job_id(user_id):
    """Generate a consistent job ID for a user."""
    return f"auto_sync_{user_id}"


def _add_job(user_id, interval_hours):
    """Add or replace an interval job for a user."""
    global scheduler
    if not scheduler:
        return

    job_id = _get_job_id(user_id)

    # Remove existing job if any
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    scheduler.add_job(
        func=_sync_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id=job_id,
        args=[user_id],
        replace_existing=True,
        name=f"Auto-sync for user {user_id} every {interval_hours}h"
    )


def schedule_user_sync(user_id, interval_hours):
    """
    Enable auto-sync for a user with the given interval.
    Also persists the setting to the database.
    """
    import database as db

    # Validate interval
    if interval_hours not in (1, 2, 4):
        raise ValueError("Interval must be 1, 2, or 4 hours")

    # Save to database
    db.update_user_config(
        user_id,
        
        auto_sync_enabled=True,
        auto_sync_interval=interval_hours
    )

    # Add the scheduler job
    _add_job(user_id, interval_hours)
    print(f"✓ Auto-sync scheduled for user {user_id} every {interval_hours}h")


def remove_user_sync(user_id):
    """
    Disable auto-sync for a user.
    Also persists the setting to the database.
    """
    import database as db
    global scheduler

    # Save to database
    db.update_user_config(
        user_id,
        auto_sync_enabled=False
    )

    # Remove the scheduler job
    if scheduler:
        try:
            scheduler.remove_job(_get_job_id(user_id))
        except Exception:
            pass

    print(f"✓ Auto-sync disabled for user {user_id}")


def get_user_schedule(user_id):
    """Get the current auto-sync schedule info for a user."""
    import database as db
    global scheduler

    user = db.get_user(user_id)
    if not user:
        return {'enabled': False, 'interval': 2, 'next_run': None}

    enabled = user.get('auto_sync_enabled', False)
    interval = user.get('auto_sync_interval', 2)
    next_run = None

    if scheduler and enabled:
        job = scheduler.get_job(_get_job_id(user_id))
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        'enabled': enabled,
        'interval': interval,
        'next_run': next_run
    }


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown(wait=False)
        print("✓ Auto-sync scheduler stopped")
