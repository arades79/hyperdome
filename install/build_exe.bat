REM delete old dist files
rmdir /s /q dist

REM build onionshare-gui.exe
pyinstaller install\hyperdome_client.spec -y
pyinstaller install\hyperdome_server.spec -y

REM TODO: download tor for standalone tor functionality (not working so disabled)
REM TODO: Sign exe
REM TODO: build an installer, sign it
