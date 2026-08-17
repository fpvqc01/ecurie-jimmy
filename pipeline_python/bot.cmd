@echo off
rem Raccourci : lance le bot avec le bon Python sans dependre du PATH.
rem   bot            -> analyse + ordres sur compte demo
rem   bot --dry-run  -> analyse seulement
rem   bot backtest   -> backtest
rem   bot dashboard  -> plateforme web privee sur http://localhost:5000
rem   bot ftmo-bias  -> ecrit le biais macro pour l'EA MetaTrader 5
if "%1"=="backtest" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0backtest.py" %2 %3 %4 %5 %6
) else if "%1"=="ftmo-bias" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0export_bias.py"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0export_news.py"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0export_vol.py"
) else if "%1"=="ftmo-news" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0export_news.py"
) else if "%1"=="dashboard" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0dashboard.py"
) else (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0run.py" %*
)
