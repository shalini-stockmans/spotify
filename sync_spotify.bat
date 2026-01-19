@echo off
REM Batch file to run Spotify sync script
REM Use this with Windows Task Scheduler

cd /d "%~dp0"
call env\Scripts\activate.bat
python sync_spotify.py
deactivate
