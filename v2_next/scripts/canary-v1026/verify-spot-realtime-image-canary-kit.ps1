[CmdletBinding()]
param(
    [string]$KitRoot=$PSScriptRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedManifestSha256,
    [switch]$Quiet
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedNames = @(
    'README.md','analyze-spot-http-framing.ps1','backend_bundle_integrity.psm1',
    'canary_kit_files_sha256.json','canary_kit_identity.json','collect-spot-connecttimeout-evidence.ps1',
    'collect_operational_observability.ps1','evidence_zip_integrity.psm1',
    'invoke-spot-realtime-image-canary-120m.ps1','monitor-spot-connecttimeout-trigger.ps1',
    'operator_attestation_15m.json','release-pins.json',
    'test-v1026-canary-observation-counter-contract.ps1',
    'v1026_release_identity_integrity.psm1','verify-spot-realtime-image-canary-kit.ps1'
) | Sort-Object
function Boot-PlainPath {
    param([string]$Path)
    $node=[IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
    while ($null -ne $node) {
        $attributes=$node.Attributes
        if ([int]$attributes -ne -1 -and ($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse path rejected before code import.' }
        if ($node -is [IO.FileInfo]) { $node=$node.Directory } else { $node=$node.Parent }
    }
}
function Boot-Hash {
    param([IO.Stream]$Stream)
    $sha=[Security.Cryptography.SHA256]::Create()
    try { $Stream.Position=0; return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','') }
    finally { $sha.Dispose() }
}
$held=[Collections.Generic.List[IO.FileStream]]::new()
try {
    # Never import adjacent code before external manifest binding and byte verification.
    Boot-PlainPath $KitRoot
    $manifestPath=Join-Path $KitRoot 'canary_kit_files_sha256.json'
    Boot-PlainPath $manifestPath
    $pin=[IO.File]::Open($manifestPath,'Open','Read','Read'); $held.Add($pin)
    if ((Boot-Hash $pin) -cne $ExpectedManifestSha256) { throw 'External kit manifest SHA256 mismatch.' }
    $bootManifest=[IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json
    $bootNames=@($bootManifest.name | Sort-Object)
    $want=@($expectedNames | Where-Object { $_ -cne 'canary_kit_files_sha256.json' })
    if (($bootNames -join '|') -cne ($want -join '|')) { throw 'Boot manifest exact membership mismatch.' }
    $items=@(Get-ChildItem -LiteralPath $KitRoot -Force)
    if (@($items | Where-Object { $_.PSIsContainer }).Count -gt 0 -or
        (@($items.Name | Sort-Object) -join '|') -cne ($expectedNames -join '|')) { throw 'Boot kit exact membership mismatch.' }
    foreach ($entry in $bootManifest) {
        $path=Join-Path $KitRoot $entry.name
        Boot-PlainPath $path
        $pin=[IO.File]::Open($path,'Open','Read','Read'); $held.Add($pin)
        if (($entry.length -isnot [int] -and $entry.length -isnot [long]) -or
            $entry.length -lt 0 -or $pin.Length -ne $entry.length -or
            $entry.sha256 -isnot [string] -or (Boot-Hash $pin) -cne $entry.sha256) { throw 'Boot kit bytes mismatch.' }
    }
    Import-Module (Join-Path $KitRoot 'evidence_zip_integrity.psm1') -Force
    Import-Module (Join-Path $KitRoot 'v1026_release_identity_integrity.psm1') -Force
$actual = @(Get-EvidenceFileNames $KitRoot | ForEach-Object { $_ } | Sort-Object)
if (($actual -join '|') -cne ($expectedNames -join '|')) { throw 'Unexpected kit file set.' }
$manifest = [IO.File]::ReadAllText((Join-Path $KitRoot 'canary_kit_files_sha256.json')) | ConvertFrom-Json
$manifestNames = @($manifest.name | Sort-Object)
$wantNames = @($expectedNames | Where-Object { $_ -cne 'canary_kit_files_sha256.json' })
if (($manifestNames -join '|') -cne ($wantNames -join '|')) { throw 'Invalid kit manifest membership.' }
foreach ($entry in $manifest) {
    Assert-EvidenceEntryName $entry.name
    $fact = Get-EvidenceFileFact (Join-Path $KitRoot $entry.name)
    if (($entry.length -isnot [long] -and $entry.length -isnot [int]) -or
        $fact.length -ne $entry.length -or $fact.sha256 -cne $entry.sha256) { throw ('Kit hash/length mismatch: '+$entry.name) }
}
$identity = [IO.File]::ReadAllText((Join-Path $KitRoot 'canary_kit_identity.json')) | ConvertFrom-Json
Assert-V1026CanaryPolicy $identity
$attestation = [IO.File]::ReadAllText((Join-Path $KitRoot 'operator_attestation_15m.json')) | ConvertFrom-Json
if ($attestation.schema_version -cne 'spot-operator-visual-attestation-v1' -or
    $attestation.status -cne 'PENDING' -or $attestation.product_version -cne '1.0.26' -or
    $attestation.build_git_commit -cne 'd7a1b20f96711fb07fc7add0867e79ee36506fce' -or
    $attestation.evidence_kind -cne 'pending-server-validation') { throw 'Past/invalid attestation rejected.' }
foreach ($name in @('observation_recorded','continuous_spot_image_refresh_confirmed','no_new_app_error_confirmed')) {
    $p=$attestation.PSObject.Properties[$name]
    if ($null -eq $p -or $p.Value -isnot [bool] -or $p.Value) { throw 'Attestation must remain unobserved.' }
}
if ($attestation.machine_generated -isnot [bool] -or -not $attestation.machine_generated) { throw 'Placeholder is not human evidence.' }
$native = Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
& $native -NoProfile -ExecutionPolicy Bypass -File (Join-Path $KitRoot 'test-v1026-canary-observation-counter-contract.ps1') `
    -ControllerPath (Join-Path $KitRoot 'invoke-spot-realtime-image-canary-120m.ps1') `
    -CollectorPath (Join-Path $KitRoot 'collect-spot-connecttimeout-evidence.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Counter contract failed.' }
if (-not $Quiet) {
    [pscustomobject]@{result='V1026_PENDING_CANARY_KIT_INTEGRITY_PASS'; files=$actual.Count;
        external_manifest_binding_verified=$true; product_commit=$identity.product.build_git_commit; prerequisite_15m='PENDING_SERVER_VALIDATION';
        full_120m_allowed=$false; server_execution_authorized=$false; production_promotion_allowed=$false}
}
} finally { foreach ($pin in $held) { $pin.Dispose() } }
