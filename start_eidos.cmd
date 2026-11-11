@echo off
setlocal
pushd "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
    echo Eidos: project Python was not found in .venv\Scripts\python.exe.
    pause
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -X faulthandler -m eidos %*
set "EIDOS_EXIT_CODE=%ERRORLEVEL%"
if not "%EIDOS_EXIT_CODE%"=="0" (
    echo Eidos stopped with error %EIDOS_EXIT_CODE%. See the message above.
    pause
)
popd
exit /b %EIDOS_EXIT_CODE%
