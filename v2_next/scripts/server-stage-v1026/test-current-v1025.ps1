param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'read-current-v1025.ps1'
if ([IO.Directory]::Exists($OutputRoot) -or [IO.File]::Exists($OutputRoot)) { throw 'Existing fixture output is preserved.' }
$null=[IO.Directory]::CreateDirectory($OutputRoot)
$stageRoot = 'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503'
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw ($parseErrors | Out-String) }
$tests = [Collections.Generic.List[string]]::new()
function Check { param([bool]$Ok,[string]$Name) if (-not $Ok) {throw "TEST FAILED: $Name"}; $tests.Add($Name) }
function Reject { param([scriptblock]$Code,[string]$Name) $failed=$false;try {& $Code | Out-Null} catch {$failed=$true};Check $failed $Name }
$functions = $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)
foreach ($f in $functions) { . ([scriptblock]::Create($f.Extent.Text)) }
Check ($functions.Count -eq 19) 'native parser and expected function-only fixture import'
$readPins = [Collections.Generic.List[IDisposable]]::new()
$readClock = [Diagnostics.Stopwatch]::StartNew()
$commit='a203baf62b544d38072a32d71ef411c7cf8b6490'
$sourceText=[IO.File]::ReadAllText($source)
$commands=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true) | ForEach-Object {$_.GetCommandName()} | Sort-Object -Unique)
$allowed=@($functions.Name)+@('Set-StrictMode','Get-Process','Get-NetTCPConnection','Select-Object','Get-CimInstance','Where-Object','Get-ChildItem','Write-Host','Start-Sleep','ConvertFrom-Json','ConvertTo-Json','New-Object')
foreach ($c in $commands) {Check ($null -eq $c -or $c -in $allowed) ('read-only command allowlist: '+$c)}
Check (-not ($sourceText -match 'WriteAll|WriteAllBytes|CreateNew|FileMode\]::Create|Start-Process|Stop-Process|Remove-Item|Set-Content|Out-File')) 'no server file writer or process mutation'
Check ($sourceText.Contains("`$request.Method = 'GET'; `$request.Proxy = `$null; `$request.AllowAutoRedirect = `$false")) 'GET only, no proxy or redirects'
Reject {LocalGet 'api/spot/image'} 'image endpoint rejected before network'
Reject {LocalGet 'http://other-host/health'} 'external endpoint rejected before network'
foreach ($textValue in @('[]','[{}]','[{"v":1}]','[{"v":1},{"v":2}]','null','1','true','"scalar"','', '  ')) {
    Reject {DecodeJsonObject $textValue} ('root JSON array/scalar rejected before enumeration: '+$textValue)
}
Check ((Required (DecodeJsonObject '  {"v":42}') 'v') -eq 42) 'single JSON object accepted with leading whitespace'
Check ($sourceText.Contains('return DecodeJsonObject ([Text.UTF8Encoding]') -and $sourceText.Contains('return DecodeJsonObject $reader.ReadToEnd()')) 'HTTP and pinned JSON file use strict root decoder'
Reject {Required ([pscustomobject]@{}) 'missing'} 'missing field rejected'
foreach ($invalid in @($null,-1,'0',0.5,$true)) {
    Reject {CountValue ([pscustomobject]@{v=$invalid}) 'v'} ('invalid counter rejected: '+[string]$invalid)
}
Check ((CountValue ([pscustomobject]@{v=[long]42}) 'v') -eq 42) 'valid integer accepted'
function Fixture {
    $v=[ordered]@{clock_seconds=0.0;runtime=[pscustomobject]@{main_pid=1;main_start_ticks=10;backend_pid=2;backend_start_ticks=20};image_status='ok';image_source='upstream';last_success_at=1000.0;source_port_enforcement_supported=$true;source_port_enforcement_active=$true;capture_enabled=$true;source_port_policy_version='spot-source-port-quarantine-v3';source_port_minimum_reuse_interval_seconds=77.0;source_port_minimum_required_reuse_interval_seconds=75.0;error_queue_size=0;error_repeat_total=0;error_last_at=$null}
    $v.storage_settings=[pscustomobject]@{restart_required=$false;logpath='logs/data';snapshotpath='snapshots';image_capture_path='spot_images'}
    foreach ($n in @(FailureNames)+@('capture_dropped_count','capture_failure_count','http_5xx_count','source_port_bind_collision_count')) {$v[$n]=0}
    foreach ($n in @('image_downstream_request_count','image_upstream_request_count','image_refresh_success_count','source_port_transport_started_count','source_port_transport_success_count','capture_enqueued_count','capture_written_count','capture_fact_row_count')) {$v[$n]=100}
    return [pscustomobject]$v
}
function GoodPair {
    $b=Fixture; $a=Fixture; $a.clock_seconds=30.1;$a.last_success_at=1030.0
    foreach ($n in @('image_downstream_request_count','image_upstream_request_count','image_refresh_success_count','source_port_transport_started_count','source_port_transport_success_count','capture_enqueued_count','capture_written_count','capture_fact_row_count')) {$a.$n=110}
    return @($b,$a)
}
$pair=GoodPair;$r=CompareSnapshots $pair[0] $pair[1]
Check ($r.sample_result -ceq 'CURRENT_SAMPLE_OK_NOT_OPERATIONAL_APPROVAL' -and $r.holds.Count -eq 0) 'healthy short sample never operational approval'
$jsonTimestampBefore=ConvertFrom-Json -InputObject '{"last_success_at":1788911472.1738272}'
$jsonTimestampAfter=ConvertFrom-Json -InputObject '{"last_success_at":1788911493.982117}'
Check ($jsonTimestampBefore.last_success_at -is [decimal] -and $jsonTimestampAfter.last_success_at -is [decimal]) 'PS5.1 real JSON timestamp materializes as Decimal'
$p=GoodPair;$p[0].last_success_at=$jsonTimestampBefore.last_success_at;$p[1].last_success_at=$jsonTimestampAfter.last_success_at
$decimalResult=CompareSnapshots $p[0] $p[1]
Check ($decimalResult.sample_result -ceq 'CURRENT_SAMPLE_OK_NOT_OPERATIONAL_APPROVAL') 'regression: valid JSON Decimal timestamps accepted'
$jsonBefore=ConvertFrom-Json -InputObject ((Fixture)|ConvertTo-Json -Depth 6)
$jsonAfter=ConvertFrom-Json -InputObject ((GoodPair)[1]|ConvertTo-Json -Depth 6)
Check ((CompareSnapshots $jsonBefore $jsonAfter).sample_result -ceq 'CURRENT_SAMPLE_OK_NOT_OPERATIONAL_APPROVAL') 'full JSON-decoded snapshots accepted'
foreach ($literal in @('null','"1788911472.1738272"','true','{}','[]','[1788911472.0]', '0','-1')) {
    $obj=ConvertFrom-Json -InputObject ('{"last_success_at":'+$literal+'}')
    $p=GoodPair;$p[1].last_success_at=$obj.last_success_at
    Reject {CompareSnapshots $p[0] $p[1]} ('invalid timestamp JSON rejected: '+$literal)
}
foreach ($badNumber in @([double]::NaN,[double]::PositiveInfinity,[double]::NegativeInfinity)) {
    $p=GoodPair;$p[1].last_success_at=$badNumber
    Reject {CompareSnapshots $p[0] $p[1]} ('nonfinite timestamp rejected: '+[string]$badNumber)
}
$p=GoodPair;$p[0].last_success_at=$jsonTimestampBefore.last_success_at;$p[1].last_success_at=$jsonTimestampBefore.last_success_at
Check ((CompareSnapshots $p[0] $p[1]).holds -contains 'last-success-not-advancing') 'Decimal timestamp that does not advance held'
foreach ($n in @(FailureNames)+@('capture_dropped_count','capture_failure_count','http_5xx_count')) {
    $p=GoodPair;$p[1].$n=1;$r=CompareSnapshots $p[0] $p[1]
    Check ($r.holds -contains ('new-failure:'+$n)) ('new failure held: '+$n)
}
foreach ($n in @('source_port_enforcement_active','source_port_enforcement_supported','capture_enabled')) {
    $p=GoodPair;$p[1].$n=$false;$r=CompareSnapshots $p[0] $p[1]
    Check ($r.holds -contains ('inactive:'+$n)) ('disabled state held: '+$n)
}
foreach ($case in @(
    @('image_status','error','image-not-ok-upstream'),
    @('image_source','cache','image-not-ok-upstream'),
    @('source_port_policy_version','wrong','unexpected-port-policy'),
    @('source_port_minimum_reuse_interval_seconds',74.9,'reuse-interval-below-policy'),
    @('error_queue_size',1,'app-error-queue-needs-review'),
    @('error_repeat_total',1,'app-error-summary-changed'),
    @('last_success_at',1000.0,'last-success-not-advancing'),
    @('image_refresh_success_count',100,'no-progress:image_refresh_success_count')
)) {$p=GoodPair;$p[1].($case[0])=$case[1];$r=CompareSnapshots $p[0] $p[1];Check ($r.holds -contains $case[2]) ('state held: '+$case[0])}
$p=GoodPair;$p[1].runtime.backend_pid=3;Reject {CompareSnapshots $p[0] $p[1]} 'runtime change rejected'
$p=GoodPair;$p[1].image_refresh_success_count=99;Reject {CompareSnapshots $p[0] $p[1]} 'counter decrease rejected'
$p=GoodPair;$p[0].error_repeat_total=1;Reject {CompareSnapshots $p[0] $p[1]} 'error counter clearing rejected'
$p=GoodPair;$p[1].clock_seconds=29.9;Reject {CompareSnapshots $p[0] $p[1]} 'short interval rejected'
$p=GoodPair;$p[1].source_port_minimum_reuse_interval_seconds=[double]::NaN;Reject {CompareSnapshots $p[0] $p[1]} 'NaN reuse value rejected'
$p=GoodPair;$p[0].source_port_reuse_violation_count=1;$p[1].source_port_reuse_violation_count=1;$r=CompareSnapshots $p[0] $p[1]
Check ($r.historical_failure_counters_nonzero -contains 'source_port_reuse_violation_count') 'stable historical failures are explicitly retained'

$fixtureRoot=Join-Path $OutputRoot ('fixture-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($fixtureRoot)
[IO.File]::WriteAllBytes((Join-Path $fixtureRoot 'z.bin'),[byte[]]@(1,2,3))
[IO.File]::WriteAllBytes((Join-Path $fixtureRoot 'A.bin'),[byte[]]@(4,5))
try {
    $pinsBeforeInventory=$readPins.Count
    Reject {TreeFacts $fixtureRoot -ExpectedFileCount 3} 'unexpected file inventory rejected before payload locks'
    Check ($readPins.Count -eq $pinsBeforeInventory) 'file-count rejection takes no payload locks'
    Reject {TreeFacts $fixtureRoot -ExpectedFileCount 2 -ExpectedTotalBytes 999} 'unexpected byte inventory rejected before payload locks'
    Check ($readPins.Count -eq $pinsBeforeInventory) 'byte-count rejection takes no payload locks'
    $facts=TreeFacts $fixtureRoot
    $referenceRecords=@(Get-ChildItem -LiteralPath $fixtureRoot -File | ForEach-Object {
        $sha=[Security.Cryptography.SHA256]::Create()
        try {$h=[BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($_.FullName))).Replace('-','')}finally{$sha.Dispose()}
        $_.Name+[char]0+$_.Length+[char]0+$h+"`n"
    })
    [Array]::Sort($referenceRecords,[StringComparer]::Ordinal)
    $sha=[Security.Cryptography.SHA256]::Create()
    try {$h=[BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($referenceRecords)))).Replace('-','')}finally{$sha.Dispose()}
    Check ($facts.file_count -eq 2 -and $facts.total_bytes -eq 5 -and $facts.tree_sha256 -ceq $h) 'canonical tree matches independent byte calculation'
    Reject {InstalledTree $fixtureRoot} 'unapproved small payload tree rejected'
    Reject {$w=[IO.File]::Open((Join-Path $fixtureRoot 'z.bin'),'Open','Write','ReadWrite');$w.Dispose()} 'verified source read lock rejects concurrent writer'
    Reject {FileFacts (Join-Path $fixtureRoot 'z.bin') ('0'*64)} 'file hash mismatch rejected'
} finally {foreach ($pin in $readPins){$pin.Dispose()}}

# Guard the published no-mutation envelope and prevent regression to config read locks.
Check (-not $sourceText.Contains('FileFacts $configFile')) 'mutable config never retained in immutable read locks'
Check ($sourceText.Contains("[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete")) 'mutable config permits write and replacement'
Check ($sourceText.Contains("$stageRoot") -and $sourceText.Contains('F4B2FA04536CCC8B3CF095E2D643E7CB6BE0766CF3BB98D5F7FAF301C5AA5C86')) 'server staging receipt pinned outside server inputs'
Check (-not $sourceText.Contains('rollback-v1.0.24')) 'does not use v1.0.24 as current recovery candidate'
Check (-not $sourceText.Contains('SIGNED_RELEASE_REQUIRED_FOR_COMMERCIAL_USE')) 'does not incorrectly reapply obsolete development signing gate'
foreach ($field in @('installation_ready','installation_authorized','installation_started','data_backup_performed','data_restore_tested','production_promotion_allowed')) {
    Check ($sourceText.Contains($field+'=$false')) ('no false approval: '+$field)
}
$p=GoodPair; $p[1].runtime.backend_start_ticks=21
Reject {CompareSnapshots $p[0] $p[1]} 'PID reuse is rejected by process start ticks'
$p=GoodPair; $p[1].clock_seconds=120.1
Reject {CompareSnapshots $p[0] $p[1]} 'unbounded slow sample rejected'
$p=GoodPair; $p[1].PSObject.Properties.Remove('image_refresh_failure_count')
Reject {CompareSnapshots $p[0] $p[1]} 'missing failure counter never becomes zero'
$configFixture = Join-Path $fixtureRoot 'config.ini'
[IO.File]::WriteAllText($configFixture,'original',[Text.Encoding]::ASCII)
$cfg1=ConfigFacts $configFixture
$writer=[IO.File]::Open($configFixture,'Open','ReadWrite','ReadWrite,Delete')
try {
    Check ((ConfigFacts $configFixture).sha256 -ceq $cfg1.sha256) 'config read allows existing writer'
} finally { $writer.Dispose() }
$replacement=Join-Path $fixtureRoot 'config.next'
$preserved=Join-Path $fixtureRoot 'config.previous'
[IO.File]::WriteAllText($replacement,'changed',[Text.Encoding]::ASCII)
[IO.File]::Replace($replacement,$configFixture,$preserved)
$cfg2=ConfigFacts $configFixture
Reject {SameConfig $cfg1 $cfg2} 'fresh-path read detects atomic config replacement'
Check ([IO.File]::ReadAllText($preserved) -ceq 'original') 'fixture preserves old config bytes'
SameConfig $cfg2 (ConfigFacts $configFixture)
Check $true 'unchanged current config accepted'
$emptyConfig=Join-Path $fixtureRoot 'empty.ini';[IO.File]::WriteAllBytes($emptyConfig,[byte[]]@())
Reject {ConfigFacts $emptyConfig} 'empty config rejected'
$largeConfig=Join-Path $fixtureRoot 'large.ini';[IO.File]::WriteAllBytes($largeConfig,(New-Object byte[] 1048577))
Reject {ConfigFacts $largeConfig} 'oversize config rejected'
function ReceiptFixture {
    $o=[ordered]@{
        schema_version='v1026-static-stage-result-v1';result='V1026_TRANSFER_STAGED_RUNTIME_RECORDED_NOT_INSTALL_READY'
        product_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce';tooling_commit='c03f7c76ff6e75bfe330275ac0fa01326f357261'
        current_version='1.0.25';current_commit=$commit;protected_stage_root=$stageRoot
        transfer_sha256='F3FBC91CE687DAD1085F34F34C4F014B7D198B941210DB397B442BFA7334796B'
        transfer_manifest_sha256='A32E25C0901AC9CF438517E55DE2B85E03AE7243C9DC997410A1E5D04683286E'
        verified_payload_files=32
        current_runtime_after=[pscustomobject]@{main_pid=1;main_start_utc_ticks=10;backend_pid=2;backend_start_utc_ticks=20}
    }
    foreach ($name in @('installation_ready','installation_authorized','installation_started','application_restart_performed',
        'product_changes_made','automatic_rollback_performed','observation_started','packet_capture_started',
        'added_spot_image_requests','full_120m_allowed','production_promotion_allowed')) { $o[$name]=$false }
    return [pscustomobject]$o
}
$rf=ReceiptFixture
SameRuntime (AssertStageReceipt $rf) (Fixture).runtime
Check $true 'known staging receipt runtime field mapping'
foreach ($name in @('schema_version','result','product_commit','tooling_commit','current_version','current_commit','protected_stage_root','transfer_sha256','transfer_manifest_sha256')) {
    $rf=ReceiptFixture; $rf.$name='wrong'
    Reject {AssertStageReceipt $rf} ('reject staged identity mismatch: '+$name)
}
foreach ($bad in @($true,'false',$null,0)) {
    $rf=ReceiptFixture; $rf.installation_authorized=$bad
    Reject {AssertStageReceipt $rf} ('reject non-false staging authority: '+[string]$bad)
}
$rf=ReceiptFixture;$rf.verified_payload_files=31
Reject {AssertStageReceipt $rf} 'reject staged payload count mismatch'
$rf=ReceiptFixture;$rf.current_runtime_after.backend_pid=$null
Reject {AssertStageReceipt $rf} 'reject missing receipt process identity'
$jsonFile=Join-Path $fixtureRoot 'receipt.json'
[IO.File]::WriteAllText($jsonFile,((ReceiptFixture)|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($true))
$jf=FileFacts $jsonFile
$loaded=ReadJsonFile $jsonFile $jf.sha256
Check ($loaded.result -ceq (ReceiptFixture).result) 'BOM JSON hash and decode use pinned bytes'
Reject {ReadJsonFile $jsonFile ('0'*64)} 'wrong receipt hash rejected before JSON trust'
foreach ($pin in $readPins) { $pin.Dispose() }
$configFile='C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
function StorageFixture {
    return [pscustomobject]@{config_path=$configFile;restart_required=$false;values=[pscustomobject]@{
        settings=[pscustomobject]@{logpath='logs/data';snapshotpath='snapshots';password='fixture-secret-not-to-be-printed'}
        spot=[pscustomobject]@{ip='fixture-device-address';image_capture=[pscustomobject]@{path='spot_images'}}
    }}
}
$storage=SelectStorageSettings (StorageFixture)
Check (-not $storage.active_storage_paths_verified -and -not $storage.paths_followed) 'configured paths never become active storage or backup proof'
$storageJson=$storage|ConvertTo-Json -Depth 5
Check (-not $storageJson.Contains('fixture-secret') -and -not $storageJson.Contains('fixture-device-address')) 'storage projection excludes credentials and device endpoint metadata'
$sf=StorageFixture;$sf.config_path='C:\unexpected.ini'
Reject {SelectStorageSettings $sf} 'unexpected active config path rejected'
$sf=StorageFixture;$sf.values.settings.logpath=$null
Reject {SelectStorageSettings $sf} 'missing configured path not defaulted'
$sf=StorageFixture;$sf.restart_required='false'
Reject {SelectStorageSettings $sf} 'restart state must be typed boolean'
$sf=StorageFixture;$sf.values.spot.image_capture.path=('x'*1025)
Reject {SelectStorageSettings $sf} 'oversized configured storage value rejected'
$p=GoodPair;$p[1].storage_settings.restart_required=$true
Check ((CompareSnapshots $p[0] $p[1]).holds -contains 'pending-config-restart-needs-review') 'pending config restart is held without restarting'
$p=GoodPair;$p[1].storage_settings.logpath='changed'
Check ((CompareSnapshots $p[0] $p[1]).holds -contains 'configured-storage-settings-changed') 'storage setting change during sample held'
foreach ($arrayJson in @('[]','[42]','[true]','[false]','[1788911472.1738272]','[1,2]')) {
    $obj=ConvertFrom-Json -InputObject ('{"v":'+$arrayJson+'}')
    Reject {Required $obj 'v'} ('array shape rejected by Required: '+$arrayJson)
    Reject {CountValue $obj 'v'} ('array shape rejected by Required-to-CountValue: '+$arrayJson)
}
Check ($null -eq (Required ([pscustomobject]@{v=$null}) 'v')) 'scalar null remains null'
Check ((Required ([pscustomobject]@{v=$false}) 'v') -is [bool]) 'scalar false remains boolean'
Check ((Required (ConvertFrom-Json '{"v":1788911472.1738272}') 'v') -is [decimal]) 'scalar Decimal remains Decimal'
& {
    # Exercise the real Snapshot function with in-memory endpoint values, never a listener or network.
    $fixtureCalls=[Collections.Generic.List[string]]::new()
    $baseImage=Fixture
    $imageMap=[ordered]@{}
    foreach ($p in $baseImage.PSObject.Properties) { $imageMap[$p.Name]=$p.Value }
    $imageMap.last_error_at=$null;$imageMap.last_error_code=$null
    foreach ($n in @('source_port_pool_capacity','source_port_pool_guarded_count','source_port_pool_leased_count',
        'source_port_pool_quarantined_count','source_port_pool_rebind_pending_count')) { $imageMap[$n]=0 }
    $imageMap.last_success_at=[decimal]1788911472.1738272
    $fixtureImage=[pscustomobject]$imageMap
    $fixtureCapture=[pscustomobject]@{enabled=$true;mode='all';enqueued_count=100;written_count=100;fact_row_count=100;dropped_count=0;failure_count=0;queue_size=0}
    function RuntimeAnchor { return (Fixture).runtime }
    function LocalGet {
        param([string]$Endpoint)
        $fixtureCalls.Add($Endpoint)
        switch -CaseSensitive ($Endpoint) {
            'health' { return [pscustomobject]@{app_version='1.0.25';spot_temperature=[pscustomobject]@{build_git_commit=$commit}} }
            'api/spot/config' { return [pscustomobject]@{image=$fixtureImage;image_capture=$fixtureCapture} }
            'stats' { return [pscustomobject]@{total_http_5xx_count=0;errors=[pscustomobject]@{queue_size=0;repeat_total=0;last_error_at=$null}} }
            'api/config' { return StorageFixture }
            default { throw 'Unapproved fixture endpoint.' }
        }
    }
    $snapshot=Snapshot
    Check ($snapshot.last_success_at -is [decimal] -and $snapshot.capture_enabled -is [bool]) 'real Snapshot accepts Decimal/null/boolean contract'
    Check (($fixtureCalls -join '|') -ceq 'health|api/spot/config|stats|api/config') 'real Snapshot performs exactly four allowlisted local GET selections'
    Check (-not (($snapshot | ConvertTo-Json -Depth 8).Contains('fixture-secret'))) 'real Snapshot projection excludes unrelated secret fields'
    $fixtureImage.image_refresh_success_count=@(100)
    Reject {Snapshot} 'real Snapshot rejects singleton array counter from LocalGet'
    $fixtureImage.image_refresh_success_count=100
    $fixtureImage.last_success_at=@([decimal]1788911472.1738272)
    Reject {Snapshot} 'real Snapshot rejects singleton array timestamp from LocalGet'
    $fixtureImage.last_success_at=[decimal]1788911472.1738272
    $fixtureCapture.enabled=@($true)
    Reject {Snapshot} 'real Snapshot rejects singleton array boolean from LocalGet'
}
$sha=[Security.Cryptography.SHA256]::Create()
try {$sourceHash=[BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($source))).Replace('-','')}finally{$sha.Dispose()}
$result=[pscustomobject]@{result='V1026_CURRENT_BASELINE_LOCAL_FIXTURES_PASS';powershell_version=$PSVersionTable.PSVersion.ToString();source_sha256=$sourceHash;assertions=$tests.Count;checks=$tests.ToArray();server_main_executed=$false;network_queries_performed=$false;server_runtime_checked=$false;fixture_path=$fixtureRoot}
$json=$result|ConvertTo-Json -Depth 5
[IO.File]::WriteAllText((Join-Path $OutputRoot 'validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
