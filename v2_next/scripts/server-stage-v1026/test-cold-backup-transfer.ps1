param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
$checks=[Collections.Generic.List[string]]::new()
function Test {param([bool]$OK,[string]$Name) if(-not $OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $bad=$false;try{& $Code|Out-Null}catch{$bad=$true};Test $bad $Name}
$output=[IO.Path]::GetFullPath($OutputRoot)
Test (-not [IO.File]::Exists($output) -and -not [IO.Directory]::Exists($output)) 'new test root'
[void][IO.Directory]::CreateDirectory($output)
$launcher=Join-Path $PSScriptRoot 'launch-cold-backup.ps1';$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($launcher,[ref]$tokens,[ref]$errors)
Test ($errors.Count -eq 0) 'launcher parses in PS51'
foreach($f in @($ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true))){. ([scriptblock]::Create($f.Extent.Text))}
$artifact=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\artifacts\v1026-cold-backup-ready-20260912-r2'))
$zipPath=$artifact+'\v1025-cold-backup-restore-ready.zip'
$s=[IO.File]::Open($zipPath,'Open','Read','Read');$pins=[Collections.Generic.List[IDisposable]]::new()
try{
    Test ((LaunchHash $s) -ceq 'FAA801888AB58FED5D08C55CCB5DF616DAF28D29A753F594B83A2F88457801EF' -and $s.Length -eq 22383) 'exact external ZIP pin'
    $s.Position=0;$zip=[IO.Compression.ZipArchive]::new($s,'Read',$true)
    try{
        ExtractNew $zip ($output+'\extracted') $pins
        Test ($pins.Count -eq 5) 'all five reopened payloads pinned'
        Reject {ExtractNew $zip ($output+'\extracted') $pins} 'existing extraction never overwritten'
    }finally{$zip.Dispose()}
}finally{foreach($p in $pins){$p.Dispose()};$s.Dispose()}
$dllHash=$null;$s=[IO.File]::Open(($output+'\extracted\cold-backup-core.dll'),'Open','Read','Read')
try{$dllHash=LaunchHash $s}finally{$s.Dispose()}
Test ($dllHash -ceq '3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71') 'extracted DLL is tested binary'
# Default helper path returns before function declarations, host queries, assembly load or writes.
$defaultOutput=& ($output+'\extracted\backup-restore-v1025.ps1') 6>&1 | Out-String
Test ($defaultOutput.Contains('[PREPARED ONLY]')) 'extracted helper default does not enter server main'

function MutatedZip {
    param([string]$Mode)
    $memory=[IO.MemoryStream]::new();$z=[IO.Compression.ZipArchive]::new($memory,'Create',$true)
    try{
        $names=@('backup-restore-v1025.ps1','backup-restore-v1025.ps1.sha256.txt','cold-backup-core.dll','cold-backup-core.dll.sha256.txt','COLD_BACKUP_GUIDE.md')
        for($i=0;$i -lt $names.Count;$i++){
            $name=$names[$i];$b=[IO.File]::ReadAllBytes($output+'\extracted\'+$name)
            if($i -eq 0){
                if($Mode -ceq 'traversal'){$name='../escape.ps1'}
                if($Mode -ceq 'case'){$name='BACKUP-RESTORE-v1025.ps1'}
                if($Mode -ceq 'duplicate'){$name=$names[1];$b=[IO.File]::ReadAllBytes($output+'\extracted\'+$name)}
                if($Mode -ceq 'content'){$b[0]=$b[0] -bxor 1}
                if($Mode -ceq 'size'){$b=$b[0..10]}
            }
            $e=$z.CreateEntry($name)
            if($Mode -ceq 'symlink' -and $i -eq 0){$e.ExternalAttributes=0x400}
            $s=$e.Open();try{$s.Write($b,0,$b.Length)}finally{$s.Dispose()}
        }
    }finally{$z.Dispose()}
    $memory.Position=0;return ,$memory
}
foreach($mode in @('traversal','case','duplicate','content','size','symlink')){
    $m=MutatedZip $mode;$z=[IO.Compression.ZipArchive]::new($m,'Read',$true);$pins=[Collections.Generic.List[IDisposable]]::new()
    try{Reject {ExtractNew $z ($output+'\'+$mode) $pins} ('reject altered archive '+$mode)
        Test (-not [IO.Directory]::Exists($output+'\'+$mode)) ('validate all payloads before any extraction '+$mode)
    }finally{$z.Dispose();$m.Dispose();foreach($p in $pins){$p.Dispose()}}
}
$r=[ordered]@{result='COLD_BACKUP_TRANSFER_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();
    powershell=$PSVersionTable.PSVersion.ToString();zip_sha256='FAA801888AB58FED5D08C55CCB5DF616DAF28D29A753F594B83A2F88457801EF';
    server_main_executed=$false;extracted_default_gate_tested=$true;server_shutdown_performed=$false}
[IO.File]::WriteAllText($output+'\validation-result.json',($r|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
[pscustomobject]$r|Select-Object result,assertions,server_main_executed|Format-List
