import os

script_content = """
# MES Folder Consolidation Script (English -> Korean)
# Reads page_structures.json to map 'key' (English) to 'name' (Korean)
# Moves .json files from English folders to Korean folders in the specified roots.

# Force console output encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$jsonPath = "C:\\Users\\user\\Documents\\GitHub\\SmartFactoryLogger\\v2_next\\backend\\mes_bridge\\data\\page_structures.json"
$baseDir = "C:\\Users\\user\\Documents\\GitHub\\SmartFactoryLogger\\mes_data"

# Verify JSON exists
if (-not (Test-Path $jsonPath)) {
    Write-Error "Config file not found: $jsonPath"
    exit
}

# 1. Dynamically find the 3 root folders
Write-Host "Scanning for data folders in: $baseDir"
$roots = @()
$potentialDirs = Get-ChildItem -Path $baseDir -Directory

foreach ($dir in $potentialDirs) {
    # Check for layout 1: .../1번/mes_data
    $path1 = Join-Path $dir.FullName "mes_data"
    if (Test-Path $path1) {
        $roots += $path1
        Write-Host "Found target: $path1"
    }

    # Check for layout 2: .../2번/mac_dist/mes_data
    $path2 = Join-Path $dir.FullName "mac_dist\\mes_data"
    if (Test-Path $path2) {
        $roots += $path2
        Write-Host "Found target: $path2"
    }
}

if ($roots.Count -eq 0) {
    Write-Error "No 'mes_data' folders found!"
    exit
}

# 2. Load Mapping
Write-Host "`nReading page structures..."
try {
    $jsonContent = Get-Content $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "✔ JSON configuration loaded successfully."
}
catch {
    Write-Error "Failed to parse JSON: $_"
    exit
}

# 3. Process each page
foreach ($page in $jsonContent.pages) {
    if (-not $page.key -or -not $page.name) { continue }

    $engName = $page.key
    # Clean Korean name to match legacy folder convention (Space/Slash -> Underscore)
    $korName = $page.name.Replace(" ", "_").Replace("/", "_")

    if ($engName -eq $korName) { continue }

    foreach ($root in $roots) {
        # Try to find category folder
        $category = $page.category
        if (-not $category) { continue }

        $srcPath = Join-Path (Join-Path $root $category) $engName
        $dstPath = Join-Path (Join-Path $root $category) $korName

        # Check if Source (English) exists
        if (Test-Path $srcPath) {
            # Check if Target (Korean) exists, create if not
            if (-not (Test-Path $dstPath)) {
                New-Item -ItemType Directory -Path $dstPath -Force | Out-Null
                Write-Host " [+Created Directory] $dstPath"
            }

            # Move JSON files
            $files = Get-ChildItem -Path $srcPath -Filter "*.json"
            if ($files.Count -gt 0) {
                Write-Host " [Moving] $($files.Count) files: '$engName' -> '$korName' (Location: $($root | Split-Path -Leaf))"
                $files | Move-Item -Destination $dstPath -Force
            }

            # Remove Source if empty
            if ((Get-ChildItem -Path $srcPath).Count -eq 0) {
                Remove-Item -Path $srcPath -Force -Recurse
                # Write-Host " [Removed] Empty folder: $srcPath"
            }
        }
    }
}

Write-Host "`n✔ Consolidation Complete! All English folders merged into Korean folders."
"""

target_file = r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\backend\consolidate_folders.ps1"

with open(target_file, "w", encoding="utf-8-sig") as f:
    f.write(script_content)

print(f"Successfully created: {target_file}")
