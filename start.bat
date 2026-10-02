@echo off
rem Start the writing assistant on Windows.
cd /d "%~dp0"
if "%WRITER_MODEL%"=="" set WRITER_MODEL=llama3.1:8b

where python >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH". & pause & exit /b 1)
where ollama >nul 2>nul || (echo Ollama is not installed. Get it from https://ollama.com/download, open it once, then run this again. & pause & exit /b 1)

ollama list >nul 2>nul || (echo Starting Ollama... & start "" /b ollama serve & timeout /t 3 >nul)
ollama show %WRITER_MODEL% >nul 2>nul || (echo Downloading the AI model %WRITER_MODEL%. This happens once and can take a while... & ollama pull %WRITER_MODEL% || (pause & exit /b 1))

python server.py
pause
