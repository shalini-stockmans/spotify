# GitHub Actions Setup Guide

Complete step-by-step guide to set up automated Spotify syncing with GitHub Actions.

## Prerequisites

- A GitHub account
- Your code ready to push
- Spotify API credentials (Client ID, Client Secret)

---

## Step 1: Push Your Code to GitHub

If you haven't already:

1. **Create a new repository on GitHub**
   - Go to [github.com](https://github.com)
   - Click the **+** icon → **New repository**
   - Name it (e.g., `spotify-dashboard`)
   - Make it **Public** (for free unlimited GitHub Actions)
   - Don't initialize with README (you already have one)
   - Click **Create repository**

2. **Push your code** (if you haven't already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Spotify dashboard"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repository name.

---

## Step 2: Make Repository Public (If Not Already)

GitHub Actions is **FREE** for public repositories with unlimited minutes.

1. Go to your repository on GitHub
2. Click **Settings** (top menu)
3. Scroll down to **Danger Zone**
4. Click **Change repository visibility**
5. Select **Make public**
6. Type your repository name to confirm
7. Click **I understand, change repository visibility**

---

## Step 3: Add GitHub Secrets

This is where you securely store your Spotify credentials.

1. **Go to your repository on GitHub**
2. Click **Settings** (top menu)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret** button (top right)

5. **Add each secret one by one:**

   **Secret 1: SPOTIFY_CLIENT_ID**
   - Name: `SPOTIFY_CLIENT_ID`
   - Value: Your Spotify Client ID (from your `.env` file)
   - Click **Add secret**

   **Secret 2: SPOTIFY_CLIENT_SECRET**
   - Click **New repository secret** again
   - Name: `SPOTIFY_CLIENT_SECRET`
   - Value: Your Spotify Client Secret (from your `.env` file)
   - Click **Add secret**

   **Secret 3: SPOTIFY_REDIRECT_URL**
   - Click **New repository secret** again
   - Name: `SPOTIFY_REDIRECT_URL`
   - Value: `http://localhost:3000` (or whatever you're using)
   - Click **Add secret**

   **Secret 4: SPOTIFY_SCOPE**
   - Click **New repository secret** again
   - Name: `SPOTIFY_SCOPE`
   - Value: `user-read-recently-played`
   - Click **Add secret**

You should now have 4 secrets listed:
- ✅ SPOTIFY_CLIENT_ID
- ✅ SPOTIFY_CLIENT_SECRET
- ✅ SPOTIFY_REDIRECT_URL
- ✅ SPOTIFY_SCOPE

---

## Step 4: Verify Workflow File Exists

Make sure the workflow file is in your repository:

1. Check that `.github/workflows/sync_spotify.yml` exists
2. If it's not there, make sure you've pushed it to GitHub:
   ```bash
   git add .github/workflows/sync_spotify.yml
   git commit -m "Add GitHub Actions workflow"
   git push
   ```

---

## Step 5: Test the Workflow

1. **Go to the Actions tab** in your GitHub repository
2. You should see "Sync Spotify Listening Data" workflow listed
3. Click on it
4. Click **Run workflow** button (top right)
5. Select the branch (usually `main`)
6. Click the green **Run workflow** button

This will manually trigger the workflow to test if everything works.

---

## Step 6: Monitor the Workflow

1. **Watch the workflow run:**
   - Go to **Actions** tab
   - Click on the latest workflow run
   - You'll see it running in real-time

2. **Check for errors:**
   - Green checkmark ✅ = Success
   - Red X ❌ = Error (click to see details)

3. **Common issues:**
   - **Authentication errors**: Spotify OAuth requires interactive login the first time. See "OAuth Setup" below.
   - **Secret errors**: Make sure all 4 secrets are added correctly
   - **Python errors**: Check the workflow logs

---

## ⚠️ Important: Spotify OAuth Setup

GitHub Actions runs in a non-interactive environment, so Spotify OAuth needs special handling.

### Option A: Pre-authenticate Locally (Recommended)

1. **Run the sync locally once** to generate a token cache:
   ```bash
   python sync_spotify.py
   ```
   This will open a browser for you to authenticate.

2. **Find the cache file:**
   - Look for `.cache-*` file in your project directory
   - Or check where spotipy stores it (usually `.cache-USERNAME`)

3. **Add cache as GitHub Secret** (Optional):
   - You can base64 encode the cache file and store it as a secret
   - Then decode it in the workflow before running

### Option B: Use Client Credentials (If Available)

If you only need to read public data, you might be able to use client credentials flow instead of OAuth.

### Option C: Manual First Run

The workflow might fail the first time. After you authenticate locally, the token cache might work in GitHub Actions if you commit it (not recommended for security).

---

## Step 7: Verify It's Running on Schedule

The workflow is set to run **every hour** automatically.

1. **Check the schedule:**
   - Go to **Actions** tab
   - Click on **Sync Spotify Listening Data** workflow
   - You'll see scheduled runs appear

2. **Wait an hour** and check if a new run appears automatically

3. **Or adjust the schedule:**
   - Edit `.github/workflows/sync_spotify.yml`
   - Change the cron schedule (see below)
   - Commit and push:
     ```bash
     git add .github/workflows/sync_spotify.yml
     git commit -m "Update schedule"
     git push
     ```

---

## Schedule Options

Edit the cron schedule in `.github/workflows/sync_spotify.yml`:

```yaml
schedule:
  - cron: '0 * * * *'  # Every hour at minute 0
```

**Common schedules:**
- `'0 * * * *'` - Every hour (current setting)
- `'*/30 * * * *'` - Every 30 minutes
- `'0 */2 * * *'` - Every 2 hours
- `'0 0 * * *'` - Daily at midnight
- `'0 0 * * 0'` - Weekly on Sunday at midnight

**Cron format:** `minute hour day month weekday`

---

## Troubleshooting

### Workflow Not Running
- Check that the workflow file is in `.github/workflows/` directory
- Make sure it's committed and pushed to GitHub
- Verify the cron syntax is correct

### Authentication Errors
- Spotify OAuth requires interactive login the first time
- Run `sync_spotify.py` locally first to authenticate
- The token cache might need to be handled specially for GitHub Actions

### Secrets Not Found
- Double-check secret names match exactly (case-sensitive)
- Make sure you're adding them under **Actions** secrets, not environment secrets
- Verify the secrets are in the correct repository

### Database Not Persisting
- The current workflow creates a fresh database each run
- To persist data, you could:
  - Commit the database back to git (workflow does this optionally)
  - Use a hosted database service
  - Store database as an artifact

---

## Success Checklist

- ✅ Repository is public (or you have GitHub Pro)
- ✅ Code is pushed to GitHub
- ✅ All 4 secrets are added correctly
- ✅ Workflow file exists in `.github/workflows/`
- ✅ Workflow runs successfully when manually triggered
- ✅ Workflow runs automatically on schedule

---

## Next Steps

Once GitHub Actions is working:
- Monitor the **Actions** tab to see runs
- Check that tracks are being synced
- Adjust the schedule if needed
- Consider setting up the dashboard to read from the synced data

---

## Need Help?

- Check workflow logs in the **Actions** tab
- Verify all secrets are set correctly
- Make sure your Spotify app settings match (redirect URI)
- Test the sync script locally first: `python sync_spotify.py`
