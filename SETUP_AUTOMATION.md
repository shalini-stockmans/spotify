# Automated Spotify Sync Setup Guide

This guide explains how to set up automated syncing of your Spotify listening data.

## Option 1: GitHub Actions (Recommended for Cloud-Based)

GitHub Actions can run your code automatically on a schedule (hourly, daily, etc.).

**✅ FREE for public repositories!** Unlimited minutes for public repos.

### Setup Steps:

1. **Make your repository public** (or keep it private if you have GitHub Pro)
   - Settings → Scroll down → Change repository visibility → Make public

2. **Push your code to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Add automated sync"
   git push origin main
   ```

2. **Set up GitHub Secrets** (Store your Spotify credentials securely)
   - Go to your GitHub repository
   - Click **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret** and add:
     - `SPOTIFY_CLIENT_ID` - Your Spotify client ID
     - `SPOTIFY_CLIENT_SECRET` - Your Spotify client secret
     - `SPOTIFY_REDIRECT_URL` - Your redirect URL (e.g., `http://localhost:8080`)
     - `SPOTIFY_SCOPE` - Your scopes (e.g., `user-read-recently-played`)

3. **Enable GitHub Actions**
   - Go to **Actions** tab in your repository
   - The workflow will automatically run on schedule or you can manually trigger it

4. **Adjust Schedule** (Optional)
   - Edit `.github/workflows/sync_spotify.yml`
   - Change the cron schedule: `'0 * * * *'` means every hour
   - Cron format: `'minute hour day month weekday'`
     - `'0 * * * *'` - Every hour
     - `'0 */2 * * *'` - Every 2 hours
     - `'0 0 * * *'` - Daily at midnight
     - `'*/30 * * * *'` - Every 30 minutes

### ⚠️ Important Note:
GitHub Actions workflows run in a non-interactive environment, so Spotify OAuth might require a cached token file. You may need to:
1. Run the sync locally once to generate a token cache
2. Store the token cache as a GitHub secret or artifact

---

## Option 2: Windows Task Scheduler (For Local Machine)

Run the sync script on your local Windows machine automatically.

### Setup Steps:

1. **Create a batch file** (`sync_spotify.bat`):
   ```batch
   @echo off
   cd /d "C:\Users\sstockmans\OneDrive - Virtus Real Estate\Documents\Personal\spotify"
   env\Scripts\activate
   python sync_spotify.py
   ```

2. **Set up Task Scheduler**:
   - Open **Task Scheduler** (search in Windows Start menu)
   - Click **Create Basic Task**
   - Name it: "Spotify Sync"
   - Trigger: **Daily** or **When I start my computer**
   - Action: **Start a program**
   - Program: Path to your `sync_spotify.bat` file
   - Or use PowerShell:
     ```powershell
     # Run this in PowerShell as Administrator
     $action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\path\to\sync_spotify.py" -WorkingDirectory "C:\path\to\project"
     $trigger = New-ScheduledTaskTrigger -Daily -At 3am
     Register-ScheduledTask -TaskName "SpotifySync" -Action $action -Trigger $trigger
     ```

---

## Option 3: Linux/Mac Cron Job

For Linux or Mac systems:

1. **Open crontab**:
   ```bash
   crontab -e
   ```

2. **Add a line** to run every hour:
   ```bash
   0 * * * * cd /path/to/spotify && /path/to/python sync_spotify.py
   ```

3. **Or run every 30 minutes**:
   ```bash
   */30 * * * * cd /path/to/spotify && /path/to/python sync_spotify.py
   ```

---

## Option 4: Cloud Services

### Heroku Scheduler (Free tier available)
- Deploy your Flask app to Heroku
- Use Heroku Scheduler add-on
- Schedule `python sync_spotify.py` to run hourly

### AWS Lambda + EventBridge
- Package your sync script as a Lambda function
- Use EventBridge (CloudWatch Events) to trigger hourly
- Note: Requires AWS account and some setup

### PythonAnywhere
- Free tier available
- Can schedule Python tasks to run on a schedule
- Simple web interface for scheduling

---

## Option 5: Keep Your Computer Running (Simplest)

If you keep your computer on all the time, you can:

1. **Run the Flask app continuously**:
   ```bash
   python app.py
   ```

2. **The app will sync automatically** when you visit the dashboard

3. **Or run a simple loop script** (`run_sync_loop.py`):
   ```python
   import time
   import schedule
   from sync_spotify import sync_spotify_data
   
   schedule.every().hour.do(sync_spotify_data)
   
   while True:
       schedule.run_pending()
       time.sleep(60)
   ```

---

## Testing Your Setup

1. **Test the sync script manually**:
   ```bash
   python sync_spotify.py
   ```

2. **Check the database**:
   ```python
   import sqlite3
   conn = sqlite3.connect('spotify_history.db')
   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM listening_history")
   print(f"Total tracks: {cursor.fetchone()[0]}")
   conn.close()
   ```

---

## Troubleshooting

### Authentication Issues
- Make sure your `.env` file has correct credentials
- For GitHub Actions, ensure secrets are set correctly
- Spotify tokens may expire; you might need to re-authenticate periodically

### Schedule Not Running
- Check logs for errors
- Verify cron/Task Scheduler syntax
- Ensure Python environment is correct

### Database Location
- Local: Database is stored in your project directory
- GitHub Actions: Stored as artifact (downloads/uploads between runs)

---

## Recommended Approach

For most users, I recommend:
- **GitHub Actions** if you want cloud-based automation (free)
- **Windows Task Scheduler** if you keep your computer on and want local automation
- **Flask app auto-sync** if you just want it to sync when you visit the dashboard

Choose based on your needs!
