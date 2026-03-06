# HELP-me-BUNK Setup Checklist

## Before You Start
- [ ] Python 3.8+ installed
- [ ] Virtual environment created
- [ ] Access to Acharya ERPNext portal

## Step-by-Step Setup

### Phase 1: Environment Setup (5 minutes)

- [ ] Activate virtual environment:
  ```bash
  source venv/bin/activate
  ```
- [ ] Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### Phase 2: Configuration (2 minutes)

- [ ] Create a `.env` file in the project root
- [ ] Add the following (adjust as needed):
  ```
  SECRET_KEY=your-secret-key-here
  MONGODB_URI=mongodb://localhost:27017/
  ```

### Phase 3: Start Application (1 minute)

- [ ] Run the Flask app:
  ```bash
  python app.py
  ```
- [ ] Open browser: http://localhost:5000
- [ ] You should see the login page

### Phase 4: Create Account (2 minutes)

In the Dashboard:
- [ ] Click "Register" or sign up button
- [ ] Enter your desired username and password
- [ ] Submit the form
- [ ] You should be redirected to login

### Phase 5: Add ERP Credentials (2 minutes)

In the Dashboard:
- [ ] Log in with your credentials
- [ ] Navigate to settings or account section
- [ ] Enter your Acharya ERPNext username and password
- [ ] Save credentials

### Phase 6: Sync Attendance (5 minutes)

- [ ] Click "Sync Now" or "Fetch Attendance" button
- [ ] Wait for the sync to complete
- [ ] View your attendance data on the dashboard

## Features Available

After setup:
- ✅ View attendance for all subjects
- ✅ See attendance trends and statistics  
- ✅ Check which classes you can safely bunk
- ✅ Get bunk recommendations
- ✅ View your daily schedule
- ✅ Set up auto-sync for scheduled updates

## Database Setup (Optional)

For MongoDB support:
1. Install MongoDB locally or use MongoDB Atlas
2. Update `MONGODB_URI` in `.env` with your connection string
3. The app will automatically use MongoDB if available, otherwise uses JSON storage

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Make sure all packages are installed: `pip install -r requirements.txt` |
| Connection refused | Check MongoDB is running, or use JSON fallback mode |
| ERP login fails | Verify username/password are correct for Acharya portal |
| Attendance not syncing | Check internet connection, verify ERP credentials |
| 404 errors | Restart Flask app and clear browser cache |

## Need Help?

1. Check the [README.md](README.md) for full documentation
2. Review browser console for errors: Press F12
3. Check Flask terminal output for detailed messages
4. Verify all dependencies are installed

## Next Steps

Once everything is working:
- Explore the dashboard features
- Set up auto-sync for automatic attendance updates
- Share with classmates or friends
- Keep your credentials secure!

---

**Expected Time to Complete**: 10-15 minutes total

**Ready to check your attendance? Log in and start syncing!**
