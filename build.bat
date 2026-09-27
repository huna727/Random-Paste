@echo off
REM Run this on Windows, from inside the random_paste folder.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :error

echo Building RandomPaste.exe...
python -m PyInstaller --noconsole --onefile --name RandomPaste main.py
if errorlevel 1 goto :error

echo.
echo Done. Find it at dist\RandomPaste.exe
pause
goto :eof

:error
echo.
echo Build failed - see the errors above.
pause
