[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedPackageManifestSha256,
    [string]$PackageRoot='',
    [switch]$LibraryOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$held=[Collections.Generic.List[IDisposable]]::new()
$runRoot=$null
$phase='package'
function Read-PreservationPackage([string]$Root,[string]$Pin) {
    $allowed=@('invoke-health-preservation.ps1','cold-data-observation.cs','cold-data-observation.dll',
        'cold-backup-streams-core.dll','copy-cold-operating-streams.ps1','scope.json','README.txt',
        'test_cold_data_observation.ps1')
    $rootPath=[IO.Path]::GetFullPath($Root)
    $manifestStream=[IO.File]::Open(($rootPath+'\package-manifest.json'),'Open','Read','Read')
    $held.Add($manifestStream)
    $hasher=[Security.Cryptography.SHA256]::Create()
    try{
        if($manifestStream.Length -gt 65536 -or
            [BitConverter]::ToString($hasher.ComputeHash($manifestStream)).Replace('-','') -cne $Pin){throw 'package-manifest-pin'}
        $manifestStream.Position=0
        $reader=[IO.StreamReader]::new($manifestStream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
        $names=@($manifest.files|ForEach-Object name)
        if($manifest.schema -cne 'sfl-health-preservation-package-v1' -or $names.Count -ne $allowed.Count -or
            @($names|Select-Object -Unique).Count -ne $allowed.Count -or
            @($names|Where-Object{$_ -cnotin $allowed}).Count){throw 'package-members'}
        $actual=@([IO.Directory]::GetFileSystemEntries($rootPath)|ForEach-Object{[IO.Path]::GetFileName($_)})
        if($actual.Count -ne $allowed.Count+1 -or
            @($actual|Where-Object{$_ -cnotin ($allowed+@('package-manifest.json'))}).Count){throw 'package-directory-members'}
        $payloads=@{}
        foreach($entry in $manifest.files){
            $stream=[IO.File]::Open(($rootPath+'\'+$entry.name),'Open','Read','Read');$held.Add($stream)
            if($stream.Length -lt 1 -or $stream.Length -gt 10MB -or $stream.Length -ne $entry.bytes -or
                [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','') -cne $entry.sha256){throw ('package-payload-pin:'+ $entry.name)}
            $stream.Position=0;$memory=[IO.MemoryStream]::new()
            try{$stream.CopyTo($memory);$payloads[$entry.name]=$memory.ToArray()}finally{$memory.Dispose()}
        }
        foreach($pinPair in @(
            @('cold-backup-streams-core.dll','FB12E3ACB370D86999156600EFB3CD23083D890DFEC1216CF4E06E9C1CCE2A26'),
            @('copy-cold-operating-streams.ps1','2EF23477BA5FAFE4E339F9B9738351086494E02FBF4118B6893E933083FFEB70'))){
            if([BitConverter]::ToString($hasher.ComputeHash([byte[]]$payloads[$pinPair[0]])).Replace('-','') -cne $pinPair[1]){throw 'legacy-dependency-pin'}
        }
        return $payloads
    }finally{$hasher.Dispose()}
}
function Assert-PreservationCapacity([string]$Path){
    # No data-copy reservation. Keep 10 GiB operational reserve, 2 GiB installer
    # workspace, up to two 1 GiB manifests, and 256 MiB small receipts.
    $required=[long](14GB+256MB)
    $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($Path))
    if($drive.DriveType -ne 'Fixed' -or $drive.DriveFormat -cne 'NTFS' -or $drive.AvailableFreeSpace -lt $required){
        throw 'preservation-and-install-workspace-insufficient'
    }
    return [ordered]@{required_free_bytes=$required;available_free_bytes=$drive.AvailableFreeSpace;
        full_data_copy_reserved=$false;operating_reserve_bytes=[long](10GB)}
}
try {
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native){throw 'native-ps51-x64-required'}
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    if([string]::IsNullOrEmpty($PackageRoot)){$PackageRoot=$PSScriptRoot}
    $payloads=Read-PreservationPackage $PackageRoot $ExpectedPackageManifestSha256
    [void][Reflection.Assembly]::Load($payloads['cold-backup-streams-core.dll'])
    [SflColdCopyStreamsV2.Engine]::Plain([IO.Path]::GetFullPath($PackageRoot),$false)
    foreach($name in $payloads.Keys){[SflColdCopyStreamsV2.Engine]::Plain((Join-Path $PackageRoot $name),$false)}
    [void][Reflection.Assembly]::Load($payloads['cold-data-observation.dll'])
    $source=[Text.UTF8Encoding]::new($false,$true).GetString($payloads['copy-cold-operating-streams.ps1'])
    $tokens=$null;$parseErrors=$null
    $ast=[Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$parseErrors)
    if($parseErrors.Count){throw 'legacy-function-parse'}
    foreach($definition in $ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
        . ([scriptblock]::Create($definition.Extent.Text))
    }
    if($LibraryOnly){Write-Host 'LIBRARY_ONLY_VERIFIED_NO_SOURCE_DATA_ACCESSED';exit 0}
    $phase='server-and-scope'
    $scope=[Text.UTF8Encoding]::new($false,$true).GetString($payloads['scope.json'])|ConvertFrom-Json
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    if([Environment]::MachineName -cne 'DESKTOP-CIIT7LK' -or $scope.expected_computer -cne 'DESKTOP-CIIT7LK' -or
        $identity.User.Value -cne 'S-1-5-21-2762931165-1280404403-2847611662-1001' -or
        $scope.expected_operator_sid -cne $identity.User.Value -or
        -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'server-operator-admin-required'}
    if($scope.new_full_backup_policy -cne 'OMITTED_FOR_1029_HEALTH_ONLY' -or
        $scope.expected_app_version -cne '1.0.28' -or
        $scope.preceding_candidate_build_reference -cne '4cc7393e1bafbf90a329726aed9470fe0daacb21'){throw 'scope-build-policy'}
    $factory=[Environment]::GetFolderPath('DesktopDirectory')+'\SmartFactory'
    if($factory -ine 'C:\Users\user\Desktop\SmartFactory' -or $factory -ine $scope.expected_factory_root -or
        [Environment]::GetFolderPath('UserProfile') -ine $scope.expected_profile){throw 'server-profile-desktop'}
    [SflColdCopyStreamsV2.Engine]::Plain($factory,$false)
    $roots=[string[]]$scope.source_roots
    $expected=@('C:\Users\user\AppData\Roaming\SmartFactoryLogger','C:\Users\user\AppData\Roaming\smart-factory-logger-v2')
    if($roots.Count -ne 2 -or ($roots -join '|') -cne ($expected -join '|')){throw 'source-root-contract'}
    $capacity=Assert-PreservationCapacity $factory
    $runRoot=Join-Path $factory ('O'+[Guid]::NewGuid().ToString('N').Substring(0,8))
    New-ColdResultDirectory $runRoot $scope.expected_operator_sid
    Write-ColdNewJson ($runRoot+'\intent.json') ([ordered]@{schema='sfl-health-preservation-intent-v1';
        package_manifest_sha256=$ExpectedPackageManifestSha256;source_roots=$roots;capacity=$capacity;
        new_full_data_backup_created=$false;installation_performed=$false;normal_close_requested_by_helper=$false})
    $phase='operating-generation-preflight'
    $warmObservation=Get-ColdObservation
    $warmIdentity=Get-ColdWarmIdentity $warmObservation $scope
    $warmHealth=Get-ColdHealthBinding $scope
    Write-ColdNewBytes ($runRoot+'\health-before-preflight.json') $warmHealth.raw_bytes
    Write-ColdNewJson ($runRoot+'\runtime-before-preflight.json') @{observation=$warmObservation;identity=$warmIdentity;logger_service_instance_id=$warmHealth.logger_service_instance_id}
    $warmGuard=[Action]{Assert-ColdSameWarmIdentity $warmIdentity (Get-ColdWarmIdentity (Get-ColdObservation) $scope)}
    $progress=[Action[string,long,long,long]]{param($name,$bytes,$files,$elapsed) Write-Host ('PROGRESS phase='+$name+' bytes='+$bytes+' files='+$files+' elapsed_ms='+$elapsed)}
    $engine=[SflColdCopyStreamsV2.Engine]::new($roots,$warmGuard,$progress)
    $phase='live-path-stream-inventory'
    $inventory=$engine.Inventory($runRoot+'\v')
    $warmGuard.Invoke()
    $readyHealth=Get-ColdHealthBinding $scope
    if($readyHealth.logger_service_instance_id -cne $warmHealth.logger_service_instance_id){throw 'logger-generation-changed'}
    $readyObservation=Get-ColdObservation
    Assert-ColdSameWarmIdentity $warmIdentity (Get-ColdWarmIdentity $readyObservation $scope)
    Write-ColdNewBytes ($runRoot+'\health-before-ready.json') $readyHealth.raw_bytes
    Write-ColdNewJson ($runRoot+'\runtime-before-ready.json') @{observation=$readyObservation;identity=$warmIdentity;logger_service_instance_id=$readyHealth.logger_service_instance_id}
    Write-ColdNewJson ($runRoot+'\preflight.json') @{phase='READY_FOR_NORMAL_APP_EXIT';time=[DateTime]::UtcNow.ToString('o');
        inventory=$inventory;capacity=(Assert-PreservationCapacity $factory);new_full_data_backup_created=$false}
    Write-Host ('READY_FOR_NORMAL_APP_EXIT RESULT_PATH='+$runRoot)
    $phase='waiting-normal-app-exit';$wait=[Diagnostics.Stopwatch]::StartNew();$quiet=0
    while($quiet -lt 3){
        $observation=Get-ColdObservation
        if($observation.processes.Count -eq 0 -and -not $observation.port8000_listening){$quiet++}else{$quiet=0}
        if($wait.Elapsed.TotalSeconds -gt 450){throw 'normal-exit-timeout-no-force'}
        if($quiet -lt 3){Start-Sleep -Seconds 2}
    }
    Write-ColdNewJson ($runRoot+'\runtime-absence.json') @{observation=$observation;quiet_observations=$quiet;preceding_identity=$warmIdentity;normal_shutdown_receipt_verified=$false}
    $coldGuard=[Action]{Assert-ColdObservation (Get-ColdObservation)}
    $observer=[SflColdObservationV1.Observer]::new($roots,$coldGuard,$progress)
    $phase='capture-closed-original'
    $null=Assert-PreservationCapacity $factory
    $captured=$observer.Capture($runRoot+'\observed.tsv')
    $phase='verify-closed-original'
    $verified=$observer.Verify($runRoot+'\observed.tsv',$captured.ManifestSha256)
    foreach($key in @('Files','Directories','NamedStreams','Bytes')){
        if($captured.$key -ne $verified.$key){throw 'observation-counts-differ'}
    }
    $coldGuard.Invoke()
    $result=[ordered]@{schema='sfl-health-preservation-result-v1';status='CLOSED_ORIGINAL_OBSERVED_AND_REVERIFIED_NO_BACKUP';
        time=[DateTime]::UtcNow.ToString('o');run_root=$runRoot;source_roots=$roots;totals=$verified;
        file_manifest_sha256=$verified.ManifestSha256;preceding_operating_identity=$warmIdentity;
        preceding_logger_service_instance_id=$warmHealth.logger_service_instance_id;
        original_default_named_streams_and_metadata_reverified=$true;app_backend_port_absence_observed=$true;
        new_full_data_backup_created=$false;normal_shutdown_attestation='NOT_EVALUATED';
        installation_performed=$false;application_started=$false;full_data_gate='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false}
    Write-ColdNewJson ($runRoot+'\result.json') $result
    Write-Host ('RESULT_PATH='+$runRoot)
    Write-Host ('MANIFEST_SHA256='+$verified.ManifestSha256)
    Write-Host ('RESULT_SHA256='+[SflColdCopyStreamsV2.Engine]::FileHash($runRoot+'\result.json',[long]::MaxValue))
    exit 0
}catch{
    if($runRoot -and [IO.Directory]::Exists($runRoot)){
        Write-ColdNewJson ($runRoot+'\hold.json') @{status='HOLD';phase=$phase;error=$_.Exception.Message;
            new_full_data_backup_created=$false;installer_started=$false;forced_termination=$false;release_gate='HOLD'}
        Write-Host ('HOLD_RESULT_PATH='+$runRoot)
    }
    Write-Host ('FAILURE='+$_.Exception.Message)
    Write-Error $_ -ErrorAction Continue
    exit 1
}finally{foreach($handle in $held){$handle.Dispose()}}
