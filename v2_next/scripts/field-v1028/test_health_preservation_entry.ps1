param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][string]$PackagePin,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $OutputRoot){throw 'fresh-test-output-required'}
$null=[IO.Directory]::CreateDirectory($OutputRoot)
$native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
$checks=[Collections.Generic.List[string]]::new()
function Test([bool]$Value,[string]$Name){if(-not $Value){throw ('FAILED: '+$Name)};$checks.Add($Name)}
function Invoke-Entry([string]$Root,[string]$Pin,[string]$Name,[bool]$Library=$true){
    $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName=$native
    $info.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$Root+'\invoke-health-preservation.ps1" -ExpectedPackageManifestSha256 '+$Pin+' -PackageRoot "'+$Root+'"'
    if($Library){$info.Arguments+=' -LibraryOnly'}
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.WindowStyle='Hidden'
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $process=[Diagnostics.Process]::new();$process.StartInfo=$info
    try{
        $null=$process.Start();$retained=$process.Handle
        $stdoutTask=$process.StandardOutput.ReadToEndAsync();$stderrTask=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(30000)){throw 'test-child-timeout-no-force'}
        $stdout=$stdoutTask.GetAwaiter().GetResult();$stderr=$stderrTask.GetAwaiter().GetResult()
        [IO.File]::WriteAllText(($OutputRoot+'\'+$Name+'.stdout.txt'),$stdout)
        [IO.File]::WriteAllText(($OutputRoot+'\'+$Name+'.stderr.txt'),$stderr)
        return @{exit=[int]$process.ExitCode;stdout=$stdout;stderr=$stderr;handle=($retained -ne [IntPtr]::Zero)}
    }finally{$process.Dispose()}
}
$ok=Invoke-Entry $PackageRoot $PackagePin 'valid'
Test ($ok.exit -eq 0 -and $ok.handle -and $ok.stdout -match 'LIBRARY_ONLY_VERIFIED_NO_SOURCE_DATA_ACCESSED') 'locked-package-native-child-load'
$bad=Invoke-Entry $PackageRoot ('0'*64) 'bad-pin'
Test ($bad.exit -eq 1 -and $bad.stdout -match 'FAILURE=package-manifest-pin') 'bad-manifest-pin-rejected'
foreach($case in @('extra','tampered')){
    $copy=Join-Path $OutputRoot $case
    Copy-Item -LiteralPath $PackageRoot -Destination $copy -Recurse
    if($case -eq 'extra'){[IO.File]::WriteAllText(($copy+'\unexpected.txt'),'unlisted')}
    else{[IO.File]::AppendAllText(($copy+'\cold-data-observation.cs'),'tampered')}
    $result=Invoke-Entry $copy $PackagePin $case
    $expected=if($case -eq 'extra'){'package-directory-members'}else{'package-payload-pin'}
    Test ($result.exit -eq 1 -and $result.stdout -match ('FAILURE='+$expected)) ($case+' package-rejected')
}
if($env:COMPUTERNAME -cne 'DESKTOP-CIIT7LK'){
    $wrongHost=Invoke-Entry $PackageRoot $PackagePin 'wrong-host' $false
    Test ($wrongHost.exit -eq 1 -and $wrongHost.stdout -match 'FAILURE=server-operator-admin-required') 'production-host-rejection-before-source-read'
}else{throw 'entry-negative-tests-must-not-run-on-production-server'}
$record=@{status='PASS';checks=$checks.Count;names=$checks.ToArray();package_manifest_sha256=$PackagePin;server_accessed=$false;source_data_read=$false;installer_started=$false}
[IO.File]::WriteAllText(($OutputRoot+'\result.json'),($record|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
$record|ConvertTo-Json -Depth 5
