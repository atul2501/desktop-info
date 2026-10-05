@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --noconsole --clean --name PCInfo --icon assets/icon.ico --add-data "assets;assets" pc_info.py
echo.
echo Done. Your exe is at dist\PCInfo.exe
pause
