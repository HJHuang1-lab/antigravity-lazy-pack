@echo off
chcp 65001 > nul
cd /d "E:\Python檔案\antigravity-lazy-pack\stock-firebase-app"
echo [%date% %time%] === Starting Auto Update === >> auto_update.log

echo [%date% %time%] 1. Running stock_updater.py... >> auto_update.log
"C:\Users\Daniel\AppData\Local\Programs\Python\Python313\python.exe" stock_updater.py >> auto_update.log 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ❌ Python update failed with code %ERRORLEVEL%! >> auto_update.log
    exit /b %ERRORLEVEL%
)

echo [%date% %time%] 2. Deploying to Firebase Hosting... >> auto_update.log
call "C:\Users\Daniel\AppData\Roaming\npm\firebase.cmd" deploy --only hosting >> auto_update.log 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ❌ Firebase deploy failed with code %ERRORLEVEL%! >> auto_update.log
    exit /b %ERRORLEVEL%
)

echo [%date% %time%] 🎉 Auto Update successfully completed! >> auto_update.log
