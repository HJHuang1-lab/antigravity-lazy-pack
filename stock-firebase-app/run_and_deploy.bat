@echo off
chcp 65001 > nul
echo ==================================================
echo 🚀 AI 記憶體股市助理 - 開始執行本地更新與 Firebase 部署
echo ==================================================
echo.

:: 1. 執行 Python 數據更新器
echo 🔄 [Step 1/2] 正在執行 Python 收集最新的股市數據與 Gemini 日報...
python stock_updater.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 數據更新失敗！請確認 Python 環境與依賴套件是否設定正確。
    pause
    exit /b %ERRORLEVEL%
)

echo.
:: 2. 部署到 Firebase Hosting
echo 🚀 [Step 2/2] 正在將專案部署至 Firebase Hosting 雲端...
cmd /c firebase deploy --only hosting

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ 部署失敗！如果您尚未登入 Firebase，請在終端機中執行：
    echo     cmd /c firebase login
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==================================================
echo 🎉 恭喜！資料更新與 Firebase 雲端部署完全成功！
echo ==================================================
echo.
pause
