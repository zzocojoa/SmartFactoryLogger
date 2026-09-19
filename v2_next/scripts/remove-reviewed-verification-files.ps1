[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$ExpectedIndexSha256,
    [Parameter(Mandatory)][string[]]$PlanIds
)
# LOCAL ONLY. Explicit files, never recursive deletion or server operations.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major -lt 7){throw 'Local cleanup requires PowerShell 7; never send this tool to the server'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$registry=Join-Path $repo 'verification-files.local.json'
function AssertPlain([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path)
    $node=[IO.FileInfo]::new($full)
    while($null-ne$node) {
        if(([IO.File]::GetAttributes($node.FullName)-band[IO.FileAttributes]::ReparsePoint)-ne 0){throw "Link boundary: $full"}
        if($node-is[IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function Hash([string]$Path){[void](AssertPlain $Path);return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash}
[void](AssertPlain $registry)
if((Hash $registry)-cne$ExpectedIndexSha256){throw 'Management file hash mismatch'}
$index=Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json
if($index.host-ine[Environment]::MachineName-or$index.workspace-ine$repo){throw 'Wrong development host/workspace'}
$allowed=@(
 'artifacts\v1026-electron44-local-validation-20260911\electron41-dist',
 'artifacts\v1026-electron44-local-validation-20260911\package-check',
 '.tmp_electron_cache',
 '.tmp\v1023-stage-helper-test-20260903\destination2',
 '.tmp\v1023-stage-helper-test-20260903\destination3',
 'artifacts\_validate_field_kit_20260717_200829',
 'artifacts\_validate_field_kit_20260717_203214',
 'artifacts\_validate_runtime-error-root-cause-validation-field-kit-20260721_120623',
 'artifacts\_validate_runtime-error-root-cause-validation-field-kit-20260721_133001'
) | ForEach-Object {[IO.Path]::GetFullPath((Join-Path $repo $_))}
function AssertTarget([string]$Path) {
    $full=AssertPlain $Path
    if(-not$full.StartsWith($repo+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Workspace escape'}
    if(-not@($allowed|Where-Object {$full-ieq$_-or$full.StartsWith($_+'\',[StringComparison]::OrdinalIgnoreCase)}).Count){throw "Unapproved target: $full"}
}
$plans=@($index.plans|Where-Object {$_.id-cin$PlanIds})
if($plans.Count-ne$PlanIds.Count-or@($plans|Where-Object state -cne 'PLANNED_NOT_DELETED').Count){throw 'Missing, duplicate, or already attempted plan'}
$targets=@($plans|ForEach-Object {$_.files})
$directories=@($plans|ForEach-Object {$_.directories}|Sort-Object -Unique)
$tracked=@{}
foreach($p in @(git -C $repo ls-files)){ $tracked[[IO.Path]::GetFullPath((Join-Path $repo $p))]=$true }
if($LASTEXITCODE-ne 0){throw 'Git tracking check failed'}
$targetPaths=@{}
foreach($f in $targets){
    AssertTarget $f.path
    if($tracked.ContainsKey($f.path)-or$targetPaths.ContainsKey($f.path)){throw 'Tracked or duplicate target'}
    $targetPaths[$f.path]=$true
    if((Get-Item -LiteralPath $f.path).Length-ne$f.bytes-or(Hash $f.path)-cne$f.sha256){throw "Changed candidate: $($f.path)"}
    # The stream provider needs the extended path for historical names >260 chars.
    $streams=@(Get-Item -LiteralPath ('\\?\'+$f.path) -Stream '*' | Where-Object Stream -notin @(':$DATA','Zone.Identifier'))
    if($streams.Count){throw 'Unreviewed alternate data stream'}
    if($f.PSObject.Properties.Name-contains'retained_copy'){
        if($targetPaths.ContainsKey($f.retained_copy)-or(Hash $f.retained_copy)-cne$f.sha256){throw 'Retained duplicate missing or changed'}
    }
}
foreach($f in $targets){if($f.PSObject.Properties.Name-contains'retained_copy'-and$targetPaths.ContainsKey($f.retained_copy)){throw 'Retained copy is also a deletion target'}}
foreach($d in $directories){
    AssertTarget $d
    foreach($child in @(Get-ChildItem -LiteralPath $d -Force)){
        if($child.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'New reparse child'}
        if($child.PSIsContainer){if($child.FullName -inotin $directories){throw 'Unexpected directory'}}
        elseif(-not$targetPaths.ContainsKey($child.FullName)){throw 'Unexpected file'}
    }
}
function AssertNotReferenced {
    $refs=[Collections.Generic.List[string]]::new()
    foreach($p in @(Get-CimInstance Win32_Process)){if($p.ProcessId-ne$PID){$refs.Add([string]$p.ExecutablePath);$refs.Add([string]$p.CommandLine)}}
    foreach($s in @(Get-CimInstance Win32_Service)){$refs.Add([string]$s.PathName)}
    foreach($t in @(Get-ScheduledTask -ErrorAction Stop)){foreach($a in $t.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){if($a.PSObject.Properties[$field]){$refs.Add([string]$a.$field)}}}}
    $shell=New-Object -ComObject WScript.Shell
    try {
        foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
            if(-not[IO.Directory]::Exists($base)){continue}
            foreach($lnk in @(Get-ChildItem -LiteralPath $base -Filter '*.lnk' -File -Recurse -ErrorAction Stop)){
                $shortcut=$shell.CreateShortcut($lnk.FullName);$refs.Add([string]$shortcut.TargetPath);$refs.Add([string]$shortcut.Arguments);$refs.Add([string]$shortcut.WorkingDirectory)
            }
        }
    }finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    foreach($root in $allowed){
        if(-not@($targets|Where-Object {$_.path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)}).Count){continue}
        foreach($reference in $refs){if($reference.IndexOf($root,[StringComparison]::OrdinalIgnoreCase)-ge 0-or$reference.Replace('/','\').IndexOf($root,[StringComparison]::OrdinalIgnoreCase)-ge 0){throw "In-use or registered target: $root"}}
    }
}
AssertNotReferenced
Write-Host ('[VERIFIED PLAN] files='+$targets.Count+' bytes='+($targets|Measure-Object bytes -Sum).Sum+'; permanent deletion; reports and retained copies preserved.')
if(-not$PSCmdlet.ShouldProcess(($plans.id-join','),'Permanently delete the exact verified local files')){return}
function SaveIndex {
    $index.updated_at=[DateTimeOffset]::Now.ToString('o')
    [void](AssertPlain $registry)
    $staging=$registry+'.writing'
    $stream=[IO.File]::Open($staging,'CreateNew','Write','None')
    try{$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($index|ConvertTo-Json -Depth 35 -Compress));$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    [IO.File]::Move($staging,$registry,$true)
}
$event=[pscustomobject]@{at=[DateTimeOffset]::Now.ToString('o');kind='LOCAL_PERMANENT_DELETE';plan_ids=$PlanIds;state='IN_PROGRESS';deleted_files=0;deleted_bytes=0L;deleted_directories=0;error=$null}
$index.history=@($index.history)+$event
foreach($plan in $plans){$plan.state='DELETING'}
SaveIndex
try {
    foreach($f in $targets){
        AssertTarget $f.path
        if((Hash $f.path)-cne$f.sha256){throw 'Target changed before removal'}
        if($f.PSObject.Properties.Name-contains'retained_copy'-and(Hash $f.retained_copy)-cne$f.sha256){throw 'Retained duplicate changed before removal'}
        Remove-Item -LiteralPath ('\\?\'+$f.path) -Force -ErrorAction Stop
        $f.state='DELETED';$event.deleted_files++;$event.deleted_bytes+=[long]$f.bytes
    }
    foreach($d in @($directories|Sort-Object Length -Descending)){
        AssertTarget $d
        if(@(Get-ChildItem -LiteralPath $d -Force).Count){throw 'Directory changed before empty removal'}
        Remove-Item -LiteralPath ('\\?\'+$d) -Force -ErrorAction Stop
        $event.deleted_directories++
    }
    foreach($f in $targets){if(Test-Path -LiteralPath $f.path){throw 'Deleted file remains'}}
    foreach($plan in $plans){$plan.state='COMPLETE'}
    $event.state='COMPLETE'
}catch{$event.state='PARTIAL_STOPPED';$event.error=$_.Exception.Message;foreach($plan in $plans){$plan.state='PARTIAL_STOPPED'};throw}
finally{SaveIndex}
$event | ConvertTo-Json -Depth 4
