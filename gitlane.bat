@echo off
chcp 65001 >nul
set PYTHONUTF8=1
call "C:\Users\zalak\OneDrive\Desktop\Projects\gitmind_v2\gitmind_v2\.venv\Scripts\activate.bat"
cd /d "C:\Users\zalak\OneDrive\Desktop\Projects\gitmind_v2\gitmind_v2"
python main.py %* 
