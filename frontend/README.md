# Frontend for Vercel Deployment
# Copy this folder to a separate GitHub repository for Vercel deployment

This folder contains the Vite-based frontend for the Attendance Dashboard.

## Quick Start

```bash
npm install
npm run dev      # Development server
npm run build    # Production build
```

## Deployment to Vercel

1. Create a new GitHub repository for this frontend folder
2. Push the code to GitHub
3. Connect to Vercel (vercel.com)
4. Select the repository
5. Add environment variable:
   - Key: `VITE_API_URL`
   - Value: `https://your-render-backend.onrender.com`
6. Deploy!

## Environment Variables

- `VITE_API_URL`: Backend API URL (defaults to http://localhost:5000 for development)

## File Structure

- `index.html` - Login page
- `dashboard.html` - Main dashboard (to be created)
- `src/api.js` - API client for backend communication
- `vite.config.js` - Vite configuration
- `vercel.json` - Vercel deployment configuration
