param(
  [int]$GridRow = 20,
  [int]$GridMargin = 4,
  [int]$GridCols = 60
)

$ErrorActionPreference = "Stop"

function Write-TextFile {
  param(
    [string]$Path,
    [string]$Content
  )

  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Update-GridConstants {
  param(
    [string]$Path,
    [int]$Row,
    [int]$Margin,
    [int]$Cols
  )

  if (-not (Test-Path $Path)) {
    Write-Warning "Skip: $Path (not found)"
    return $false
  }

  $content = [System.IO.File]::ReadAllText($Path)
  $content = $content -replace "const GRID_CELL_HEIGHT = \\d+;", "const GRID_CELL_HEIGHT = $Row;"
  $content = $content -replace "const GRID_CELL_VMARGIN = \\d+;", "const GRID_CELL_VMARGIN = $Margin;"
  $content = $content -replace "const GRID_COLUMN_COUNT = \\d+;", "const GRID_COLUMN_COUNT = $Cols;"
  Write-TextFile -Path $Path -Content $content
  return $true
}

function Update-GridCss {
  param(
    [string]$Path,
    [int]$Row,
    [int]$Margin,
    [int]$Cols
  )

  if (-not (Test-Path $Path)) {
    Write-Warning "Skip: $Path (not found)"
    return $false
  }

  $content = [System.IO.File]::ReadAllText($Path)
  $content = $content -replace "--grid-cols: \\d+;", "--grid-cols: ${Cols};"
  $content = $content -replace "--grid-gap: \\d+px;", "--grid-gap: ${Margin}px;"
  $content = $content -replace "--grid-row: \\d+px;", "--grid-row: ${Row}px;"
  Write-TextFile -Path $Path -Content $content
  return $true
}

$root = Split-Path -Parent $PSScriptRoot
$targets = @(
  Join-Path $root "frontend\\node_modules\\@grafana\\scenes\\dist\\index.js",
  Join-Path $root "frontend\\node_modules\\@grafana\\scenes\\dist\\esm\\packages\\scenes\\src\\components\\layout\\grid\\constants.js"
)

$updated = 0
foreach ($path in $targets) {
  if (Update-GridConstants -Path $path -Row $GridRow -Margin $GridMargin -Cols $GridCols) {
    $updated += 1
  }
}

$cssPath = Join-Path $root "frontend\\src\\App.css"
if (Update-GridCss -Path $cssPath -Row $GridRow -Margin $GridMargin -Cols $GridCols) {
  $updated += 1
}

Write-Host ("Updated files: {0}" -f $updated)
