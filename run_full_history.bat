@echo off
echo Starting Full Historical Data Extraction (2016-2026)...
echo This process may take several hours.
echo Logs will be saved to Logs/collector.log

cd /d "%~dp0"
python -m v2_next.backend.mes_bridge.collector --from-year 2016 --to-year 2026

echo Extraction Complete!
pause
