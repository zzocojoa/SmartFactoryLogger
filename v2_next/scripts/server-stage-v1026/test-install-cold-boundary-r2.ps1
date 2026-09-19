param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5){throw 'Native Windows PowerShell 5.1 required'}
$output=[IO.Path]::GetFullPath($OutputRoot)
if([IO.File]::Exists($output)-or[IO.Directory]::Exists($output)){throw 'Existing fixture is preserved'}
$source=Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup-r2.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'r2 parse failed'}
foreach($f in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){
    . ([scriptblock]::Create($f.Extent.Text))
}
$enginePath=Join-Path $PSScriptRoot 'cold-backup-core.cs'
if((Get-FileHash -LiteralPath $enginePath -Algorithm SHA256).Hash -cne 'D2F56CE62ADA4155F68CC947A81669A1AE3A1DB200076F9DA6AE165E302A8E7D'){throw 'Legacy engine source drift'}
Add-Type -TypeDefinition ([IO.File]::ReadAllText($enginePath)) -Language CSharp
[void][IO.Directory]::CreateDirectory($output)
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$OK,[string]$Name)if(-not$OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Action,[string]$Name)$rejected=$false;try{&$Action|Out-Null}catch{$rejected=$true};Check $rejected $Name}
$realStopped=(Get-Command AssertStopped).ScriptBlock
# Never query the real application's state from a synthetic fixture.
function AssertStopped {if($script:running){throw 'TEST: app restarted'}}
$script:running=$false
$script:pins=[Collections.Generic.List[IDisposable]]::new()
# Host ACL policy is covered separately; only this synthetic fixture's ACL gate is mocked.
function AssertPrivateAcl {param([string]$Path)}
$stateSpecs=[ordered]@{
    'config.ini'=$true;'config.bak'=$true;'config.pending.json'=$false
    'config_meta.json'=$true;'config_cache.json'=$false;'layout.json'=$true
    'layout.backup.json'=$true;'operator_metadata.json'=$true
    'operator_metadata_runtime_state.json'=$true;'state.json'=$true
}

function NewFixture {
    param([string]$Name)
    foreach($pin in $script:pins){$pin.Dispose()};$script:pins.Clear()
    $root=Join-Path $output $Name
    $script:backupWorkRoot=$root+'\work';$script:dataRoot=$root+'\data'
    $script:profileRoot=$root+'\profile';$script:layoutsRoot=$dataRoot+'\layouts'
    $state=$backupWorkRoot+'\state-source'
    foreach($p in @($state,$dataRoot,$profileRoot,$layoutsRoot)){[void][IO.Directory]::CreateDirectory($p)}
    [IO.File]::WriteAllText(($profileRoot+'\sample.bin'),'abc')
    [IO.File]::WriteAllText(($layoutsRoot+'\sample.bin'),'abc')
    $rows=@(foreach($entry in $stateSpecs.GetEnumerator()){
        if(-not$entry.Value){continue}
        $s=$dataRoot+'\'+$entry.Key;$d=$state+'\'+$entry.Key
        [IO.File]::WriteAllText($s,'abc');[IO.File]::Copy($s,$d,$false)
        $fact=ReadOriginalStateFact $s
        [pscustomobject]@{name=$entry.Key;source=$s;staged=$d;bytes=$fact.bytes;sha256=$fact.sha256
            creation_utc_ticks=$fact.creation_utc_ticks;last_write_utc_ticks=$fact.last_write_utc_ticks
            attributes=$fact.attributes;source_sddl=$fact.source_sddl}
    })
    $map=[ordered]@{schema_version='v1025-minimal-state-map-v1';files=$rows;original_files_overwritten=$false;original_files_deleted=$false}
    [IO.File]::WriteAllText(($backupWorkRoot+'\state-map.json'),($map|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    $guard=[Action]{AssertStopped};$progress=[Action[string,long,long,long]]{param($n,$b,$f,$e)}
    $engine=[SflColdBackupV1.Engine]::new([string[]]@($profileRoot,$layoutsRoot,$state),$guard,$progress)
    $manifest=$backupWorkRoot+'\files.manifest.tsv'
    $made=$engine.Backup(($backupWorkRoot+'\backup'),$manifest)
    $script:backupManifestHash=$made.ManifestSha256
    $null=$engine.Verify($manifest,$backupManifestHash,($backupWorkRoot+'\backup'),($backupWorkRoot+'\restore'),$true)
    [IO.File]::WriteAllText(($backupWorkRoot+'\intent.json'),'{}')
    $receipt=[ordered]@{
        schema_version='v1025-minimal-cold-backup-result-v1'
        result='V1025_MINIMAL_COLD_BACKUP_AND_FILE_RESTORE_VERIFIED'
        product_version='1.0.25';product_commit='a203baf62b544d38072a32d71ef411c7cf8b6490'
        manifest_sha256=$backupManifestHash;backup_root=$backupWorkRoot+'\backup'
        restore_rehearsal_root=$backupWorkRoot+'\restore'
        source_file_count=$made.Files;source_directory_count=$made.Directories;source_bytes=$made.Bytes
        app_still_stopped=$true;backup_readback_verified=$true;restored_file_hashes_verified=$true
        source_hashes_rechecked=$true;exact_membership_verified=$true;original_state_hashes_rechecked=$true
        installation_started=$false;automatic_restart_performed=$false;installed_program_directory_backed_up=$false
    }
    foreach($pair in @(@('intent.json','intent_sha256'),@('state-map.json','state_map_sha256'))){
        $path=$backupWorkRoot+'\'+$pair[0];$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $receipt[$pair[1]]=$hash
        [IO.File]::WriteAllText(($path+'.sha256.txt'),($hash+"`n"),[Text.Encoding]::ASCII)
    }
    $script:backupResult=$backupWorkRoot+'\result.json'
    [IO.File]::WriteAllText($backupResult,($receipt|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
    $script:backupResultHash=(Get-FileHash -LiteralPath $backupResult -Algorithm SHA256).Hash
    [IO.File]::WriteAllText(($backupResult+'.sha256.txt'),($backupResultHash+"`n"),[Text.Encoding]::ASCII)
}
function Evidence {
    # File content + creation/write metadata + exact membership; reads only this fixture.
    return (@(Get-ChildItem -LiteralPath $backupWorkRoot -Recurse -Force|Sort-Object FullName|ForEach-Object{
        $hash=if($_.PSIsContainer){'-'}else{(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}
        '{0}|{1}|{2}|{3}|{4}' -f $_.FullName,$_.CreationTimeUtc.Ticks,$_.LastWriteTimeUtc.Ticks,[int]$_.Attributes,$hash
    }) -join "`n")
}

NewFixture 'valid';$before=Evidence
$null=AssertBackup
Check ((Evidence) -ceq $before) 'valid cold check writes nothing and creates no restore'
$stateFile=$dataRoot+'\config.ini'
$exclusive=[IO.File]::Open($stateFile,'Open','ReadWrite','None');$exclusive.Dispose()
Check $true 'original state handles released before launch'

foreach($leaf in @('backup','restore')){
    foreach($fault in @('missing','tamper','extra')){
        NewFixture ($leaf+'-'+$fault);$target=$backupWorkRoot+'\'+$leaf+'\r0\sample.bin'
        # These targets were just created by NewFixture, never a managed/server tree.
        switch($fault){
            'missing'{[IO.File]::Delete($target)}
            'tamper'{[IO.File]::WriteAllText($target,'xyz')}
            'extra'{[IO.File]::WriteAllText(($backupWorkRoot+'\'+$leaf+'\extra.bin'),'x')}
        }
        Reject {AssertBackup} ($leaf+' '+$fault+' blocks installation through actual receipt gate')
    }
}
foreach($fault in @('profile','layouts','staged','original-state','metadata','absent-file','absent-directory')){
    NewFixture $fault
    switch($fault){
        'profile'{[IO.File]::WriteAllText(($profileRoot+'\sample.bin'),'xyz')}
        'layouts'{[IO.File]::WriteAllText(($layoutsRoot+'\extra.bin'),'x')}
        'staged'{[IO.File]::WriteAllText(($backupWorkRoot+'\state-source\config.ini'),'xyz')}
        'original-state'{[IO.File]::WriteAllText(($dataRoot+'\config.ini'),'xyz')}
        'metadata'{[IO.File]::SetLastWriteTimeUtc(($dataRoot+'\config.ini'),[DateTime]::UtcNow.AddHours(-1))}
        'absent-file'{[IO.File]::WriteAllText(($dataRoot+'\config.pending.json'),'x')}
        'absent-directory'{[void][IO.Directory]::CreateDirectory($dataRoot+'\config_cache.json')}
    }
    Reject {AssertBackup} ($fault+' drift rejected through actual receipt gate')
}
foreach($pin in $script:pins){$pin.Dispose()};$script:pins.Clear()

$script:launches=0;$script:order=[Collections.Generic.List[string]]::new()
InvokeColdCheckedLaunch {$script:order.Add('cold')} {$script:order.Add('stopped')} {$script:order.Add('launch');$script:launches++}
Check ($launches-eq1-and($order -join ',')-ceq'cold,stopped,launch') 'cold and stopped gates immediately precede one launch'
$script:launches=0
Reject {InvokeColdCheckedLaunch {throw 'TEST: source changed during approval'} {} {$script:launches++}} 'source drift after approval blocks launch'
Check ($launches-eq0) 'source failure launch count zero'
$script:running=$true
Reject {InvokeColdCheckedLaunch {} {AssertStopped} {$script:launches++}} 'app restarted during approval blocks launch'
Check ($launches-eq0) 'restart failure launch count zero'
$script:running=$false

# Execute the actual r2 stopped check against query mocks; provider failures are not absence.
function Get-Process {param($ErrorAction) throw 'TEST: process query failed'}
function Get-NetTCPConnection {param($ErrorAction) @()}
Reject {&$realStopped} 'process provider failure stops preflight'
function Get-Process {param($ErrorAction) @()}
function Get-NetTCPConnection {param($ErrorAction) throw 'TEST: listener query failed'}
Reject {&$realStopped} 'listener provider failure stops preflight'
function Get-NetTCPConnection {param($ErrorAction) @()}
&$realStopped
Check $true 'empty successful queries mean stopped'
function Get-Process {param($ErrorAction) [pscustomobject]@{ProcessName='SmartFactoryBackend'}}
Reject {&$realStopped} 'running backend rejected'

$text=[IO.File]::ReadAllText($source)
Check ($text.Contains("Need(`$answer-ceq'INSTALL V1.0.26')'operator-not-approved'`n    AssertStopped")) 'main rechecks immediately after approval'
Check ($text.Contains('InvokeColdCheckedLaunch { $null=AssertBackup } { AssertStopped } { $shell.ShellExecute(')) 'actual COM launch bound to fresh full checks'
Check ((Get-Command AssertBackup).ScriptBlock.ToString().Contains('AssertColdBackupContents $result')) 'receipt check invokes the content verifier'
Check ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup.ps1') -Algorithm SHA256).Hash -ceq '7943B476C75BF5FC1B8F1CB9D83C6018E787F4ACCEA17D42BF0C6C670FF42C53') 'historical helper bytes preserved'
# Import builder gates only, never its packaging main. No external DLL required.
$builder=Join-Path $PSScriptRoot 'build-install-v1026-transfer-r2.ps1'
$builderAst=[Management.Automation.Language.Parser]::ParseFile($builder,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'builder parse failed'}
foreach($name in @('HashFile','ReadPinnedValidation','AssertCopiedHelper')){
    $fn=$builderAst.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq$name},$true)
    . ([scriptblock]::Create($fn.Extent.Text))
}
$receiptPath=$output+'\synthetic-receipt.json'
[IO.File]::WriteAllText($receiptPath,'{"fixture":true}')
$receiptHash=HashFile $receiptPath
$read=ReadPinnedValidation $receiptPath $receiptHash
Check ($read.fixture-eq$true) 'builder reads exactly hash-verified receipt bytes'
Reject {[IO.File]::WriteAllText($receiptPath,'{"fixture":false}')} 'receipt pin prevents overwrite during packaging'
Reject {ReadPinnedValidation $receiptPath ('0'*64)} 'wrong receipt hash rejected'
$copied=$output+'\synthetic-helper.ps1'
[IO.File]::WriteAllText($copied,'# synthetic helper')
$copiedHash=HashFile $copied
Check ((AssertCopiedHelper $copied $copiedHash)-ceq$copiedHash) 'copied helper bound to tested hash'
[IO.File]::WriteAllText($copied,'# untested replacement')
Reject {AssertCopiedHelper $copied $copiedHash} 'helper copy changed after validation rejected'
$builderText=[IO.File]::ReadAllText($builder)
Check ($builderText.Contains('AssertCopiedHelper $helperTarget $review.helper_sha256')-and$builderText.Contains('$facts[0].sha256-cne$review.helper_sha256')) 'ZIP helper fact stays bound to validation receipt'
foreach($pin in $script:pins){$pin.Dispose()};$script:pins.Clear()
$result=[pscustomobject]@{result='V1026_INSTALL_R2_COLD_BOUNDARY_TEST_PASS';assertions=$checks.Count;helper_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash;engine_source_sha256=(Get-FileHash -LiteralPath $enginePath -Algorithm SHA256).Hash;server_main_executed=$false;installer_started=$false;network_queries=$false;fixture=$output}
$json=$result|ConvertTo-Json
[IO.File]::WriteAllText(($output+'\validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
