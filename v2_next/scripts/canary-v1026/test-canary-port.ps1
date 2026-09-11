[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$KitRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$modulePath=Join-Path $PSScriptRoot 'evidence_zip_integrity.psm1'
Import-Module $modulePath -Force
Import-Module (Join-Path $PSScriptRoot 'v1026_release_identity_integrity.psm1') -Force
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('sfl-v1026-port-test-'+[guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($testRoot)
$passed=[Collections.Generic.List[string]]::new()
function Check { param([bool]$Value,[string]$Name) if (-not $Value) { throw ('FAIL: '+$Name) }; $passed.Add($Name) }
function Reject { param([scriptblock]$Action,[string]$Label) $rejected=$false; try { & $Action | Out-Null } catch { $rejected=$true }; Check $rejected $Label }
function FixtureText { param([string]$Path,[string]$Value) [IO.File]::WriteAllText($Path,$Value,[Text.UTF8Encoding]::new($false)) }
function Native-Result {
    param([string]$Program,[string[]]$Argv)
    $saved=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        $output=@(& $native -NoProfile -ExecutionPolicy Bypass -File $Program @Argv 2>&1)
        $code=$LASTEXITCODE
    } finally { $ErrorActionPreference=$saved }
    return [pscustomobject]@{code=$code;text=($output | Out-String)}
}
function FixtureZip {
    param([string]$Path,[object[]]$Entries)
    $out=[IO.File]::Open($Path,'CreateNew','Write','None')
    $archive=[IO.Compression.ZipArchive]::new($out,'Create',$true)
    try {
        foreach ($item in $Entries) {
            $entry=$archive.CreateEntry($item.name)
            if ($item.PSObject.Properties['attributes']) { $entry.ExternalAttributes=$item.attributes }
            $stream=$entry.Open()
            try { $bytes=[Text.Encoding]::UTF8.GetBytes($item.text); $stream.Write($bytes,0,$bytes.Length) }
            finally { $stream.Dispose() }
        }
    } finally { $archive.Dispose(); $out.Dispose() }
}

# Load definitions through the AST only: never execute the controller's live entry point.
$controllerPath=Join-Path $KitRoot 'invoke-spot-realtime-image-canary-120m.ps1'
$tokens=$null; $parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($controllerPath,[ref]$tokens,[ref]$parseErrors)
Check (@($parseErrors).Count -eq 0) 'controller-parse'
$functions=@($ast.EndBlock.Statements | Where-Object { $_ -is [Management.Automation.Language.FunctionDefinitionAst] })
foreach ($definition in $functions) { . ([scriptblock]::Create($definition.Extent.Text)) }
$field=[pscustomobject]@{observation_elapsed_seconds=7199.999}
Check (-not (Test-OperatorVisualConfirmationEligible $field)) '7199.999-seconds-rejected'
$field.observation_elapsed_seconds=7200.0
Check (Test-OperatorVisualConfirmationEligible $field) '7200-seconds-accepted'
foreach ($value in @('7200',[double]::NaN,[double]::PositiveInfinity,$true)) {
    $field.observation_elapsed_seconds=$value
    Check (-not (Test-OperatorVisualConfirmationEligible $field)) ('invalid-duration-'+[string]$value)
}
$before=[ordered]@{}; $after=[ordered]@{}
foreach ($name in @(Get-ObservationFailureCounterNames)) { $before[$name]=0L; $after[$name]=0L }
$counter='source_port_bind_retry_exhaustion_count'
$delta=Get-FailureCounterDeltaReport ([pscustomobject]$before) ([pscustomobject]$after)
Check ($delta.hard_failures.Count -eq 0 -and $delta.evidence_holds.Count -eq 0) 'zero-failure-deltas'
$after[$counter]=1L
$delta=Get-FailureCounterDeltaReport ([pscustomobject]$before) ([pscustomobject]$after)
Check (@($delta.hard_failures | Where-Object { $_ -like '*bind_retry_exhaustion*' }).Count -eq 1) 'bind-retry-increase-hard-failure'
$before[$counter]=2L
$delta=Get-FailureCounterDeltaReport ([pscustomobject]$before) ([pscustomobject]$after)
Check (@($delta.evidence_holds | Where-Object { $_ -like '*bind_retry_exhaustion*' }).Count -eq 1) 'bind-retry-reset-hold'
foreach ($value in @(-1,'0',0.5,$false,$null)) {
    $after[$counter]=$value
    Reject { Get-FailureCounterDeltaReport ([pscustomobject]$before) ([pscustomobject]$after) } ('invalid-counter-'+[string]$value)
}
$after.Remove($counter)
Reject { Get-FailureCounterDeltaReport ([pscustomobject]$before) ([pscustomobject]$after) } 'missing-bind-retry-rejected'

$identity=Get-V1026CanaryPolicy
Assert-V1026CanaryPolicy $identity
$passed.Add('pending-identity-accepted')
foreach ($version in @('1.0.25','1.0.22')) {
    $bad=Get-V1026CanaryPolicy; $bad.product.version=$version
    Reject { Assert-V1026CanaryPolicy $bad } ('old-version-'+$version)
}
foreach ($value in @('false',0,1,$null,$true)) {
    $bad=Get-V1026CanaryPolicy; $bad.prerequisite_15m.full_120m_allowed=$value
    Reject { Assert-V1026CanaryPolicy $bad } ('invalid-approval-type-'+[string]$value)
}
$bad=Get-V1026CanaryPolicy; $bad.prerequisite_15m.result='PASS'
Reject { Assert-V1026CanaryPolicy $bad } 'past-pass-rejected'
$bad=Get-V1026CanaryPolicy; $bad.prerequisite_15m.evidence_files=@('past.zip')
Reject { Assert-V1026CanaryPolicy $bad } 'past-evidence-rejected'
$bad=Get-V1026CanaryPolicy; $bad.product.installer_sha256='0'*64
Reject { Assert-V1026CanaryPolicy $bad } 'wrong-installer-hash-rejected'
$bad=Get-V1026CanaryPolicy; $bad.product.build_git_commit='0'*40
Reject { Assert-V1026CanaryPolicy $bad } 'wrong-product-commit-rejected'

$source=Join-Path $testRoot 'source'; $null=[IO.Directory]::CreateDirectory($source)
FixtureText (Join-Path $source 'one.txt') 'alpha'
FixtureText (Join-Path $source 'two.txt') 'beta'
$zipPath=Join-Path $testRoot 'good.zip'; $receiptPath=Join-Path $testRoot 'good.receipt.json'
$writer=[IO.File]::Open((Join-Path $source 'one.txt'),'Open','Write','ReadWrite')
try { $zip=New-VerifiedEvidenceZip -SourceRoot $source -Destination $zipPath -ReceiptPath $receiptPath }
finally { $writer.Dispose() }
Check ($zip.entry_count -eq 2 -and [IO.File]::Exists($receiptPath)) 'shared-writer-and-reopened-zip'
Check ((Get-EvidenceFileFact $zipPath).sha256 -ceq $zip.sha256) 'final-zip-hash'
Reject { New-VerifiedEvidenceZip $source $zipPath } 'existing-zip-preserved'
Check ((Get-EvidenceFileFact $zipPath).sha256 -ceq $zip.sha256) 'existing-zip-unchanged'
Reject { New-VerifiedEvidenceZip $source (Join-Path $source 'nested.zip') } 'zip-inside-source-rejected'
Reject { New-VerifiedEvidenceZip $source (Join-Path $testRoot 'new.zip') -ReceiptPath $receiptPath } 'existing-receipt-preserved'
Reject { Test-VerifiedEvidenceZip $zipPath $zip.entries -ExpectedSha256 ('0'*64) } 'wrong-zip-hash-rejected'
$badEntries=@($zip.entries | ForEach-Object { [pscustomobject]@{name=$_.name;length=$_.length;sha256=$_.sha256} })
$badEntries[0].length++
Reject { Test-VerifiedEvidenceZip $zipPath $badEntries } 'wrong-entry-length-rejected'
$badEntries[0].length--; $badEntries[0].sha256='0'*64
Reject { Test-VerifiedEvidenceZip $zipPath $badEntries } 'wrong-entry-hash-rejected'
$variants=[ordered]@{
    missing=@([pscustomobject]@{name='one.txt';text='alpha'})
    extra=@([pscustomobject]@{name='one.txt';text='alpha'},[pscustomobject]@{name='two.txt';text='beta'},[pscustomobject]@{name='three.txt';text='extra'})
    duplicate=@([pscustomobject]@{name='one.txt';text='alpha'},[pscustomobject]@{name='one.txt';text='alpha'})
    casecollision=@([pscustomobject]@{name='one.txt';text='alpha'},[pscustomobject]@{name='ONE.txt';text='alpha'})
    traversal=@([pscustomobject]@{name='../one.txt';text='alpha'},[pscustomobject]@{name='two.txt';text='beta'})
    symlink=@([pscustomobject]@{name='one.txt';text='alpha';attributes=-1577123840},[pscustomobject]@{name='two.txt';text='beta'})
    reparse=@([pscustomobject]@{name='one.txt';text='alpha';attributes=1024},[pscustomobject]@{name='two.txt';text='beta'})
    content=@([pscustomobject]@{name='one.txt';text='wrong'},[pscustomobject]@{name='two.txt';text='beta'})
}
foreach ($variant in $variants.GetEnumerator()) {
    $path=Join-Path $testRoot ($variant.Key+'.zip')
    FixtureZip $path $variant.Value
    Reject { Test-VerifiedEvidenceZip $path $zip.entries } ('zip-'+$variant.Key+'-rejected')
}
$truncated=Join-Path $testRoot 'truncated.zip'
[IO.File]::Copy($zipPath,$truncated)
$stream=[IO.File]::Open($truncated,'Open','Write','None')
try { $stream.SetLength(10) } finally { $stream.Dispose() }
Reject { Test-VerifiedEvidenceZip $truncated $zip.entries } 'truncated-zip-rejected'
foreach ($name in @('/root','C:/root','a\b','a/../b','a//b','NUL.txt','a./b','a:ads','a<b','a>b','a"b','a|b','a?b','a*b')) {
    Reject { Assert-EvidenceEntryName $name } ('unsafe-name-'+$name)
}
# Deterministic concurrent-writer simulation inside the ZIP module: change a source on its second hash.
$zipModule=Get-Module evidence_zip_integrity
$changing=Join-Path $testRoot 'changing'; $null=[IO.Directory]::CreateDirectory($changing)
$changingFile=Join-Path $changing 'log.txt'; FixtureText $changingFile 'initial'
& $zipModule {
    param($Path)
    $script:SavedHashFunction=${function:Get-EvidenceStreamHash}
    $script:MutationTarget=$Path; $script:HashCalls=0
    function script:Get-EvidenceStreamHash {
        param([IO.Stream]$Stream)
        $script:HashCalls++
        if ($script:HashCalls -eq 2) { [IO.File]::AppendAllText($script:MutationTarget,'changed') }
        & $script:SavedHashFunction $Stream
    }
} $changingFile
$failureReceipt=Join-Path $testRoot 'changed.receipt.json'
try { Reject { New-VerifiedEvidenceZip $changing (Join-Path $testRoot 'changed.zip') -ReceiptPath $failureReceipt } 'changing-source-rejected' }
finally { Import-Module $modulePath -Force }
Check (-not [IO.File]::Exists($failureReceipt)) 'no-completion-receipt-on-failure'

$native=Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
$trustedVerifier=Join-Path $PSScriptRoot 'verify-spot-realtime-image-canary-kit.ps1'
$manifestHash=(Get-EvidenceFileFact (Join-Path $KitRoot 'canary_kit_files_sha256.json')).sha256
$checked=Native-Result $trustedVerifier @('-KitRoot',$KitRoot,'-ExpectedManifestSha256',$manifestHash)
Check ($checked.code -eq 0) 'verifier-real-kit-positive'
$checked=Native-Result $trustedVerifier @('-KitRoot',$KitRoot,'-ExpectedManifestSha256',('0'*64))
Check ($checked.code -ne 0 -and $checked.text.Contains('External kit manifest SHA256 mismatch')) 'verifier-external-hash-first'
$tampered=Join-Path $testRoot 'tampered-kit'; $null=[IO.Directory]::CreateDirectory($tampered)
foreach ($entry in @(Get-ChildItem -LiteralPath $KitRoot -File)) { [IO.File]::Copy($entry.FullName,(Join-Path $tampered $entry.Name)) }
FixtureText (Join-Path $tampered 'evidence_zip_integrity.psm1') "throw 'MODULE_IMPORT_EXECUTED'"
$checked=Native-Result $trustedVerifier @('-KitRoot',$tampered,'-ExpectedManifestSha256',$manifestHash)
Check ($checked.code -ne 0 -and $checked.text.Contains('Boot kit bytes mismatch') -and
    -not $checked.text.Contains('MODULE_IMPORT_EXECUTED')) 'tampered-module-not-imported'
$tamperedManifest=[IO.File]::ReadAllText((Join-Path $tampered 'canary_kit_files_sha256.json')) | ConvertFrom-Json
$tamperedModuleFact=Get-EvidenceFileFact (Join-Path $tampered 'evidence_zip_integrity.psm1')
foreach ($entry in $tamperedManifest) {
    if ($entry.name -ceq 'evidence_zip_integrity.psm1') { $entry.sha256=$tamperedModuleFact.sha256; $entry.length=$tamperedModuleFact.length }
}
FixtureText (Join-Path $tampered 'canary_kit_files_sha256.json') ($tamperedManifest | ConvertTo-Json -Depth 5)
$checked=Native-Result $trustedVerifier @('-KitRoot',$tampered,'-ExpectedManifestSha256',$manifestHash)
Check ($checked.code -ne 0 -and $checked.text.Contains('External kit manifest SHA256 mismatch') -and
    -not $checked.text.Contains('MODULE_IMPORT_EXECUTED')) 'rewritten-internal-manifest-rejected'
$checked=Native-Result $controllerPath @('-PreflightOnly')
Check ($checked.code -eq 3 -and $checked.text.Contains('V1026_SERVER_LAUNCH_BINDING_REQUIRED')) 'review-controller-live-entry-blocked'
$collector=Join-Path $KitRoot 'collect-spot-connecttimeout-evidence.ps1'
$collectorText=[IO.File]::ReadAllText($collector)
Check ($collectorText.Contains('V1026_SERVER_LAUNCH_BINDING_REQUIRED') -and $collectorText.Contains('New-VerifiedEvidenceZip')) 'collector-guard-and-zip-hook'
Check (-not [IO.File]::ReadAllText($controllerPath).Contains('/api/spot/live_image.jpg')) 'no-added-image-probe'
$badCollector=Join-Path $testRoot 'collector-missing-counter.ps1'
FixtureText $badCollector ($collectorText.Replace("        'source_port_bind_retry_exhaustion_count',",''))
$contract=Join-Path $KitRoot 'test-v1026-canary-observation-counter-contract.ps1'
$savedPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & $native -NoProfile -ExecutionPolicy Bypass -File $contract -ControllerPath $controllerPath -CollectorPath $badCollector 2>$null
    $rejectionExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$savedPreference }
Check ($rejectionExit -ne 0) 'missing-collector-counter-contract-rejected'
$badController=Join-Path $testRoot 'controller-old-contract.ps1'
FixtureText $badController ([IO.File]::ReadAllText($controllerPath).Replace('        "source_port_bind_retry_exhaustion_count",',''))
try {
    $ErrorActionPreference='Continue'
    & $native -NoProfile -ExecutionPolicy Bypass -File $contract -ControllerPath $badController -CollectorPath $badCollector 2>$null
    $rejectionExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$savedPreference }
Check ($rejectionExit -ne 0) 'old-12-by-32-contract-rejected'
[pscustomobject]@{result='V1026_CANARY_PORT_REGRESSION_PASS';tests_passed=$passed.Count;tests=$passed.ToArray();fixture_root=$testRoot;server_queries_performed=$false} | ConvertTo-Json -Depth 6
