# Read-only, sanitized reference snapshot. No process, service, task or file changes.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$boundary=Join-Path $repo 'dist'
$hits=[Collections.Generic.List[object]]::new()
$counts=@{processes=0;processes_without_readable_command_line=0;services=0;tasks=0;shortcuts=0;skipped_links=0}
function InspectReference([string]$Value,[string]$Kind,[string]$Id) {
    if([string]::IsNullOrWhiteSpace($Value)){return}
    $normalized=$Value.Replace('/','\')
    $offset=$normalized.IndexOf($boundary,[StringComparison]::OrdinalIgnoreCase)
    if($offset-lt 0){return}
    $end=$offset+$boundary.Length
    if($end-eq$normalized.Length-or$normalized[$end]-in @('\','"',"'",' ')){
        $hits.Add([pscustomobject]@{kind=$Kind;id=$Id})
    }
}
foreach($item in @(Get-CimInstance Win32_Process)){
    if($item.ProcessId-eq$PID){continue}
    $counts.processes++
    if([string]::IsNullOrWhiteSpace($item.CommandLine)){$counts.processes_without_readable_command_line++}
    InspectReference ([string]$item.CommandLine) 'process' ([string]$item.ProcessId)
    InspectReference ([string]$item.ExecutablePath) 'process' ([string]$item.ProcessId)
}
foreach($item in @(Get-CimInstance Win32_Service)){
    $counts.services++;InspectReference ([string]$item.PathName) 'service' ([string]$item.Name)
}
foreach($item in @(Get-ScheduledTask)){
    $counts.tasks++
    foreach($action in $item.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){
        if($action.PSObject.Properties[$field]){InspectReference ([string]$action.$field) 'scheduled-task' ([string]$item.TaskName)}
    }}
}
$shell=New-Object -ComObject WScript.Shell
try {
    foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
        if(-not[IO.Directory]::Exists($base)){continue}
        $pending=[Collections.Generic.Stack[string]]::new();$pending.Push($base)
        while($pending.Count){
            foreach($child in [IO.DirectoryInfo]::new($pending.Pop()).EnumerateFileSystemInfos()){
                if(($child.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne 0){$counts.skipped_links++;continue}
                if($child-is[IO.DirectoryInfo]){$pending.Push($child.FullName);continue}
                if($child.Extension-ine'.lnk'){continue}
                $counts.shortcuts++;$shortcut=$shell.CreateShortcut($child.FullName)
                InspectReference ([string]$shortcut.TargetPath) 'shortcut' $child.Name
                InspectReference ([string]$shortcut.Arguments) 'shortcut' $child.Name
                InspectReference ([string]$shortcut.WorkingDirectory) 'shortcut' $child.Name
            }
        }
    }
} finally {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
[pscustomobject]@{
    at=[DateTimeOffset]::Now.ToString('o');counts=$counts;matches=@($hits.ToArray())
    coverage='Readable process paths/command lines, services, scheduled actions, Desktop and Start Menu shortcuts. Relative paths, unreadable processes, global handles and shell current directories are not completely observable. Links are skipped.'
    source_writes=0;server_operations=0
}|ConvertTo-Json -Depth 6 -Compress
