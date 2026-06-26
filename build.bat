@echo off
REM Build standalone exe for len-options-flow
REM Uses --onedir for reliability and smaller file size

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set VENV_PYTHON=C:\Users\WDAGUtilityAccount\crewai-env\Scripts\python.exe

echo Installing PyInstaller...
"%VENV_PYTHON%" -m pip install pyinstaller

echo Building len-options-flow.exe ...
"%VENV_PYTHON%" -m PyInstaller --noconfirm --onedir --console ^
    --name len-options-flow ^
    --add-data "OptionsFlow.md;." ^
    --hidden-import crewai ^
    --hidden-import crewai.flow ^
    --hidden-import pydantic ^
    --hidden-import httpx ^
    --hidden-import openai ^
    --hidden-import chromadb ^
    --hidden-import tokenizers ^
    --hidden-import tiktoken ^
    --hidden-import openai.lib._parsers ^
    --collect-all pydantic ^
    --collect-all crewai ^
    --collect-all chromadb ^
    crewai_demo.py

echo.
echo Build complete. Output in: dist\len-options-flow\
echo Run: dist\len-options-flow\len-options-flow.exe <csv_path>
echo.
pause
