REM delete old dist files
rmdir /s /q dist

REM build onionshare-gui.exe
pyinstaller install\pyinstaller.spec -y

REM download tor
python install\get-tor-windows.py

REM TODO: Sign exe

REM build an installer, dist\onionshare-setup.exe
REM makensis.exe install\onionshare.nsi

REM TODO: sign installer exe
