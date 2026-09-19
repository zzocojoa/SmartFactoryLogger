param(
    [Parameter(Mandatory=$true)][string]$Helper,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$ReleaseRoot,
    [Parameter(Mandatory=$true)][string]$ExtractedAppRoot,
    [Parameter(Mandatory=$true)][string]$UninstallerPath,
    [Parameter(Mandatory=$true)][string]$Launcher
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition-cne'Desktop'-or$PSVersionTable.PSVersion.ToString()-notlike'5.1.*'){throw 'Native PowerShell 5.1 test required.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$OK,[string]$Name)if(-not$OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name)$rejected=$false;try{&$Code|Out-Null}catch{$rejected=$true};Check $rejected $Name}
if([IO.File]::Exists($OutputRoot)-or[IO.Directory]::Exists($OutputRoot)){throw 'Fixture already exists; preserve it.'}
$fixture=[IO.Path]::GetFullPath($OutputRoot)
[void][IO.Directory]::CreateDirectory($fixture)
$testReleaseRoot=$ReleaseRoot
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Helper,[ref]$tokens,[ref]$errors)
Check ($errors.Count-eq0) 'helper parses under PS5.1'
$functions=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($function in $functions){.([scriptblock]::Create($function.Extent.Text))}
# Only literal/settings assignments at script root; no server try/main is invoked.
foreach($statement in $ast.EndBlock.Statements){
    if($statement-is[Management.Automation.Language.AssignmentStatementAst]){.([scriptblock]::Create($statement.Extent.Text))}
}
$commands=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.CommandAst]},$true)|ForEach-Object{$_.GetCommandName()})
foreach($forbidden in @('Start-Process','Stop-Process','Remove-Item','Move-Item','Invoke-Expression','Set-Content','Clear-Content','Start-Sleep','LaunchInstallerStandard','AssertStopped')){
    Check ($forbidden -notin $commands) ('no '+$forbidden)
}
Check ($functions.Name -notcontains 'LaunchInstallerStandard') 'no installer function copied'
$helperHash=(Get-FileHash -LiteralPath $Helper -Algorithm SHA256).Hash

try {
    $manifestPath=Join-Path $testReleaseRoot 'extracted-payload-manifest.json'
    $null=FileFact $manifestPath 'D527AA7F8284AF6917FE1166F070871C07BCA379F03BD32740BDEF70CD48814F'
    $null=FileFact (Join-Path $testReleaseRoot 'release_identity.json') '7EB46147F55DAD515E507196A7E1FBACD7D1B075E870DB159F82580DA64E3493'
    $manifest=ReadJson $manifestPath
    $realMap=ManifestMap $manifest
    Check ($realMap.Count-eq1646) 'real manifest plus uninstaller membership'
    $payloadMap=$realMap.Clone();$payloadMap.Remove($uninstaller.path)
    $inventory=InstalledInventory $ExtractedAppRoot $payloadMap
    $realRows=[Collections.Generic.List[string]]::new();[long]$realBytes=0
    foreach($name in $inventory.Keys){
        $entry=$payloadMap[$name]
        $s=[IO.File]::Open($inventory[$name],'Open','Read','Read')
        try{$h=HashStream $s;$length=$s.Length}finally{$s.Dispose()}
        if($h-cne$entry.sha256-or$length-ne$entry.length){throw 'Real extracted payload differs.'}
        $realRows.Add("$name`0$length`0$h`n");$realBytes+=$length
    }
    Check ((HashRows $realRows.ToArray())-ceq$expectedPayloadTree-and$realBytes-eq560922854) 'every real packaged payload byte verified'
    $unFact=FileFact $UninstallerPath $uninstaller.sha256 $uninstaller.length
    $realRows.Add("$($uninstaller.path)`0$($unFact.length)`0$($unFact.sha256)`n")
    Check ((HashRows $realRows.ToArray())-ceq$expectedInstalledTree-and($realBytes+$unFact.length)-eq$expectedInstalledBytes) 'real combined 1646-file tree identity'

    foreach($name in @('../bad','a/../b','/absolute','C:/absolute','a\b','a:stream','a//b','a/./b','a.','a ','NUL','CON.txt','a/*','')){
        Reject {RelativeName $name} ('unsafe manifest path rejected: '+$name)
    }
    RelativeName 'resources/example.dll';Check $true 'normal relative path accepted'
    function FixtureFile {param([string]$Path,[string]$Content)[IO.File]::WriteAllText($Path,$Content,[Text.UTF8Encoding]::new($false))}
    function Entry {param([string]$Root,[string]$Name)$path=Join-Path $Root $Name;$s=[IO.File]::OpenRead($path);try{[pscustomobject]@{path=$Name;length=$s.Length;sha256=HashStream $s}}finally{$s.Dispose()}}
    function Rows {param([object[]]$Entries)@($Entries|ForEach-Object{"$($_.path)`0$($_.length)`0$($_.sha256)`n"})}
    $small=Join-Path $fixture 'small';[void][IO.Directory]::CreateDirectory($small)
    FixtureFile (Join-Path $small 'app.exe') 'fixture app'
    FixtureFile (Join-Path $small 'uninstall.exe') 'fixture uninstaller'
    $appEntry=Entry $small 'app.exe';$uninstaller=Entry $small 'uninstall.exe'
    $expectedPayloadFiles=1;$expectedPayloadTree=HashRows (Rows @($appEntry))
    $expectedInstalledBytes=$appEntry.length+$uninstaller.length
    $expectedInstalledTree=HashRows (Rows @($appEntry,$uninstaller))
    $smallManifest=[pscustomobject]@{schema='sfl-extracted-payload-v1';file_count=1;tree_sha256=$expectedPayloadTree;files=@($appEntry)}
    $smallMap=ManifestMap $smallManifest
    $tree=VerifyInstalled $small $smallMap
    Check ($tree.file_count-eq2-and$tree.tree_sha256-ceq$expectedInstalledTree) 'complete synthetic installed verification'
    $caseMap=@{'APP.EXE'=[pscustomobject]@{path='APP.EXE';length=$appEntry.length;sha256=$appEntry.sha256};'uninstall.exe'=$uninstaller}
    Reject {InstalledInventory $small $caseMap} 'case alias rejected'
    $missing=Join-Path $fixture 'missing';[void][IO.Directory]::CreateDirectory($missing)
    FixtureFile (Join-Path $missing 'app.exe') 'fixture app'
    Reject {InstalledInventory $missing $smallMap} 'missing file rejected'
    $extra=Join-Path $fixture 'extra';[void][IO.Directory]::CreateDirectory($extra)
    FixtureFile (Join-Path $extra 'unknown.dat') 'unknown'
    Reject {InstalledInventory $extra $smallMap} 'unexpected file rejected'
    $linkedRoot=Join-Path $fixture 'linked';[void][IO.Directory]::CreateDirectory($linkedRoot)
    $junction=Join-Path $linkedRoot 'redirect'
    $null=New-Item -ItemType Junction -Path $junction -Target $small -ErrorAction Stop
    Reject {InstalledInventory $linkedRoot $smallMap} 'actual directory reparse point rejected before traversal'
    Reject {Plain (Join-Path $junction 'app.exe')} 'reparse ancestor rejected'
    FixtureFile (Join-Path $small 'app.exe') 'fixture bad'
    Reject {VerifyInstalled $small $smallMap} 'same-length tamper rejected'
    FixtureFile (Join-Path $small 'app.exe') 'longer fixture bad'
    Reject {VerifyInstalled $small $smallMap} 'length tamper rejected'
    $oldClock=$clock;$clock=[pscustomobject]@{Elapsed=[TimeSpan]::FromSeconds(301)}
    Reject {InstalledInventory $small $smallMap} 'time budget enforced'
    $clock=$oldClock
    $badManifest=$smallManifest.PSObject.Copy();$badManifest.schema='unexpected'
    Reject {ManifestMap $badManifest} 'manifest schema rejected'
    $badManifest=$smallManifest.PSObject.Copy();$badManifest.tree_sha256='0'*64
    Reject {ManifestMap $badManifest} 'manifest tree mismatch rejected'
    $expectedPayloadFiles=2
    $duplicate=$smallManifest.PSObject.Copy();$duplicate.file_count=2;$duplicate.files=@($appEntry,$appEntry)
    Reject {ManifestMap $duplicate} 'duplicate manifest member rejected'
    $expectedPayloadFiles=1

    $runA=[pscustomobject]@{main_pid=1;backend_pid=2;processes=@([pscustomobject]@{pid=2;start_ticks=100;elevated=$false})}
    SameRuntime $runA ($runA|ConvertTo-Json -Depth 5|ConvertFrom-Json)
    Check $true 'runtime identity equality accepted'
    $runB=$runA|ConvertTo-Json -Depth 5|ConvertFrom-Json;$runB.processes[0].start_ticks=101
    Reject {SameRuntime $runA $runB} 'PID reuse or restart rejected'
    $health=[pscustomobject]@{app_version='1.0.26';spot_temperature=[pscustomobject]@{build_git_commit=$expectedCommit};runtime_kind='frozen';executable_path=$installRoot+'\resources\backend\SmartFactoryBackend.exe';frontend_runtime_class='packaged-resources';frontend_static_ready=$true}
    HealthIdentity $health;Check $true 'exact packaged health accepted'
    $health.spot_temperature.build_git_commit='a'*40
    Reject {HealthIdentity $health} 'different health commit rejected'
    $image=[pscustomobject]@{config_attestation_status='fingerprint_mismatch';config_operator_verified=$false;config_drift_detected=$true;config_drift_fields=@('spot_config_fingerprint_sha256');low_signal_comparator_verified=$false;spot_config_verified_fingerprint_sha256='74d2c05108eac93f7f3ef33b14f8b9018c3404b8996c0d6e7f94e5abc3da48ab';image_status='ok';image_source='upstream';image_refresh_success_count=123;image_refresh_failure_count=0;source_port_transport_failure_count=0;secret='SENSITIVE_SENTINEL_DO_NOT_EXPORT';source_port_recent_request_events=@('SENSITIVE_SENTINEL_DO_NOT_EXPORT')}
    $errorsSummary=[pscustomobject]@{queue_size=0}
    $selected=SelectedStatus $image $errorsSummary
    Check ($selected.historical_v1020_attestation_present-and$selected.fingerprint_only_drift-and-not$selected.config_operator_verified) 'attestation warning retained separately'
    Check (($selected|ConvertTo-Json)-notmatch'SENSITIVE_SENTINEL') 'private text and request histories excluded'
    $image.image_refresh_success_count='123'
    Reject {SelectedStatus $image $errorsSummary} 'string counter is not silently coerced'
    $image.image_refresh_success_count=123;$image.config_operator_verified='false'
    Reject {SelectedStatus $image $errorsSummary} 'string bool is not silently coerced'

    $receipt=Join-Path $fixture 'fixture-result.json'
    $receiptHash=WriteJsonNew $receipt ([ordered]@{result='SYNTHETIC';file_count=2})
    Check ((Get-FileHash -LiteralPath $receipt -Algorithm SHA256).Hash-ceq$receiptHash) 'receipt rehashed after writing'
    Reject {WriteJsonNew $receipt ([ordered]@{result='replacement'})} 'existing evidence never overwritten'
    $blockedReceipt=Join-Path $fixture 'existing-sidecar.json'
    FixtureFile ($blockedReceipt+'.sha256.txt') 'preserved'
    Reject {WriteJsonNew $blockedReceipt ([ordered]@{result='replacement'})} 'existing sidecar prevents new receipt'
    Check (-not[IO.File]::Exists($blockedReceipt)) 'sidecar rejection leaves result path absent'
    $acl=PrivateAcl
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Check ($acl.AreAccessRulesProtected-and$rules.Count-eq2-and@($rules|Where-Object{$_.IdentityReference.Value-cin@('S-1-5-18','S-1-5-32-544')}).Count-eq2) 'admin and SYSTEM-only ACL object'
    $reportRules=@((ReportAcl).GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $operatorRules=@($reportRules|Where-Object{$_.IdentityReference.Value-ceq$expectedUser})
    Check ($reportRules.Count-eq3-and$operatorRules.Count-eq1-and($operatorRules[0].FileSystemRights-band[Security.AccessControl.FileSystemRights]::Write)-eq0) 'selected report grants operator read but no write'
    InitializeTokenInspector
    Check ([SflInstallToken]::UserSid($PID)-ceq[Security.Principal.WindowsIdentity]::GetCurrent().User.Value) 'native token query fixture'
    $maxOutput='C:\ProgramData\SFLOps\runs\v1026-tree-read-20260916-235959-'+('f'*32)+'\result.json.sha256.txt'
    Check ($maxOutput.Length-lt240) 'output path length budget'

    $launcherText=[IO.File]::ReadAllText($Launcher)
    $null=[Management.Automation.Language.Parser]::ParseInput($launcherText,[ref]$tokens,[ref]$errors)
    Check ($errors.Count-eq0) 'short copy/paste launcher parses under PS5.1'
    $dummy=Join-Path $fixture 'dummy-helper.ps1'
    FixtureFile $dummy "Write-Output 'PINNED_LAUNCH_FIXTURE_OK'"
    $dummyHash=(Get-FileHash -LiteralPath $dummy -Algorithm SHA256).Hash
    $dummyLaunch=$launcherText.Replace('C:\Users\user\Desktop\SmartFactory\read-installed-v1026.ps1',$dummy).Replace($helperHash,$dummyHash)
    $output=@(& ([scriptblock]::Create($dummyLaunch)))
    Check ($output.Count-eq1-and$output[0]-ceq'PINNED_LAUNCH_FIXTURE_OK') 'exact short launcher executes verified bytes'
    Reject {& ([scriptblock]::Create($dummyLaunch.Replace($dummyHash,('0'*64))))} 'short launcher rejects altered hash before execution'

    $result=[ordered]@{result='V1026_INSTALLED_READ_LOCAL_TEST_PASS';assertions=$checks.Count;powershell_version=$PSVersionTable.PSVersion.ToString();helper_sha256=$helperHash;real_payload_files_verified=1645;real_uninstaller_verified=$true;server_main_executed=$false;network_requests_performed=$false;installer_started=$false;product_changes_made=$false;actual_server_acl_creation_tested=$false;actual_server_process_and_api_binding_tested=$false;checks=$checks.ToArray()}
    [IO.File]::WriteAllText((Join-Path $fixture 'validation-result.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    Write-Host ('[LOCAL PASS] assertions='+$checks.Count+'; server main never executed')
}
catch { Write-Host $_.ScriptStackTrace; throw }
finally {foreach($pin in $pins){$pin.Dispose()}}
