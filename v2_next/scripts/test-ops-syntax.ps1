param([switch]$DesktopOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$roots=@((Join-Path $PSScriptRoot 'server-stage-v1026'),(Join-Path $PSScriptRoot 'server-path-audit'))
$files=@(foreach($root in $roots){Get-ChildItem -LiteralPath $root -File -Filter '*.ps1'})
if(-not $DesktopOnly){$files+=@(Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter '*.ps1')}
$templates=@('launch-template.ps1','prepare-cleanup-batch.template.ps1')
$count=0
foreach($file in $files){
    if($file.Name -cin $templates){continue}
    $tokens=$null;$errors=$null
    [void][Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
    if($errors.Count){throw ($file.Name+': '+(($errors|ForEach-Object{$_.Message})-join '; '))}
    $count++
}
"[PASS] $count PowerShell source parses; DesktopOnly=$DesktopOnly; templates tested after substitution."
