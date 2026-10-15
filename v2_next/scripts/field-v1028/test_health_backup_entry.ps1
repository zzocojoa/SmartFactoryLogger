param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $OutputRoot){throw 'new-test-root-required'}
$null=[IO.Directory]::CreateDirectory($OutputRoot)
$launcher=$PackageRoot+'\invoke-health-backup.ps1'
$bundle=$PackageRoot+'\backup'
$pin=(Get-FileHash -LiteralPath ($bundle+'\bundle-manifest.json') -Algorithm SHA256).Hash
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($launcher,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'launcher-parse'}
foreach($definition in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
    . ([scriptblock]::Create($definition.Extent.Text))
}
$checks=[Collections.Generic.List[string]]::new()
function Check([bool]$Value,[string]$Name){if(-not $Value){throw ('FAILED:'+ $Name)};$checks.Add($Name)}
function Reject([scriptblock]$Action,[string]$Message,[string]$Name){
    $failure=$null;try{& $Action}catch{$failure=$_.Exception.Message}
    Check ($null -ne $failure -and $failure.Contains($Message)) $Name
}
Invoke-PinnedStreamsCopyCommand $bundle $pin -LibraryOnly
Check $true 'actual-sealed-package-library-load'
Reject {Invoke-PinnedStreamsCopyCommand $bundle ('0'*64) -LibraryOnly} 'External manifest pin mismatch' 'wrong-external-pin-rejected'
$tampered=$OutputRoot+'\tampered';Copy-Item -LiteralPath $bundle -Destination $tampered -Recurse
[IO.File]::AppendAllText(($tampered+'\README.txt'),'tamper')
Reject {Invoke-PinnedStreamsCopyCommand $tampered $pin -LibraryOnly} 'Payload length/hash mismatch' 'changed-member-rejected'
$extra=$OutputRoot+'\extra';Copy-Item -LiteralPath $bundle -Destination $extra -Recurse
[IO.File]::WriteAllText(($extra+'\unexpected.txt'),'extra')
Reject {Invoke-PinnedStreamsCopyCommand $extra $pin -LibraryOnly} 'Folder membership mismatch' 'extra-member-rejected'
$scope=Get-Content -LiteralPath ($bundle+'\scope.json') -Raw|ConvertFrom-Json
Check ($scope.expected_app_version -ceq '1.0.28' -and $scope.preceding_candidate_build_reference -ceq '4cc7393e1bafbf90a329726aed9470fe0daacb21' -and $scope.approved_operating_build_reference -ceq '541d701d544eea6a8a4e4836047077eaf9cfaf30') 'candidate-and-approved-rollback-identities-distinct'
$probe=@'
$ErrorActionPreference='Stop'
if(-not [Environment]::Is64BitOperatingSystem){throw '64-bit Windows required'}
$part=if([Environment]::Is64BitProcess){'System32'}else{'Sysnative'}
$selected=[IO.Path]::Combine([Environment]::GetFolderPath('Windows'),$part,'WindowsPowerShell\v1.0\powershell.exe')
Write-Host ('BOOTSTRAP_IS64='+[Environment]::Is64BitProcess)
Write-Host ('SELECTED_NATIVE='+$selected)
& $selected -NoProfile -NonInteractive -ExecutionPolicy Bypass -File '@LAUNCHER@' -ExpectedBundleManifestSha256 '@PIN@' -BundlePath '@BUNDLE@' -LibraryOnly
exit $LASTEXITCODE
'@
$probe=$probe.Replace('@LAUNCHER@',$launcher).Replace('@PIN@',$pin).Replace('@BUNDLE@',$bundle)
$probePath=$OutputRoot+'\architecture-probe.ps1';[IO.File]::WriteAllText($probePath,$probe,[Text.UTF8Encoding]::new($false))
foreach($arch in @('System32','SysWOW64')){
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=[Environment]::GetFolderPath('Windows')+'\'+$arch+'\WindowsPowerShell\v1.0\powershell.exe'
    $start.Arguments='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$probePath+'"'
    $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
    $process=[Diagnostics.Process]::new();$process.StartInfo=$start
    try{
        if(-not $process.Start()){throw 'probe-start'}
        $retained=$process.Handle
        $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit(30000)){throw 'probe-timeout-no-force'}
        $a=$stdout.GetAwaiter().GetResult();$b=$stderr.GetAwaiter().GetResult()
        [IO.File]::WriteAllText(($OutputRoot+'\'+$arch+'.stdout.log'),$a)
        [IO.File]::WriteAllText(($OutputRoot+'\'+$arch+'.stderr.log'),$b)
        Check ($process.ExitCode -eq 0 -and $a.Contains('LIBRARY_ONLY_VERIFIED_NO_SOURCE_DATA_ACCESSED') -and $b.Length -eq 0) ($arch+'-native-library-child-exit-zero')
        $flag=if($arch -ceq 'System32'){'True'}else{'False'}
        Check ($a.Contains('BOOTSTRAP_IS64='+$flag) -and $retained -ne [IntPtr]::Zero) ($arch+'-actual-bootstrap-architecture-and-handle')
    }finally{$process.Dispose()}
}
$result=[ordered]@{status='PASS';checks=$checks.Count;names=$checks.ToArray();launcher_sha256=(Get-FileHash -LiteralPath $launcher).Hash;manifest_sha256=$pin;production_source_roots_accessed=$false;server_accessed=$false;full_backup_executed=$false}
[IO.File]::WriteAllText(($OutputRoot+'\tests-result.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 5
