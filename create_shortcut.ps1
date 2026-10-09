# Create Desktop Shortcut for ImageEditor
# Run this once in PowerShell: powershell -ExecutionPolicy Bypass -File create_shortcut.ps1

$WshShell = New-Object -comObject WScript.Shell
$Desktop = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "ImageEditor.lnk")
$Shortcut = $WshShell.CreateShortcut($Desktop)

# Find pythonw automatically
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    $pythonw = "C:\Users\tc06h\AppData\Local\Programs\Python\Python312\pythonw.exe"
}

$scriptPath = "$HOME\Documents\ImageEditor\main.py"

$Shortcut.TargetPath = $pythonw
$Shortcut.Arguments = "`"$scriptPath`""
$Shortcut.WorkingDirectory = "$HOME\Documents\ImageEditor"
$Shortcut.Description = "Photoshop-style AI Image Editor - Milestone 4"
$Shortcut.IconLocation = $pythonw
$Shortcut.Save()

Write-Host "Shortcut created on Desktop: $Desktop"
Write-Host "Target: $pythonw $scriptPath"
