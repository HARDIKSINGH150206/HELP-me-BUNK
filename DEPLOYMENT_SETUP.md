DEPLOYMENT SETUP GUIDE
======================

## Option 1: Separate Frontend & Backend (Recommended)

### Backend (Flask API) → Render

1. Keep your current `app.py` and all Python files on Render
2. Updated `render.yaml` is ready to use
3. Add environment variables on Render dashboard:
   - MONGODB_URI: your_mongo_connection_string
   - SECRET_KEY: generate_a_secure_random_string
   - FRONTEND_URL: https://your-frontend-vercel-app.vercel.app

4. Deploy:
   ```bash
   git push
   # Render auto-deploys from GitHub
   ```

### Frontend (Static/JS) → Vercel

1. Copy the entire `/frontend` folder to a separate GitHub repository or keep it in a separate directory
2. Create a new Vercel project:
   - Connect to your GitHub repo
   - Set build command: `npm run build`
   - Set output: `dist`

3. Add environment variable in Vercel dashboard:
   - VITE_API_URL: https://your-render-backend.onrender.com

4. Deploy:
   ```bash
   git push
   # Vercel auto-deploys from GitHub
   ```

## Setup Instructions

### Step 1: Install Dependencies
```bash
cd /path/to/attendance-project
pip install -r requirements.txt
npm --prefix frontend install
```

### Step 2: Update Files
- `requirements.txt` ✓ (Added flask-cors)
- `app.py` ✓ (Added CORS support)
- `render.yaml` ✓ (Updated for API-only backend)
- `.env.local` ✓ (Configuration template)

### Step 3: Test Locally
```bash
# Terminal 1: Start Flask backend
python app.py

# Terminal 2: Start frontend dev server
cd frontend
npm run dev
```

Access frontend at `http://localhost:3000`

### Step 4: Deploy to Render & Vercel

**For GitHub Integration:**
1. Push code to GitHub
2. Connect GitHub repo to Render (Settings → GitHub)
3. Create separate Vercel project from `/frontend` folder

## Environment Variables Needed

**Backend (Render):**
- MONGODB_URI
- SECRET_KEY
- FRONTEND_URL

**Frontend (Vercel):**
- VITE_API_URL (your render backend URL)

## Important Notes

1. **CORS is now enabled** for the API endpoints
2. **Frontend uses relative API paths** - configured to use VITE_API_URL
3. **Sessions are maintained** via cookies with credentials: 'include'
4. **Auto-sync and scheduler** remain on the backend

## Testing CORS

If you get CORS errors, verify:
1. FRONTEND_URL is set correctly on Render
2. API requests use credentials: 'include'
3. Backend is accessible from frontend URL
4. Check browser console for specific CORS error messages
