@echo off
rem Filtre dollar L4.1 : met a jour Ecurie_DXY.txt dans les terminaux.
rem Double-clic une fois par jour (ou ajouter au demarrage de Windows).
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0dxy_filtre.py"
pause
