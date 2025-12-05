# Script to install FFmpeg
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$downloadPath = "$env:TEMP\ffmpeg.zip"
$installDir = "C:\ffmpeg"
$binDir = "$installDir\bin"

Write-Host "Downloading FFmpeg..."
Invoke-WebRequest -Uri $ffmpegUrl -OutFile $downloadPath

Write-Host "Extracting FFmpeg..."
if (Test-Path $installDir) {
    Remove-Item -Recurse -Force $installDir
}
Expand-Archive -Path $downloadPath -DestinationPath $env:TEMP -Force

# Move to C:\ffmpeg
$extractedDir = Get-ChildItem -Path "$env:TEMP\ffmpeg-master-latest-win64-gpl" -Directory
if ($extractedDir) {
    Move-Item -Path $extractedDir.FullName -Destination $installDir -Force
} else {
    # Try to find where it extracted
    $dirs = Get-ChildItem -Path "$env:TEMP" -Filter "ffmpeg-*" -Directory
    if ($dirs) {
        Move-Item -Path $dirs[0].FullName -Destination $installDir -Force
    } else {
        Write-Error "Could not find extracted directory"
        exit 1
    }
}

Write-Host "Adding to PATH..."
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$binDir*") {
    $newPath = "$currentPath;$binDir"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $binDir to User PATH"
} else {
    Write-Host "$binDir already in PATH"
}

# Also update current session path so we can use it immediately
$env:Path += ";$binDir"

Write-Host "FFmpeg installed successfully!"
ffmpeg -version
