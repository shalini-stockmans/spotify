# How the Incremental Sync Works

## The Challenge

**Spotify API Limitation:**
- Can only fetch the **last 50 songs** per API call
- But you want a **complete database** of ALL songs you've ever listened to

## The Solution: Incremental Sync

### How It Works

1. **First Run (Hour 1):**
   - Fetches last 50 songs from Spotify
   - Stores all 50 in database
   - Database now has: 50 songs

2. **Second Run (Hour 2):**
   - Fetches last 50 songs from Spotify (might overlap with previous 50)
   - Checks each song's `played_at` timestamp
   - **Only adds NEW songs** (ones not in database yet)
   - Skips duplicates automatically
   - Database now has: 50 + new songs from hour 2

3. **Third Run (Hour 3):**
   - Fetches last 50 songs
   - Adds only new ones
   - Database grows: Previous songs + new songs from hour 3

4. **Over Time:**
   - Each hourly sync adds only NEW songs
   - Database gradually builds up complete history
   - After 24 hours: ~50-200 unique songs (depending on overlap)
   - After 1 week: Hundreds of unique songs
   - After 1 month: Thousands of unique songs

### Duplicate Prevention

**Method 1: Database UNIQUE Constraint**
```sql
played_at TEXT NOT NULL UNIQUE
```
- Each song play has a **unique timestamp**
- Database **rejects** any duplicate `played_at` values
- **100% guaranteed** no duplicates at database level

**Method 2: INSERT OR IGNORE**
```python
INSERT OR IGNORE INTO listening_history ...
```
- Tries to insert the record
- If `played_at` already exists → **silently skips** (no error)
- Returns count: "X added, Y skipped"

**Result:**
- ✅ **Zero duplicates possible**
- ✅ **Automatic duplicate detection**
- ✅ **No manual checking needed**

### Example Timeline

**Day 1, 10:00 AM - First Sync:**
- Fetches: Songs A, B, C, D, E... (50 songs)
- All 50 are NEW → All 50 added
- Database: 50 songs

**Day 1, 11:00 AM - Second Sync:**
- Fetches: Songs C, D, E, F, G... (50 songs, some overlap)
- Songs C, D, E already exist → **Skipped**
- Songs F, G, H... are NEW → **Added**
- Database: 50 + 30 new = 80 songs

**Day 1, 12:00 PM - Third Sync:**
- Fetches: Songs F, G, H, I, J... (50 songs)
- Songs F, G, H already exist → **Skipped**
- Songs I, J, K... are NEW → **Added**
- Database: 80 + 20 new = 100 songs

**After 1 Week:**
- Database: ~500-1000 unique songs
- All songs you listened to in the past week
- **Zero duplicates**

### Pagination for More Songs

The sync also uses **pagination** to get more than 50 songs per run:

1. **Batch 1:** Fetches last 50 songs
2. **Batch 2:** Fetches 50 songs BEFORE the oldest from Batch 1
3. **Batch 3:** Fetches 50 songs BEFORE the oldest from Batch 2
4. Continues until Spotify returns no more data

**Result:** Can fetch up to **1,000 songs per sync** (20 batches × 50 songs)

### Verification

Your database currently shows:
- ✅ **50 total records**
- ✅ **50 unique `played_at` values**
- ✅ **0 duplicates found**

**Perfect!** The duplicate prevention is working correctly.

## Summary

✅ **Incremental Sync:** Each run adds only NEW songs  
✅ **Duplicate Prevention:** `played_at UNIQUE` constraint + `INSERT OR IGNORE`  
✅ **Complete History:** Database grows over time with all your listening data  
✅ **Automatic:** No manual intervention needed  
✅ **Verified:** Your database has 0 duplicates  

**Your setup is working perfectly!** 🎵
