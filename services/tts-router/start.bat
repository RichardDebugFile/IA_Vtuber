@echo off
:: TTS Router - Inicio Manual
:: Puerto: 8810

set PYTHON=..\..\.venv\Scripts\python.exe
if not exist %PYTHON% set PYTHON=..\..\venv\Scripts\python.exe

set SERVER=%~dp0server.py

echo Iniciando TTS Router en http://127.0.0.1:8810
%PYTHON% "%SERVER%"
