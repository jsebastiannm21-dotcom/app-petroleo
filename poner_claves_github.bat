@echo off
rem Doble clic: pone en GitHub las claves de las tareas en la nube (las lee de .env, no las muestra).
cd /d "%~dp0"
python poner_claves_github.py
pause
