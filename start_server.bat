@echo off
rem Démarre le site GN Skill Tree (lancé par la tâche planifiée au démarrage de Windows).
rem Le mot de passe Animation est lu dans admin_password.txt, qui n'est pas dans git.
cd /d "%~dp0"
if exist admin_password.txt set /p ADMIN_PASSWORD=<admin_password.txt
rem Écoute seulement sur cet ordi : Tailscale Funnel s'occupe de l'accès depuis internet
set HOST=127.0.0.1
set PYTHONIOENCODING=utf-8
if not exist data mkdir data
".venv\Scripts\python.exe" server.py >> data\server.log 2>&1
