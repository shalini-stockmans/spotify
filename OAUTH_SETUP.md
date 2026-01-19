# Spotify OAuth Setup for GitHub Actions

## The Problem

Spotify OAuth requires **interactive browser authentication** the first time. GitHub Actions runs in a non-interactive environment, so it can't open a browser.

## Solution: Pre-authenticate Locally

You need to authenticate locally first, then commit the token cache to GitHub.

### Step 1: Authenticate Locally

1. **Run the sync script locally:**
   ```bash
   python sync_spotify.py
   ```

2. **A browser will open** - log in to Spotify and authorize the app

3. **A `.cache-*` file will be created** in your project directory (e.g., `.cache-username`)

### Step 2: Commit the Cache File

1. **Find the cache file:**
   ```bash
   ls -la .cache-*
   ```
   Or check your project directory for a file starting with `.cache-`

2. **Add it to git** (but NOT to .gitignore):
   ```bash
   git add .cache-*
   git commit -m "Add Spotify OAuth token cache"
   git push
   ```

3. **Update .gitignore** to allow cache files:
   - Remove or comment out the `.cache` and `.cache-*` lines from `.gitignore`
   - Or add an exception: `!.cache-*`

### Step 3: Update the Script

The script will now:
- ✅ Detect it's running in GitHub Actions
- ✅ Use the cached token (no browser needed)
- ✅ Fail fast with a clear error if no cache exists

## Alternative: Use a Personal Access Token (Advanced)

If you want to avoid committing the cache file, you could:
1. Base64 encode the cache file
2. Store it as a GitHub Secret
3. Decode it in the workflow before running the script

But the simplest approach is to commit the cache file (it's just a token, not your password).

## Verification

After committing the cache file:
1. Push to GitHub
2. Trigger the workflow manually
3. It should authenticate successfully using the cached token

---

**Note:** The token will expire eventually. When it does, you'll need to re-authenticate locally and commit the new cache file.
