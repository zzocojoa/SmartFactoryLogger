[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{64}$')][string]$ExpectedManifestSha256,
    [string]$ManifestPath = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# This verifier only reads a delivery package. It never installs, starts, stops,
# attests configuration, contacts the device, or grants observation approval.
function Require-FieldCondition {
    param([bool]$Condition,[string]$Code)
    if (-not $Condition) { throw $Code }
}
function Assert-FieldPlainPath {
    param([string]$Path)
    $node = [IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
    while ($null -ne $node) {
        $attributes = $node.Attributes
        Require-FieldCondition ([int]$attributes -eq -1 -or ($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
    }
}
function Assert-FieldEntryName {
    param([string]$Name)
    Require-FieldCondition ($Name.Length -gt 0 -and $Name.Length -le 200 -and $Name -cnotmatch '[\\:<>"|?*\x00-\x1f]' -and -not $Name.StartsWith('/')) 'unsafe-entry-name'
    foreach ($part in $Name.Split('/')) {
        Require-FieldCondition (-not [string]::IsNullOrWhiteSpace($part) -and $part -notin @('.','..') -and $part -notmatch '[. ]$' -and $part -notmatch '^(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)') 'unsafe-entry-component'
    }
}
function Get-FieldStreamHash {
    param([IO.Stream]$Stream)
    $Stream.Position = 0
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hash.ComputeHash($Stream)).Replace('-','').ToLowerInvariant() }
    finally { $hash.Dispose() }
}
function Read-FieldLockedJson {
    param([IO.Stream]$Stream)
    Require-FieldCondition ($Stream.Length -gt 0 -and $Stream.Length -le 2MB) 'json-size'
    $Stream.Position = 0
    $reader = [IO.StreamReader]::new($Stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
}
function Get-FieldNames {
    param([string]$Root)
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($Root)
    $names = [Collections.Generic.List[string]]::new()
    $seen = 0
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        Assert-FieldPlainPath $directory
        foreach ($entry in @(Get-ChildItem -LiteralPath $directory -Force)) {
            $seen++
            Require-FieldCondition ($seen -le 256) 'package-entry-budget'
            Assert-FieldPlainPath $entry.FullName
            if ($entry.PSIsContainer) { $queue.Enqueue($entry.FullName); continue }
            $name = $entry.FullName.Substring($Root.Length+1).Replace('\','/')
            Assert-FieldEntryName $name
            if ($name -cne 'package-manifest.json') { $names.Add($name) }
        }
    }
    $result = $names.ToArray()
    [Array]::Sort($result,[StringComparer]::Ordinal)
    return ,$result
}
function Assert-FieldIdentity {
    param([object]$Manifest)
    Require-FieldCondition ($Manifest.schema_version -ceq 'sfl-v1028-field-package-v1') 'package-schema'
    Require-FieldCondition ($Manifest.classification -ceq 'UNSIGNED_INTERNAL_FIELD_PREPARATION') 'package-classification'
    $expected = @(
        @('candidate','1.0.28','4cc7393e1bafbf90a329726aed9470fe0daacb21','installers/CANDIDATE_4cc7393e_UNSIGNED.exe',164618981,'8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848'),
        @('rollback','1.0.26','541d701d544eea6a8a4e4836047077eaf9cfaf30','installers/ROLLBACK_541d701_UNSIGNED.exe',163826264,'08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c')
    )
    foreach ($row in $expected) {
        $actual = $Manifest.($row[0])
        Require-FieldCondition ($actual.version -ceq $row[1] -and $actual.build_commit -ceq $row[2] -and $actual.installer_file -ceq $row[3] -and $actual.bytes -eq $row[4] -and $actual.sha256 -ceq $row[5]) ('identity-'+$row[0])
        Require-FieldCondition ($actual.bytes -is [int] -or $actual.bytes -is [long]) 'identity-size-type'
    }
    foreach ($name in @('installation_authorized','canary_authorized','promotion_authorized')) {
        Require-FieldCondition ($Manifest.$name -is [bool] -and -not $Manifest.$name) ('preparation-flag-'+$name)
    }
}
$held = [Collections.Generic.Dictionary[string,IO.FileStream]]::new([StringComparer]::Ordinal)
$manifestStream = $null
try {
    Require-FieldCondition ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'native-powershell-5.1-x64-required'
    Require-FieldCondition ([IO.Path]::IsPathRooted($PackageRoot)) 'absolute-package-root-required'
    $root = [IO.Path]::GetFullPath($PackageRoot).TrimEnd('\')
    Assert-FieldPlainPath $root
    Require-FieldCondition ([IO.Directory]::Exists($root) -and $root -cne [IO.Path]::GetPathRoot($root).TrimEnd('\')) 'package-root-invalid'
    if ([string]::IsNullOrWhiteSpace($ManifestPath)) { $ManifestPath = Join-Path $root 'package-manifest.json' }
    Assert-FieldPlainPath $ManifestPath
    $manifestStream = [IO.File]::Open($ManifestPath,'Open','Read','Read')
    $manifestHash = Get-FieldStreamHash $manifestStream
    Require-FieldCondition ($manifestHash -ceq $ExpectedManifestSha256.ToLowerInvariant()) 'external-manifest-hash'
    $manifest = Read-FieldLockedJson $manifestStream
    Assert-FieldIdentity $manifest
    Require-FieldCondition ($manifest.files -is [array] -and $manifest.files.Count -gt 2 -and $manifest.files.Count -le 128) 'manifest-file-count'
    $specs = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $manifest.files) {
        Assert-FieldEntryName $entry.name
        Require-FieldCondition (-not $specs.ContainsKey($entry.name) -and $entry.name -cne 'package-manifest.json') 'duplicate-or-self-entry'
        Require-FieldCondition (($entry.bytes -is [int] -or $entry.bytes -is [long]) -and $entry.bytes -ge 0 -and $entry.sha256 -is [string] -and $entry.sha256 -cmatch '^[a-f0-9]{64}$') 'entry-fact-type'
        $specs.Add($entry.name,$entry)
    }
    $expectedNames = [string[]]@($manifest.files.name)
    [Array]::Sort($expectedNames,[StringComparer]::Ordinal)
    $actualNames = Get-FieldNames $root
    Require-FieldCondition (($actualNames -join "`n") -ceq ($expectedNames -join "`n")) 'exact-file-set'
    foreach ($name in $expectedNames) {
        $path = Join-Path $root $name.Replace('/','\')
        Require-FieldCondition ($path.Length -le 240) 'path-budget'
        Assert-FieldPlainPath $path
        $stream = [IO.File]::Open($path,'Open','Read','Read')
        $held.Add($name,$stream)
        Require-FieldCondition ($stream.Length -eq $specs[$name].bytes) ('file-size:'+ $name)
        Require-FieldCondition ((Get-FieldStreamHash $stream) -ceq $specs[$name].sha256) ('file-hash:'+ $name)
    }
    foreach ($role in @('candidate','rollback')) {
        $identity = $manifest.$role
        $spec = $specs[$identity.installer_file]
        Require-FieldCondition ($spec.bytes -eq $identity.bytes -and $spec.sha256 -ceq $identity.sha256) ('installer-binding-'+$role)
        $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $root $identity.installer_file)
        Require-FieldCondition ([string]$signature.Status -ceq 'NotSigned') ('unsigned-state-'+$role)
    }
    $payload = Read-FieldLockedJson $held['reference/candidate-payload.json']
    Require-FieldCondition ($payload.candidate_commit -ceq $manifest.candidate.build_commit -and $payload.version -ceq $manifest.candidate.version -and $payload.installer_sha256 -ceq $manifest.candidate.sha256 -and $payload.installer_bytes -eq $manifest.candidate.bytes -and $payload.payload_file_count -eq 1814) 'payload-identity'
    foreach ($flag in @('nsis_payload_matches_unpacked_build','frontend_matches_both_payload_locations','backend_manifest_and_provenance_verified','asar_runtime_matches_git_commit')) {
        Require-FieldCondition ($payload.$flag -is [bool] -and $payload.$flag) ('payload-evidence-'+$flag)
    }
    Require-FieldCondition (@($payload.payload_files.PSObject.Properties).Count -eq 1814) 'payload-entry-count'
    $backend = Read-FieldLockedJson $held['reference/backend-verification.json']
    Require-FieldCondition ($backend.passed -is [bool] -and $backend.passed -and $backend.provenance.git_commit -ceq $manifest.candidate.build_commit -and $backend.provenance.source -ceq 'clean_git_head' -and $backend.integrity.actual_file_count -eq 1687 -and $backend.integrity.actual_bundle_sha256 -ceq '28F2D8A481A18CBD8A909AC73F52B2852E3787D01798A926EC838730D1E915B7') 'backend-provenance'
    $qa = Read-FieldLockedJson $held['qa/bundle-manifest.json']
    Require-FieldCondition ($specs['qa/bundle-manifest.json'].sha256 -ceq 'e2598e47c1f2c1e5140e07e55faca11842a082efc51ac60f34349d56c8e1ea29') 'qa-manifest-binding'
    foreach ($property in $qa.files.PSObject.Properties) {
        $name = 'qa/'+$property.Name
        Require-FieldCondition ($specs.ContainsKey($name) -and $specs[$name].bytes -eq $property.Value.bytes -and $specs[$name].sha256 -ceq $property.Value.sha256) 'qa-file-binding'
    }
    Require-FieldCondition (((Get-FieldNames $root) -join "`n") -ceq ($expectedNames -join "`n")) 'post-read-file-set'
    [ordered]@{result='FIELD_PACKAGE_BYTES_AND_IDENTITIES_VERIFIED';candidate_commit=$manifest.candidate.build_commit;
      installer_sha256=$manifest.candidate.sha256;rollback_commit=$manifest.rollback.build_commit;
      rollback_installer_sha256=$manifest.rollback.sha256;manifest_sha256=$manifestHash;files_verified=$held.Count;
      signatures='NotSigned';verification_scope='DELIVERY_PACKAGE_ONLY_NOT_INSTALLED_TREE_OR_FIELD_QA';
      installed_tree_verified=$false;installation_performed=$false;canary_started=$false;promotion_allowed=$false;
      release_gate='HOLD'} | ConvertTo-Json -Depth 4
    exit 0
} catch {
    [ordered]@{result='FIELD_PACKAGE_HOLD';reason=$_.Exception.Message;installation_performed=$false;
      canary_started=$false;promotion_allowed=$false} | ConvertTo-Json -Compress
    exit 1
} finally {
    foreach ($stream in $held.Values) { $stream.Dispose() }
    if ($null -ne $manifestStream) { $manifestStream.Dispose() }
}
