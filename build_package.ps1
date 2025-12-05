# Check for uv
Write-Host "Checking for uv..."
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (using mirror)..."
    pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install uv. Please install it manually."
        exit 1
    }
}

# Create venv
Write-Host "Setting up virtual environment..."

# Try to remove existing venv
if (Test-Path ".venv") {
    Write-Host "Found existing .venv, attempting to clean..."
    Remove-Item -Recurse -Force ".venv" -ErrorAction SilentlyContinue
}

# Create venv with uv
Write-Host "Creating/Updating venv..."
uv venv .venv --python 3.10 --allow-existing
if ($LASTEXITCODE -ne 0) {
    Write-Warning "uv venv failed. Assuming existing venv is usable."
}

# Setup paths
$CurrentDir = Get-Location
$VenvPythonAbs = "$CurrentDir\.venv\Scripts\python.exe"
$VenvScriptsDir = "$CurrentDir\.venv\Scripts"

# Check python.exe and create pyvenv.cfg
if (-not (Test-Path $VenvPythonAbs)) {
    Write-Warning "Could not find python.exe at $VenvPythonAbs"
} 
else {
    Write-Host "Creating pyvenv.cfg..."
    $PyVenvCfg = @(
        "home = $VenvScriptsDir",
        "include-system-site-packages = false",
        "version = 3.10.19"
    )
    $PyVenvCfg | Out-File ".venv\pyvenv.cfg" -Encoding utf8
}

$VenvPython = ".venv\Scripts\python.exe"

# Install dependencies
Write-Host "Installing dependencies from requirements-gpu.txt..."
uv pip install -r requirements-gpu.txt --python $VenvPython --index-url https://pypi.tuna.tsinghua.edu.cn/simple
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install requirements."
    exit 1
}

# Install PyTorch (CUDA 12.1)
Write-Host "Installing PyTorch (CUDA 12.1)..."
uv pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu121 --python $VenvPython
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install PyTorch."
    exit 1
}

# Ensure PyInstaller
Write-Host "Ensuring PyInstaller is installed..."
uv pip install pyinstaller --python $VenvPython --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Build EXE
Write-Host "Building EXE with PyInstaller..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

$PyInstallerPath = ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $PyInstallerPath)) {
    Write-Error "PyInstaller not found at $PyInstallerPath"
    exit 1
}

& $PyInstallerPath build_exe.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

# Package
$ReleaseDir = "release_v2.0_gpu"
Write-Host "Packaging into $ReleaseDir..."
if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

# Copy EXE
$ExeFiles = Get-ChildItem "dist" -Filter "*.exe"
if ($ExeFiles) {
    Copy-Item $ExeFiles.FullName -Destination $ReleaseDir
} else {
    $DistDirs = Get-ChildItem "dist" -Directory
    if ($DistDirs) {
        Copy-Item $DistDirs.FullName -Destination $ReleaseDir -Recurse
    } else {
         Write-Error "No output found in dist/"
         exit 1
    }
}

# Copy resources
$Resources = @("templates", "config", "cookies.txt", "模板.xlsx", "install_ffmpeg.ps1")
foreach ($Res in $Resources) {
    if (Test-Path $Res) {
        Copy-Item -Path $Res -Destination $ReleaseDir -Recurse
        Write-Host "Copied $Res"
    }
}

# Copy FFmpeg
Write-Host "Looking for FFmpeg..."
$ffmpeg = Get-Command "ffmpeg" -ErrorAction SilentlyContinue
if ($ffmpeg) {
    $ffmpegPath = $ffmpeg.Source
    $ffmpegDir = Split-Path $ffmpegPath
    $ffprobePath = Join-Path $ffmpegDir "ffprobe.exe"
    
    Copy-Item $ffmpegPath -Destination $ReleaseDir
    Write-Host "Copied ffmpeg.exe"
    
    if (Test-Path $ffprobePath) {
        Copy-Item $ffprobePath -Destination $ReleaseDir
        Write-Host "Copied ffprobe.exe"
    }
} else {
    Write-Warning "FFmpeg not found. Please install manually."
}

# Readme
$ReleaseReadme = "$ReleaseDir\README.txt"
"Bilibili Video Subtitle Summarizer (GPU Edition)" | Out-File $ReleaseReadme
"================================================" | Out-File $ReleaseReadme -Append
"" | Out-File $ReleaseReadme -Append
"Installation:" | Out-File $ReleaseReadme -Append
"1. Extract all files." | Out-File $ReleaseReadme -Append
"2. Edit cookies.txt with your Bilibili SESSDATA." | Out-File $ReleaseReadme -Append
"3. Run the executable." | Out-File $ReleaseReadme -Append
"" | Out-File $ReleaseReadme -Append
"Note: This version includes GPU support (CUDA 12)." | Out-File $ReleaseReadme -Append
"Ensure you have NVIDIA drivers installed." | Out-File $ReleaseReadme -Append

Write-Host "Build Complete! Output: $ReleaseDir"