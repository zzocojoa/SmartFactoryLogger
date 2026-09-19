param(
    [Parameter(Mandatory=$true)][string]$EngineAssembly,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'minimal-cold-backup-v1025.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count-ne 0){throw($errors|Out-String)}
$checks=[Collections.Generic.List[string]]::new()
function Check{param([bool]$OK,[string]$Name)if(-not$OK){throw('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject{param([scriptblock]$Code,[string]$Name)$failed=$false;try{&$Code|Out-Null}catch{$failed=$true};Check $failed $Name}
$functions=@($ast.FindAll({param($node)$node-is[Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($function in $functions){.([scriptblock]::Create($function.Extent.Text))}
$text=[IO.File]::ReadAllText($source)
Check($functions.Count-eq 21)'parse/import functions only; server main not executed'
Check($text.Contains("param([switch]`$Execute)")-and$text.Contains("if (-not `$Execute)"))'execution requires explicit switch'
Check($text.Contains("Type BACKUP MINIMAL V1.0.25"))'separate operator token'
Check($text.Contains("`$opsRoot = 'C:\ProgramData\SFLOps'"))'SFLOps root pinned'
Check($text.Contains("`$backupParent = `$opsRoot + '\backups'"))'backup policy child pinned'
Check(-not$text.Contains('C:\ProgramData\SFL26B-'))'legacy backup root absent'
Check($text.Contains('CSV, images, fact/diagnostic logs, snapshots and installed program directory are NOT backed up'))'minimal exclusions explicit'
Check($text.Contains('APP REMAINS STOPPED')-and$text.Contains('automatic_restart_performed=$false'))'no automatic restart claim'
Check($text-notmatch'(?im)^\s*(Stop-Process|Start-Process|Remove-Item|Move-Item|Copy-Item|Clear-Content|Set-Content|Invoke-Expression)\b')'no destructive/process command'
Check($text.Contains('$mainId = 13432')-and$text.Contains('$backendId = 15240'))'preflight process IDs pinned'
Check($text.Contains('$mainTicks = [long]639249359473432800')-and
    $text.Contains('$backendTicks = [long]639249359490446273'))'preflight process start ticks pinned'
Check($text.Contains("'config.pending.json' = `$false")-and$text.Contains("'config_cache.json' = `$false"))'preflight missing-state contract pinned'
Check($text.Contains("Need (`$rows.Count -eq 8) 'state-copy-count'"))'exact existing state count pinned'

$enginePath=[IO.Path]::GetFullPath($EngineAssembly)
$engineBytes=[IO.File]::ReadAllBytes($enginePath)
$engineStream=[IO.MemoryStream]::new($engineBytes)
try{$engineActual=HashStream $engineStream}finally{$engineStream.Dispose()}
Check($engineActual-ceq'3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71')'exact validated engine binary'
[void][Reflection.Assembly]::Load($engineBytes)

if([IO.File]::Exists($OutputRoot)-or[IO.Directory]::Exists($OutputRoot)){throw'Existing fixture output is preserved.'}
$fixture=[IO.Path]::GetFullPath($OutputRoot)
[void][IO.Directory]::CreateDirectory($fixture)
$profile=Join-Path $fixture 'profile';$layouts=Join-Path $fixture 'layouts';$appData=Join-Path $fixture 'appdata'
foreach($directory in @($profile,$layouts,$appData)){[void][IO.Directory]::CreateDirectory($directory)}
[IO.File]::WriteAllText((Join-Path $profile 'Preferences'),'profile')
[void][IO.Directory]::CreateDirectory((Join-Path $profile 'Local Storage'))
[IO.File]::WriteAllText((Join-Path $profile 'Local Storage\state'),'leveldb')
[IO.File]::WriteAllText((Join-Path $layouts 'layout-a.json'),'layout')

$dataRoot=$appData
$stateSpecs=[ordered]@{
    'config.ini'=$true;'config.bak'=$true;'config.pending.json'=$false;'config_meta.json'=$true;
    'config_cache.json'=$false;'layout.json'=$true;'layout.backup.json'=$true;
    'operator_metadata.json'=$true;'operator_metadata_runtime_state.json'=$true;'state.json'=$true
}
foreach($entry in $stateSpecs.GetEnumerator()){if([bool]$entry.Value){[IO.File]::WriteAllText((Join-Path $appData $entry.Key),('fixture-'+$entry.Key))}}
$stateRowsBefore=CheckStatePresence
Check($stateRowsBefore.Count-eq 8)'fixture state presence contract'
$stateSource=Join-Path $fixture 'state-source';$stateRows=CopyStateFiles $stateSource
Check($stateRows.Count-eq 8)'state copies and hashes'
RecheckOriginalStates $stateRows;Check $true 'original state rehash'
$first=$stateRows[0];[IO.File]::AppendAllText($first.source,'tamper')
Reject{RecheckOriginalStates $stateRows}'original state drift rejected'
[IO.File]::WriteAllText($first.source,('fixture-'+$first.name))

$guardCount=0;$guard=[Action]{$script:guardCount++};$progress=[Action[string,long,long,long]]{param($name,$done,$count,$millis)}
$engine=[SflColdBackupV1.Engine]::new([string[]]@($profile,$layouts,$stateSource),$guard,$progress)
$backupRoot=Join-Path $fixture 'backup';$restoreRoot=Join-Path $fixture 'restore';$manifest=Join-Path $fixture 'files.manifest.tsv'
$inventory=$engine.Inventory($restoreRoot)
$backup=$engine.Backup($backupRoot,$manifest)
Check($backup.Files-eq$inventory.Files-and$backup.Directories-eq$inventory.Directories-and$backup.Bytes-eq$inventory.Bytes)'inventory/backup totals'
$restored=$engine.Verify($manifest,$backup.ManifestSha256,$backupRoot,$restoreRoot,$true)
$verified=$engine.Verify($manifest,$backup.ManifestSha256,$restoreRoot,$null,$false)
Check($restored.Files-eq$backup.Files-and$verified.Files-eq$backup.Files-and$guardCount-gt 0)'backup restore and source recheck'
[IO.File]::AppendAllText((Join-Path $restoreRoot 'r0\Preferences'),'tamper')
Reject{$engine.Verify($manifest,$backup.ManifestSha256,$restoreRoot,$null,$false)}'restored tamper rejected'

$acl=NewPrivateAcl
$rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
Check($acl.AreAccessRulesProtected-and$rules.Count-eq 2)'private ACL has two protected rules'
Check(@($rules|Where-Object{$_.IdentityReference.Value-cin@('S-1-5-32-544','S-1-5-18')}).Count-eq 2)'private ACL trustees'

$result=[pscustomobject]@{result='V1025_MINIMAL_COLD_BACKUP_LOCAL_TEST_PASS';assertions=$checks.Count;
    powershell_version=$PSVersionTable.PSVersion.ToString();helper_sha256=$null;engine_sha256=$engineActual;
    end_to_end_files=$backup.Files;end_to_end_bytes=$backup.Bytes;server_main_executed=$false;network_queries_performed=$false;
    application_stopped=$false;product_changes_made=$false;checks=$checks.ToArray()}
$sha=[Security.Cryptography.SHA256]::Create()
try{$result.helper_sha256=[BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($source))).Replace('-','')}
finally{$sha.Dispose()}
$json=$result|ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $fixture 'validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
