# Render Deployment Guide

## Quick Start (5 minutes)

### Step 1: Push to GitHub
```bash
cd /home/hardik-singh/Documents/VScode/Code/attendance-project
git add .
git commit -m "prep: Ready for Render deployment"
git push origin main
```

### Step 2: Connect to Render

1. Go to [render.com](https://render.com)
2. Sign up / Log in with GitHub account
3. Click **New +** → **Web Service**
4. Select your GitHub repo: `attendance-project`
5. Click **Connect**

### Step 3: Configure Service

**Name:** `attendance-dashboard` (or any name)
**Runtime:** Python 3.11
**Build Command:** `pip install -r requirements.txt`
**Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class sync --timeout 120`
**Instance Type:** Free (or Starter for more stability)

### Step 4: Add Environment Variables

In Render dashboard, go to **Environment** tab and add:

```
MONGODB_URI=<your-mongodb-connection-string>
SECRET_KEY=<generate-random-key>
FLASK_ENV=production
DEBUG=false
```

To generate SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 5: Deploy

Click **Create Web Service**

Render will:
- Install dependencies
- Build the app
- Start the service
- Assign you a public URL (like `https://attendance-dashboard.onrender.com`)

**Deploy time:** 2-3 minutes

---

## Environment Variables Explained

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `MONGODB_URI` | YES | `mongodb+srv://user:pass@...` | Get from MongoDB Atlas |
| `SECRET_KEY` | YES | `a1b2c3d4...` | Use any 64-char random string |
| `FLASK_ENV` | NO | `production` | Auto on Render, only needed for safety |
| `DEBUG` | NO | `false` | Must be `false` in production |

### Get MongoDB URI

1. Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. Create free cluster (if not already)
3. Go to **Connect** → **Drivers**
4. Copy connection string (looks like `mongodb+srv://...`)
5. Replace `<password>` with your actual MongoDB password
6. Paste into Render env vars

---

## Troubleshooting

### Service keeps crashing?
- Check **Logs** in Render dashboard
- Look for import errors or missing packages
- Common issue: `gunicorn` not in requirements.txt (it's there, you're good)

### MongoDB connection fails?
- Verify connection string in **Environment** tab
- Make sure MongoDB cluster is running
- Check IP whitelist in MongoDB Atlas (set to `0.0.0.0/0` for Render)

### Selenium driver fails?
- Render uses headless Linux, no display
- Code should use headless Chrome (check `attendance_scraper.py`)
- If crashing, consider using v2 (HTTP API) which doesn't need Selenium

### App is slow?
- Free tier has 0.5 CPU, limited RAM
- Upgrade to **Starter** (paid, $7/month) for better performance
- Or optimize: kill background jobs during scraping

---

## Monitoring & Logs

**View logs live:**
- Render Dashboard → Service → **Logs** tab
- Shows real-time output and errors

**Restart service:**
- Render Dashboard → **Manual Deploy** → **Deploy latest commit**
- Or just push to GitHub (auto-redeploy)

---

## Custom Domain (Optional)

1. Buy domain (GoDaddy, Namecheap, etc.)
2. Render Dashboard → **Settings** → **Custom Domains**
3. Add your domain
4. Follow DNS instructions
5. CNAME points to Render URL

---

## Cost

| Tier | Price | CPU | RAM | Perfect For |
|------|-------|-----|-----|-------------|
| Free | $0/mo | 0.5 | 512MB | Testing/hobby |
| Starter | $7/mo | 2 | 2GB | Small production |
| Standard | $25/mo | 4 | 4GB | Medium production |

**Current:** You can use free tier, but watch memory usage with Selenium.

---

## After Deployment ✅

1. **Visit your URL** - Should see login page
2. **Test login** - Try with real credentials
3. **Check logs** - Any errors? Fix them.
4. **Enable auto-deploy** - Push to GitHub → auto-redeploy
5. **Set up alerts** (optional) - Get notified if service crashes

---

## Git-Based Auto-Deployment

Every time you push to GitHub, Render automatically:
1. Fetches latest code
2. Installs dependencies
3. Restarts the app

**Start auto-deploy:**
```bash
git add .
git commit -m "feature: Add something cool"
git push origin main
```

Render detects push → redeploys automatically (2-3 min)

---

## Production Checklist

- [x] `requirements.txt` has all packages
- [x] `Procfile` exists and is correct
- [x] `render.yaml` configured
- [x] `app.run(debug=False)` for production (gunicorn runs it, debug ignored anyway)
- [x] MongoDB ready
- [x] SECRET_KEY set
- [x] Environment variables added
- [ ] Test login works
- [ ] Test attendance scraping works
- [ ] Monitor first 24 hours for crashes
- [ ] Set up email alerts (optional)

---

## Quick Commands

```bash
# Test locally before pushing
python3 -m pip install -r requirements.txt
python3 app.py
# Visit http://localhost:5000

# Push to deploy
git add .
git commit -m "ready for render"
git push origin main

# View logs (if you have render CLI)
# render logs --service=attendance-dashboard
```

---

## Still Having Issues?

Common problems:

1. **"ModuleNotFoundError: No module named 'X'"**
   - Add package to `requirements.txt`
   - Push to GitHub
   - Render redeploys automatically

2. **"Connection refused on port 5000"**
   - Render doesn't use 5000, it uses `$PORT` env var
   - Code already handles this (gunicorn does)
   - Should be fine

3. **"Selenium can't find Chrome"**
   - Render is headless Linux
   - Need headless browser setup
   - Or use v2 (HTTP API) instead

4. **"Out of memory"**
   - Free tier = 512MB RAM
   - Upgrade to Starter or optimize code
   - Kill long-running processes

---

**Deployment ready! 🚀**
