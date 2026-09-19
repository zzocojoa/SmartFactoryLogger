[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ReleaseRoot,[Parameter(Mandatory=$true)][string]$CanaryBuildResult,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedCanaryBuildResultSha256,
    [Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess) { throw 'Use native x64 PS 5.1.' }
$canarySource=Join-Path (Split-Path -Parent $PSScriptRoot) 'canary-v1026'
Import-Module (Join-Path $canarySource 'evidence_zip_integrity.psm1') -Force
Import-Module (Join-Path $canarySource 'v1026_release_identity_integrity.psm1') -Force
. (Join-Path $PSScriptRoot 'stage-functions.ps1')
$master='c03f7c76ff6e75bfe330275ac0fa01326f357261'
if ((& git -C $PSScriptRoot rev-parse HEAD).Trim() -cne $master) { throw 'Tooling HEAD differs.' }
& git -C $PSScriptRoot diff --exit-code $master -- $canarySource
if ($LASTEXITCODE -ne 0) { throw 'Committed Canary source changed.' }
$sourceStatus=(& git -C $PSScriptRoot status --porcelain --untracked-files=all -- $canarySource | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceStatus -ne '') { throw 'Canary source must be clean, including untracked files.' }
$candidate=Test-V1026ReleaseCandidate $ReleaseRoot
Assert-EvidencePlainPath $CanaryBuildResult
$buildPin=[IO.File]::Open($CanaryBuildResult,'Open','Read','Read')
try {
    if ((Get-EvidenceStreamHash $buildPin) -cne $ExpectedCanaryBuildResultSha256) { throw 'Canary build receipt differs from externally recorded SHA256.' }
    $buildPin.Position=0
    $reader=[IO.StreamReader]::new($buildPin,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try { $canary=ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
} finally { $buildPin.Dispose() }
if ($canary.result -cne 'V1026_CANARY_PORT_OFFLINE_VERIFIED' -or $canary.tooling_parent_commit -cne $master -or
    $canary.port_regression.tests_passed -ne 71 -or -not $canary.loopback_integration_passed -or
    $canary.server_execution_authorized -or $canary.observation_started -or $canary.full_120m_allowed) { throw 'Fresh master-bound offline kit evidence required.' }
$currentSourceNames=Get-EvidenceFileNames $canarySource
if ((@($currentSourceNames | Sort-Object) -join '|') -cne (@($canary.tooling_source_snapshot.entries.name | Sort-Object) -join '|')) { throw 'Canary source snapshot membership differs.' }
foreach ($e in $canary.tooling_source_snapshot.entries) {
    $f=Get-EvidenceFileFact (Join-Path $canarySource $e.name)
    if ($f.sha256 -cne $e.sha256 -or $f.length -ne $e.length) { throw 'Canary source snapshot differs.' }
}
$null=Test-VerifiedEvidenceZip -Path $canary.archive.path -Entries @($canary.archive.entries) -ExpectedSha256 $canary.archive.sha256
if (Test-Path -LiteralPath $OutputRoot) { throw 'Existing build output preserved; choose a new path.' }
Assert-EvidencePlainPath $OutputRoot
$output=[IO.Path]::GetFullPath($OutputRoot)
$null=[IO.Directory]::CreateDirectory($output)
$payload=Join-Path $output 'transfer-files'; $null=[IO.Directory]::CreateDirectory($payload)
foreach ($item in @(@('release',[IO.Path]::GetFullPath($ReleaseRoot)),@('kit',$canary.kit_root))) {
    $dir=Join-Path $payload $item[0]; $null=[IO.Directory]::CreateDirectory($dir)
    $specs=$(if ($item[0] -ceq 'release') { (Get-V1026ReleasePins).files } else { $canary.archive.entries })
    foreach ($e in $specs) {
        $source=Join-Path $item[1] $e.name; Assert-EvidencePlainPath $source
        $pin=[IO.File]::Open($source,'Open','Read','Read')
        try {
            if ($pin.Length -ne $e.length -or (Get-EvidenceStreamHash $pin) -cne $e.sha256) { throw 'Source bytes changed.' }
            $pin.Position=0; $dest=Join-Path $dir $e.name
            $writer=[IO.File]::Open($dest,'CreateNew','Write','None')
            try { $pin.CopyTo($writer); $writer.Flush($true) } finally { $writer.Dispose() }
            if ((Get-EvidenceFileFact $dest).sha256 -cne $e.sha256) { throw 'Copied payload differs.' }
        } finally { $pin.Dispose() }
    }
}
# Embed only the reviewed integrity functions needed on the server; no adjacent code import from Desktop.
$tokens=$null; $parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $canarySource 'evidence_zip_integrity.psm1'),[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Integrity source parse failed.' }
$required=@('Assert-EvidencePlainPath','Assert-EvidenceEntryName','Get-EvidenceStreamHash','Get-EvidenceFileFact','Get-EvidenceFileNames','Test-VerifiedEvidenceZip','Write-EvidenceJsonNew')
$functions=@($ast.FindAll({param($a) $a -is [Management.Automation.Language.FunctionDefinitionAst]},$false) | Where-Object Name -In $required)
if ($functions.Count -ne $required.Count) { throw 'Integrity function set differs.' }
$embedded="Add-Type -AssemblyName System.IO.Compression`n"+(@($functions | ForEach-Object { $_.Extent.Text }) -join "`n")
$template=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'server-stage.ps1'))
foreach ($marker in @('# @INTEGRITY_FUNCTIONS@','# @STAGE_FUNCTIONS@')) {
    if ([regex]::Matches($template,[regex]::Escape($marker)).Count -ne 1) { throw 'Helper assembly marker differs.' }
}
$helper=$template.Replace('# @INTEGRITY_FUNCTIONS@',$embedded).Replace('# @STAGE_FUNCTIONS@',[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'stage-functions.ps1')))
$helperPath=Join-Path $payload 'server-stage.ps1'
Write-StageBytesNew $helperPath ([Text.UTF8Encoding]::new($false).GetBytes($helper))
Write-StageBytesNew (Join-Path $payload 'SERVER_GUIDE.md') ([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'SERVER_GUIDE.md')))
$helperFact=Get-EvidenceFileFact $helperPath
$entries=@(foreach ($name in (Get-EvidenceFileNames $payload)) {
    $f=Get-EvidenceFileFact (Join-Path $payload $name)
    [pscustomobject]@{name=$name;length=$f.length;sha256=$f.sha256}
})
$manifest=[ordered]@{schema_version='v1026-static-stage-transfer-v1';recorded_at=[DateTimeOffset]::Now.ToString('o');
    classification='UNSIGNED_INTERNAL_DEVELOPMENT_STATIC_STAGE_ONLY';product_commit=$candidate.product_commit;tooling_commit=$master;
    helper_status='HASH_BOUND_LOCAL_PREPARATION_NOT_COMMITTED';files=$entries;
    installation_authorized=$false;observation_authorized=$false;production_promotion_allowed=$false}
Assert-StageContract ([pscustomobject]$manifest)
$manifestFact=Write-EvidenceJsonNew (Join-Path $payload 'transfer-manifest.json') $manifest
$zipName='v1026-server-stage-ready-'+[DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'.zip'
$zip=New-VerifiedEvidenceZip -SourceRoot $payload -Destination (Join-Path $output $zipName)
if ($zip.entry_count -ne 32) { throw 'Final ZIP requires 32 files.' }
$launcher=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'launch-template.ps1'))
$replacements=@{'@ZIP_NAME@'=$zipName;'@ZIP_HASH@'=$zip.sha256;'@ZIP_LENGTH@'=[string]$zip.length;
    '@HELPER_HASH@'=$helperFact.sha256;'@HELPER_LENGTH@'=[string]$helperFact.length;'@MANIFEST_HASH@'=$manifestFact.sha256}
foreach ($r in $replacements.GetEnumerator()) {
    if (-not $launcher.Contains($r.Key)) { throw 'Launcher assembly marker missing.' }
    $launcher=$launcher.Replace($r.Key,$r.Value)
}
foreach ($sourceCode in @($helper,$launcher)) {
    $tokens=$null; $parseErrors=$null
    $null=[Management.Automation.Language.Parser]::ParseInput($sourceCode,[ref]$tokens,[ref]$parseErrors)
    if ($parseErrors.Count -gt 0) { throw ('Assembled script parse failed: '+($parseErrors.Message -join '; ')) }
}
Write-StageBytesNew (Join-Path $output 'START_V1026_STAGE.txt') ([Text.UTF8Encoding]::new($false).GetBytes($launcher))
$null=Test-VerifiedEvidenceZip -Path $zip.path -Entries @($zip.entries) -ExpectedSha256 $zip.sha256
Write-StageBytesNew ($zip.path+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($zip.sha256+"`n"))
Write-EvidenceJsonNew (Join-Path $output 'build-result.json') ([ordered]@{
    result='V1026_SERVER_STAGE_TRANSFER_BUILT_NOT_SERVER_TESTED';recorded_at=[DateTimeOffset]::Now.ToString('o');archive=$zip;
    helper=$helperFact;manifest=$manifestFact;canary_build_result=[IO.Path]::GetFullPath($CanaryBuildResult);canary_build_result_sha256=$ExpectedCanaryBuildResultSha256;
    tooling_commit=$master;product_commit=$candidate.product_commit;helper_committed=$false;
    server_staging_executed=$false;server_installation_authorized=$false;observation_started=$false;production_promotion_allowed=$false
}) | Out-Null
Write-Host ('[TRANSFER] '+$zip.path)
Write-Host ('[SHA256] '+$zip.sha256)
