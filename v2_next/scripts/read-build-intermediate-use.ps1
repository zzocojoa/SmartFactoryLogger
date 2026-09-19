# Read-only fixed development scope. Does not expose raw process command lines.
[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedIndexSha256)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt7-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Fixed development host / PowerShell 7 required'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$index=Join-Path $repo 'verification-files.local.json'
$boundary=Join-Path $repo 'backend\build'
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$document=$null
try {
    # Import only the native initializer and read-only filesystem functions, never transaction functions.
    foreach($definition in @(
        @{path='server-path-audit\cleanup-archive-core.ps1';names=@('Initialize-CleanupNative')},
        @{path='dist-migration-core.ps1';names=@('Get-DistHash','Assert-DistPlain','Add-DistGuard','Get-DistMetadata','Assert-DistMetadata','Get-DistTree')}
    )){
        $text=[IO.File]::ReadAllText((Join-Path $PSScriptRoot $definition.path))
        $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
        if($errors.Count){throw 'Invalid helper syntax'}
        foreach($name in $definition.names){
            $fn=@($ast.FindAll({param($node)$node-is[Management.Automation.Language.FunctionDefinitionAst]-and$node.Name-ceq$name},$false))
            if($fn.Count-ne1){throw 'Ambiguous read-only primitive'}
            . ([scriptblock]::Create($fn[0].Extent.Text))
        }
    }
    Initialize-CleanupNative
    Add-DistGuard $boundary $guards
    $indexStream=[SflCleanupNativeV1]::OpenFile($index,$false);$pins.Add($indexStream)
    if((Get-DistHash $indexStream)-cne$ExpectedIndexSha256){throw 'Management hash differs'}
    $indexStream.Position=0;$document=[System.Text.Json.JsonDocument]::Parse($indexStream)
    $reviews=@($document.RootElement.GetProperty('audits').EnumerateArray()|Where-Object {$_.GetProperty('id').GetString()-ceq'fd82da0e-aba2-4c9f-9ad4-c21b8f260c8e'})
    if($reviews.Count-ne1){throw 'Fixed preceding review missing'}
    $expected=@{}
    foreach($f in $reviews[0].GetProperty('files').EnumerateArray()){
        $p=$f.GetProperty('path').GetString()
        if($p.StartsWith($boundary+'\',[StringComparison]::Ordinal)){$expected[$p]=$f.GetRawText()|ConvertFrom-Json}
    }
    $tree=Get-DistTree $boundary
    if($expected.Count-ne31-or$tree.files.Count-ne31-or@($tree.files|Where-Object {-not$expected.ContainsKey($_)}).Count){throw 'Build tree membership differs'}
    $records=[Collections.Generic.List[object]]::new();$held=@{}
    foreach($directory in $tree.directories){Add-DistGuard $directory $guards;[SflCleanupNativeV1]::NoAlternateStreams($directory,$true)}
    foreach($p in $tree.files){
        Assert-DistPlain $p
        $s=[IO.File]::Open($p,'Open','Read','None');$pins.Add($s);$held[$p]=$s
        $identity=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$p,$false)
        [SflCleanupNativeV1]::NoAlternateStreams($p,$false)
        $metadata=[pscustomobject](Get-DistMetadata $p);$sha=Get-DistHash $s
        $prior=$expected[$p]
        if($s.Length-ne$prior.bytes-or($prior.PSObject.Properties['sha256']-and$sha-cne$prior.sha256)){throw 'Prior build record differs'}
        $records.Add(@{path=$p;sha256=$sha;identity=$identity;metadata=$metadata;exclusive_read_open=$true;alternate_streams=0})
    }
    $counts=@{processes=0;unreadable_process_command_lines=0;services=0;tasks=0;shortcuts=0;skipped_links=0}
    $hits=[Collections.Generic.List[object]]::new()
    function Inspect([string]$Value,[string]$Kind,[string]$Id){
        $n=$Value.Replace('/','\')
        if($n-match'(?i)(?:^|[\\\s"''])backend\\build(?:\\|[\s"'']|$)|build\\(?:SmartFactoryBackend|spot-temperature-v25-qa)(?:\\|[\s"'']|$)|pyinstaller|build_spot_temperature_v25_qa_bundle|scripts\\deploy\.ps1'){
            $hits.Add(@{kind=$Kind;id=$Id})
        }
    }
    foreach($p in @(Get-CimInstance Win32_Process)){
        if($p.ProcessId-eq$PID){continue};$counts.processes++
        if([string]::IsNullOrWhiteSpace($p.CommandLine)){$counts.unreadable_process_command_lines++}
        Inspect ([string]$p.CommandLine) 'process' ([string]$p.ProcessId);Inspect ([string]$p.ExecutablePath) 'process' ([string]$p.ProcessId)
    }
    foreach($s in @(Get-CimInstance Win32_Service)){$counts.services++;Inspect ([string]$s.PathName) 'service' $s.Name}
    foreach($t in @(Get-ScheduledTask)){
        $counts.tasks++
        foreach($a in $t.Actions){foreach($field in @('Execute','Arguments','WorkingDirectory')){if($a.PSObject.Properties[$field]){Inspect ([string]$a.$field) 'task' $t.TaskName}}}
    }
    $shell=New-Object -ComObject WScript.Shell
    try {
        foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'),[Environment]::GetFolderPath('StartMenu'),[Environment]::GetFolderPath('CommonStartMenu'))){
            if(-not[IO.Directory]::Exists($base)){continue}
            $stack=[Collections.Generic.Stack[string]]::new();$stack.Push($base)
            while($stack.Count){foreach($child in [IO.DirectoryInfo]::new($stack.Pop()).EnumerateFileSystemInfos()){
                if(($child.Attributes-band[IO.FileAttributes]::ReparsePoint)-ne0){$counts.skipped_links++;continue}
                if($child-is[IO.DirectoryInfo]){$stack.Push($child.FullName);continue}
                if($child.Extension-ine'.lnk'){continue}
                $counts.shortcuts++;$shortcut=$shell.CreateShortcut($child.FullName)
                try {Inspect $shortcut.TargetPath 'shortcut' $child.Name;Inspect $shortcut.Arguments 'shortcut' $child.Name;Inspect $shortcut.WorkingDirectory 'shortcut' $child.Name}
                finally {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shortcut)}
            }}
        }
    }finally{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)}
    foreach($r in $records){
        Assert-DistMetadata (Get-DistMetadata $r.path) $r.metadata
        if((Get-DistHash $held[$r.path])-cne$r.sha256){throw 'Pinned build file changed'}
    }
    $after=Get-DistTree $boundary
    if(@(Compare-Object $tree.files $after.files).Count-or@(Compare-Object $tree.directories $after.directories).Count){throw 'Membership changed during observation'}
    $directoryAcls=@($tree.directories|ForEach-Object {@{path=$_;sddl=(Get-Acl -LiteralPath $_).Sddl}})
    [ordered]@{at=[DateTimeOffset]::UtcNow.ToString('o');files=$records.ToArray();directories=$directoryAcls;counts=$counts;matches=$hits.ToArray();source_writes=0;deleted_files=0;server_operations=0;
        limitations='Readable process paths/commands, service/task actions and user/common Desktop/StartMenu shortcuts only. Unreadable system processes, relative shell working directories, other users and global mapped images are not fully observable. Exclusive read handles cover this observation interval only; rerun exact preflight immediately before any separately authorized deletion.'}|ConvertTo-Json -Depth 10 -Compress
} finally {
    if($null-ne$document){$document.Dispose()}
    foreach($p in $pins){$p.Dispose()}
    foreach($g in $guards.Values){$g.handle.Dispose()}
}
