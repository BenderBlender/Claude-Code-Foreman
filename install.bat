@echo off
chcp 65001 >nul
rem Foreman (Прораб) installer for Windows: double-click and drag the project folder into the window, or drop the folder onto this file.
rem English messages: install.bat "C:\path\to\project" --lang en      Remove: install.bat "C:\path\to\project" --uninstall
where py >nul 2>nul && (py -3 "%~dp0install.py" %* & goto :end)
where python >nul 2>nul && (python "%~dp0install.py" %* & goto :end)
echo Python 3.8+ не найден. Установите его с https://www.python.org/downloads/ (галочка «Add python.exe to PATH») и запустите снова.
echo Python 3.8+ was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run again.
:end
pause
