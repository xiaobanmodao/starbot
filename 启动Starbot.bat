@echo off
chcp 65001 >nul 2>nul
title Starbot
echo === Starbot ===
cd /d "%~dp0"
uv run python start.py
pause
