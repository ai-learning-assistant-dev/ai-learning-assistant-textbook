@echo off
chcp 65001 >nul
echo ================================================================================
echo Bilibili Video Subtitle Download and Summary Tool - Build Script
echo ================================================================================
echo.

echo [1/4] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller not found, installing...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo Failed to install PyInstaller, please install manually: pip install pyinstaller
        pause
        exit /b 1
    )
)
echo [OK] PyInstaller is ready
echo.

echo [2/4] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo [OK] Clean completed
echo.

echo [3/4] Starting build...
python -m PyInstaller --clean build_exe.spec
if %errorlevel% neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo [OK] Build completed
echo.

echo Checking generated files...
if exist dist\BilibiliSubtitleSummarizer.exe (
    echo [OK] Found BilibiliSubtitleSummarizer.exe
) else if exist dist\BilibiliSubtitleSummarizer (
    echo [INFO] Found file without extension, renaming...
    ren dist\BilibiliSubtitleSummarizer BilibiliSubtitleSummarizer.exe
    echo [OK] Renamed to BilibiliSubtitleSummarizer.exe
) else (
    echo [ERROR] Generated file not found
    dir dist
    pause
    exit /b 1
)
echo.

echo [4/4] Creating release directory...
if not exist release mkdir release
if exist release\BilibiliSubtitleSummarizer.exe del release\BilibiliSubtibleSummarizer.exe

REM Copy main program
copy dist\BilibiliSubtitleSummarizer.exe release\

REM Create config directories and files
if not exist release\config mkdir release\config
if not exist release\subtitles mkdir release\subtitles

REM Create cookies.txt template
(
echo # Bilibili Cookie Configuration File
echo # Please replace "your_SESSDATA_value" below with your actual SESSDATA
echo # 
echo # How to get SESSDATA:
echo # 1. Login to bilibili.com
echo # 2. Press F12 to open Developer Tools
echo # 3. Go to "Application" tab
echo # 4. Select "Cookies" -^> "https://www.bilibili.com"
echo # 5. Find "SESSDATA" and copy its value
echo # 6. Replace the content below and save
echo # 
echo SESSDATA=your_SESSDATA_value
) > release\cookies.txt

REM Create empty model configuration
(
echo {
echo   "models": []
echo }
) > release\config\llm_models.json

REM Create default app configuration
(
echo {
echo   "output_directory": "subtitles",
echo   "last_selected_model": "",
echo   "cookies_file": "cookies.txt",
echo   "auto_refresh_interval": 2000,
echo   "web_port": 5000
echo }
) > release\config\app_config.json

REM Copy README
copy README.md release\

REM Create usage instructions
(
echo Bilibili Video Subtitle Downloader and Summarizer - Standalone Version
echo ================================================================================
echo.
echo How to Use:
echo 1. Double-click BilibiliSubtitleSummarizer.exe to run
echo 2. Program will start web service automatically ^(first run takes 10-30 seconds^)
echo 3. Open the address shown in browser ^(default: http://127.0.0.1:5000^)
echo 4. Configure models and process videos in web interface
echo.
echo First Time Setup:
echo 1. Edit cookies.txt file and fill in your Bilibili SESSDATA
echo 2. Add at least one LLM model in web interface
echo.
echo Configuration Files:
echo - cookies.txt: Bilibili login credentials ^(required^)
echo - config/app_config.json: Application settings ^(port, output directory, etc^)
echo - config/llm_models.json: LLM model configurations ^(add via web interface^)
echo.
echo Output Directory:
echo - subtitles/: Default output directory for subtitles and summaries
echo.
echo Notes:
echo 1. Make sure firewall allows program to access network
echo 2. First run needs extraction, startup is slower ^(10-30 seconds^)
echo 3. Press Ctrl+C to close the program
echo 4. Do not delete config folder
echo.
echo Features:
echo - Single exe file, no additional dependencies needed
echo - All dependencies are packaged into exe
echo - Auto-extracts to temp directory at runtime
echo.
echo For more information, see README.md
) > release\Usage_Instructions.txt

echo [OK] Release files created
echo.

echo ================================================================================
echo Build Complete! ^(Standalone Version^)
echo ================================================================================
echo.
echo Output directory: release\
echo Executable: BilibiliSubtitleSummarizer.exe
echo Config files: cookies.txt, config\
echo.
echo File List:
echo   BilibiliSubtitleSummarizer.exe  ^(Main program, approx 80-120MB^)
echo   cookies.txt                      ^(Cookie configuration^)
echo   config\                          ^(Configuration directory^)
echo   subtitles\                       ^(Output directory^)
echo   Usage_Instructions.txt           ^(Usage guide^)
echo   README.md                        ^(Detailed documentation^)
echo.
echo Instructions:
echo - Copy all files from release folder to target computer
echo - Double-click BilibiliSubtitleSummarizer.exe to run
echo - First startup takes 10-30 seconds ^(extracting dependencies^)
echo.
pause

