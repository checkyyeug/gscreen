@echo off
REM gScreen Windows Runner
REM 
REM Usage:
REM   run.bat          - Run full slideshow
REM   run.bat --sync-only - Sync only
REM   run.bat --display-only - Display only (skip sync)

cd /d %~dp0
python main.py %*
