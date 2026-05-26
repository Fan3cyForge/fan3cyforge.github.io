@echo off
setlocal
cd /d "%~dp0"

echo [info] 正在自動激活 Anaconda (tripo_env) 環境...
rem 檢查系統常見的 Anaconda/Miniconda 安裝路徑並呼叫激活腳本
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" tripo_env
) else if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" tripo_env
) else (
    echo [warn] 未能自動定位 activate.bat，將嘗試使用當前終端環境執行。
)

echo [info] 開始執行 Python 同步腳本...
python scripts\sync_assets.py %*
if errorlevel 1 (
  echo.
  echo [failed] sync_assets.py 執行時發生錯誤。
  pause
  exit /b 1
)
echo.
echo [ok] 全套 Pipeline 運作完畢，已成功生成/洗淨 JSON！
pause
