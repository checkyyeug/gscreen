@echo off
REM gScreen Windows Sync Only
REM Syncs files from Google Drive

cd /d %~dp0
python main.py --sync-only
