[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native PS5.1 x64 required.'}
function ResumeBuildHash {param([byte[]]$Bytes) $sha=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','')}finally{$sha.Dispose()}}
function ResumeNewFile {param([string]$Path,[byte[]]$Bytes)
    $s=[IO.File]::Open($Path,'CreateNew','Write','Read');try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    if((ResumeBuildHash ([IO.File]::ReadAllBytes($Path))) -cne (ResumeBuildHash $Bytes)){throw 'Delivery readback mismatch.'}
}
$utf8=[Text.UTF8Encoding]::new($false,$true)
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$old=Join-Path $workspace 'artifacts\server-cleanup-release-pair-r1'
$output=Join-Path $workspace 'artifacts\server-cleanup-release-pair-resume-r1'
if([IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'Existing resume delivery must not be overwritten.'}
$node=[IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($output))
while($null -ne $node){if($node.Exists -and ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse output ancestor.'};$node=$node.Parent}
$zipBytes=[IO.File]::ReadAllBytes((Join-Path $old 'v1019-release-pair-cleanup-ready-r1.zip'))
if($zipBytes.Length -ne 22604 -or (ResumeBuildHash $zipBytes) -cne '62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3'){throw 'Published ZIP changed.'}
$oldBytes=[IO.File]::ReadAllBytes((Join-Path $old 'RUN_RELEASE_PAIR_CLEANUP.txt'))
if((ResumeBuildHash $oldBytes) -cne '15D4E9EF623B472E9B08E6A08A3B1E9DADF097273835DCC898A53A20123C86E8'){throw 'Published launcher changed.'}
$gate=$utf8.GetString([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'release-pair-resume-gate.ps1')))
$launcher=$utf8.GetString($oldBytes)
$marker='        Initialize-CleanupNative'
if(@([regex]::Matches($launcher,[regex]::Escape($marker))).Count -ne 1){throw 'Ambiguous insertion point.'}
$launcher=$launcher.Replace($marker,($gate+"`n"+$marker+"`n        Invoke-ReleasePairResumeGate `$streams `$launchGuards"))
$child="Set-StrictMode -Version Latest`n`$ErrorActionPreference='Stop'`n`$ProgressPreference='SilentlyContinue'`ntry {`n"+
    $launcher.TrimEnd()+" 6>&1 | ForEach-Object {[Console]::WriteLine([string]`$_)}`nexit 0`n}`ncatch {[Console]::WriteLine('[HOLD] Cleanup resume stopped: '+`$_.Exception.Message);exit 1}`n"
if($child.Contains("`n'@")){throw 'Unexpected here-string terminator in child.'}
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($child))
if($encoded.Length+250 -gt 32000){throw 'Resume child exceeds conservative command-line budget.'}
$prefix=@'
& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
        -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
        throw 'Use native administrator x64 Windows PowerShell 5.1.'
    }
    $childCode=@'
'@
$suffix="'@`n"+@'
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childCode))
    if($encoded.Length+250 -gt 32000){throw 'Child command exceeds launch budget.'}
    Write-Host '[APPROVED] Recheck ACL receipt and existing evidence, then delete ONLY 22 R1 duplicate files. No ACL repair or app changes.' -ForegroundColor Yellow
    & $native -NoLogo -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $encoded
    $code=$LASTEXITCODE
    if($code -ne 0){throw ('Cleanup resume HOLD: exit='+$code+'. Preserve all output/receipts; do not retry.')}
}
'@
$outer=$prefix+"`n"+$child+"`n"+$suffix
foreach($code in @($gate,$launcher,$child,$outer)){
    $t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($code,[ref]$t,[ref]$e)
    if(@($e).Count -ne 0){throw ('Generated resume code parse failed: '+$e[0].Message)}
}
$null=[IO.Directory]::CreateDirectory($output)
ResumeNewFile (Join-Path $output 'RUN_RELEASE_PAIR_CLEANUP_RESUME.txt') ($utf8.GetBytes($outer))
ResumeNewFile (Join-Path $output 'RESUME_GUIDE.md') ([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'RELEASE_PAIR_RESUME_GUIDE.md')))
$result=[pscustomobject]@{result='RELEASE_PAIR_RESUME_PREPARED_NOT_SERVER_EXECUTED';created_at=[DateTimeOffset]::Now.ToString('o');
    launcher=(Join-Path $output 'RUN_RELEASE_PAIR_CLEANUP_RESUME.txt');launcher_sha256=(ResumeBuildHash ($utf8.GetBytes($outer)));
    child_encoded_command_chars=$encoded.Length;existing_zip_sha256='62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3';
    acl_backup_sha256='90EE9F49517AF299AB7A0DBA38053C3B80806DF6E7C662BA765FA754260D9CAD';
    acl_journal_sha256='507678162C3521D2F7909137A92308C2C1F48EACA380865CE97B5C7D8C387C57';
    new_zip_required=$false;server_execution_performed=$false;delete_files=22;delete_bytes=157989430;delete_directories=0}
ResumeNewFile (Join-Path $output 'build-result.json') ($utf8.GetBytes(($result|ConvertTo-Json -Depth 5)))
$result|ConvertTo-Json -Depth 5
