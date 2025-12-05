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
Write-Host "Creating virtual environment..."
if (Test-Path ".venv") {
    Write-Host "Removing existing .venv..."
    Remove-Item -Recurse -Force ".venv"
}

# Create venv with uv
uv venv .venv --python 3.10
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create venv."
    exit 1
}

$VenvPython = ".venv\Scripts\python.exe"

# Install dependencies (using mirror for speed)
Write-Host "Installing dependencies from requirements-gpu.txt..."
uv pip install -r requirements-gpu.txt --python $VenvPython --index-url https://pypi.tuna.tsinghua.edu.cn/simple
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install requirements."
    exit 1
}

# Install PyTorch with CUDA support
# Note: We use the official PyTorch index for CUDA builds.
Write-Host "Installing PyTorch (CUDA 12.1)..."
uv pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu121 --python $VenvPython
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install PyTorch."
    exit 1
}

# Ensure PyInstaller is installed
Write-Host "Ensuring PyInstaller is installed..."
uv pip install pyinstaller --python $VenvPython --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Build EXE
Write-Host "Building EXE with PyInstaller..."
# Clean previous build
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

& ".venv\Scripts\pyinstaller" build_exe.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

# Package for distribution
$ReleaseDir = "release_v2.0_gpu"
Write-Host "Packaging into $ReleaseDir..."
if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

# Copy EXE
$ExeFiles = Get-ChildItem "dist" -Filter "*.exe"
if ($ExeFiles) {
    Copy-Item $ExeFiles.FullName -Destination $ReleaseDir
} else {
    # Check for directory mode
    $DistDirs = Get-ChildItem "dist" -Directory
    if ($DistDirs) {
        Copy-Item $DistDirs.FullName -Destination $ReleaseDir -Recurse
    } else {
         Write-Error "No output found in dist/"
         exit 1
    }
}

# Copy resources
$Resources = @("templates", "config", "cookies.txt", "模板.xlsx")
foreach ($Res in $Resources) {
    if (Test-Path $Res) {
        Copy-Item -Path $Res -Destination $ReleaseDir -Recurse
        Write-Host "Copied $Res"
    }
}

# Create readme for release
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

Write-Host "Build and Packaging Complete! Output in $ReleaseDir"
