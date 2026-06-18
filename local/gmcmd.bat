@echo off
title Pockie Ninja - GM Commands
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "BASE=http://127.0.0.1:8080"

echo ============================================
echo   Pockie Ninja - GM Command Helper
echo ============================================
echo.

:menu
echo  [1] Add Gold         [6] List Accounts
echo  [2] Add Coin         [7] Max Gold + Coin
echo  [3] Add EXP          [8] Max Level
echo  [4] Add Item         [9] Custom SQL
echo  [5] Set Level        [0] Open Admin Panel
echo  [Q] Quit
echo.
set /p "choice=Select: "

if /i "%choice%"=="q" goto :eof
if "%choice%"=="0" (
    start "" "%BASE%/admin.html"
    goto menu
)
if "%choice%"=="1" (
    set /p "val=Gold amount: "
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=addgold&arg1=!val!&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="2" (
    set /p "val=Coin amount: "
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=addcoin&arg1=!val!&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="3" (
    set /p "val=EXP amount: "
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=addexp&arg1=!val!&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="4" (
    set /p "iid=Item ID: "
    set /p "amt=Amount [1]: " || set "amt=1"
    if "!amt!"=="" set "amt=1"
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=additem&arg1=!iid!&arg2=!amt!&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="5" (
    set /p "val=Level: "
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=setlevel&arg1=!val!&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="6" (
    curl -s "%BASE%/gmcmd.php?cmd=list_accounts"
    echo.
    goto menu
)
if "%choice%"=="7" (
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=max_gold&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="8" (
    set /p "uid=Target UID [1]: " || set "uid=1"
    if "!uid!"=="" set "uid=1"
    curl -s "%BASE%/gmcmd.php?cmd=max_level&uid=!uid!"
    echo.
    goto menu
)
if "%choice%"=="9" (
    set /p "sql=SQL: "
    curl -s "%BASE%/gmcmd.php?cmd=custom&arg1=!sql!"
    echo.
    goto menu
)

echo Invalid choice.
goto menu
