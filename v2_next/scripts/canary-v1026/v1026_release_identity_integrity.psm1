Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'evidence_zip_integrity.psm1')

function Get-V1026ReleasePins {
    $path = Join-Path $PSScriptRoot 'release-pins.json'
    Assert-EvidencePlainPath $path
    $bytes=[IO.File]::ReadAllBytes($path)
    $sha=[Security.Cryptography.SHA256]::Create()
    try { $hash=[BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','') }
    finally { $sha.Dispose() }
    if ($hash -cne '8DFC39B6C268E58331A1E0C5C6EB17D6B225564A9E14E84699BF31CA5E7D61BE') {
        throw 'v1026 release pins differ from the externally reviewed source contract.'
    }
    return [Text.UTF8Encoding]::new($false,$true).GetString($bytes) | ConvertFrom-Json
}

function Assert-V1026ReleaseClaims {
    param([Parameter(Mandatory=$true)][object]$Identity)
    $claims = [ordered]@{
        schema_version='sfl-v1026-internal-installer-review-v1'
        result='INSTALLER_VERIFIED_CANARY_PENDING_NOT_INSTALL_READY'
        product_version='1.0.26'
        product_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce'
        source_tree='d4c6af2dc72f7d7711ecfd4a8e3bbce217a0649a'
        classification='UNSIGNED_INTERNAL_DEVELOPMENT_CANDIDATE'
        installer_file='smart-factory-logger-v2 Setup 1.0.26.exe'
        installed_payload_tree_sha256='0C18CE2E9F810A8636DA007BE00F02ADD5AEB7869E693E4827774B0E3C53F908'
        electron_version='44.3.0'; architecture='x64'
    }
    foreach ($item in $claims.GetEnumerator()) {
        $property = $Identity.PSObject.Properties[$item.Key]
        if ($null -eq $property -or $property.Value -isnot [string] -or $property.Value -cne $item.Value) {
            throw ('v1026 release claim mismatch: '+$item.Key)
        }
    }
    foreach ($name in @('migration_performed','server_installation_authorized','server_installation_performed',
        'observation_started','full_120m_allowed','production_promotion_allowed')) {
        $property = $Identity.PSObject.Properties[$name]
        if ($null -eq $property -or $property.Value -isnot [bool] -or $property.Value) {
            throw ('v1026 release flag must remain false: '+$name)
        }
    }
}

function Test-V1026ReleaseCandidate {
    param([Parameter(Mandatory=$true)][string]$ReleaseKitRoot)
    $pins = Get-V1026ReleasePins
    $expectedNames = @($pins.files.name | Sort-Object)
    $actualNames = @(Get-EvidenceFileNames $ReleaseKitRoot | ForEach-Object { $_ } | Sort-Object)
    if (($expectedNames -join "`n") -cne ($actualNames -join "`n")) { throw 'Release candidate exact file set differs.' }
    $held = [Collections.Generic.List[IO.FileStream]]::new()
    try {
        foreach ($entry in $pins.files) {
            $path = Join-Path $ReleaseKitRoot $entry.name
            Assert-EvidencePlainPath $path
            $stream = [IO.File]::Open($path,'Open','Read','Read')
            $held.Add($stream)
            if ($stream.Length -ne $entry.length -or (Get-EvidenceStreamHash $stream) -cne $entry.sha256) {
                throw ('Release candidate file mismatch: '+$entry.name)
            }
        }
        $identity = [IO.File]::ReadAllText((Join-Path $ReleaseKitRoot 'release_identity.json')) | ConvertFrom-Json
        Assert-V1026ReleaseClaims $identity
        $provenance = [IO.File]::ReadAllText((Join-Path $ReleaseKitRoot 'backend-build-provenance.json')) | ConvertFrom-Json
        if ($provenance.git_commit -cne $pins.product_commit -or $provenance.source -cne 'clean_git_head') { throw 'Backend provenance mismatch.' }
        return [pscustomobject]@{
            result='V1026_RELEASE_CANDIDATE_IDENTITY_PASS'; product_version=$pins.product_version
            product_commit=$pins.product_commit; release_kit_folder=(Split-Path -Leaf $ReleaseKitRoot)
            release_identity_sha256=$pins.release_identity_sha256; installer_sha256=$pins.installer_sha256
            app_asar_sha256=$pins.app_asar_sha256; backend_bundle_sha256=$pins.backend_bundle_sha256
            backend_bundle_file_count=$pins.backend_bundle_file_count
            rollback_version=$pins.rollback_version; rollback_commit=$pins.rollback_commit
            rollback_installer_sha256=$pins.rollback_installer_sha256
            rollback_operational_suitability=$pins.rollback_operational_suitability
            installation_authorized=$false; full_120m_allowed=$false
        }
    } finally { foreach ($stream in $held) { $stream.Dispose() } }
}

function Get-V1026CanaryPolicy {
    $pins = Get-V1026ReleasePins
    return [pscustomobject][ordered]@{
        schema_version='spot-realtime-image-v1026-canary-kit-v1'
        classification='UNSIGNED_INTERNAL_DEVELOPMENT_CANARY_REVIEW_ONLY'
        product=[pscustomobject]@{
            version=$pins.product_version; build_git_commit=$pins.product_commit
            release_identity_sha256=$pins.release_identity_sha256; installer_sha256=$pins.installer_sha256
            app_asar_sha256=$pins.app_asar_sha256; backend_bundle_sha256=$pins.backend_bundle_sha256
            backend_bundle_file_count=$pins.backend_bundle_file_count
            installed_payload_file_count=$pins.installed_payload_file_count
            installed_payload_tree_sha256=$pins.installed_payload_tree_sha256
        }
        rollback=[pscustomobject]@{
            version=$pins.rollback_version; build_git_commit=$pins.rollback_commit
            installer_sha256=$pins.rollback_installer_sha256
            operational_suitability=$pins.rollback_operational_suitability; automatic_rollback_allowed=$false
        }
        prerequisite_15m=[pscustomobject]@{
            result='PENDING_SERVER_VALIDATION'; full_120m_allowed=$false; evidence_files=@()
            operator_attestation_file='operator_attestation_15m.json'
        }
        canary=[pscustomobject]@{
            minimum_15m_seconds=900; minimum_120m_seconds=7200
            required_observation_failure_counter_count=13; collected_image_counter_count=33
            historical_failure_counter_count=14; bind_retry_exhaustion_is_hard_gate=$true
            monitor_detection_threshold_ms=5000; parent_stop_signal_max_delay_seconds=5
            source_port_minimum_reuse_seconds=75; source_port_quarantine_seconds=77
            source_port_policy_version='spot-source-port-quarantine-v3'
            request_budget_max_per_second=6.0; progress_interval_seconds=30
            progress_source='local-clock-and-process-state-only'; progress_adds_spot_requests=$false
            final_zip_policy='create-new-shared-read-rehash-reopen-exact-entries-external-receipt-v1'
        }
        tooling_status='HASH_BOUND_LOCAL_SOURCE_NOT_COMMITTED'
        server_context_bound=$false; server_execution_authorized=$false
        observation_started=$false; past_attestation_reused=$false; production_promotion_allowed=$false
    }
}

function Assert-V1026CanaryPolicy {
    param([Parameter(Mandatory=$true)][object]$Identity)
    # The identity is an exact policy object, not a bag of truthy approval flags.
    $expected = Get-V1026CanaryPolicy
    function Compare-PolicyNode {
        param([AllowNull()][object]$Actual,[AllowNull()][object]$Expected,[string]$Context)
        if ($null -eq $Expected) { if ($null -ne $Actual) { throw "Unexpected value: $Context" }; return }
        if ($null -eq $Actual) { throw "Missing policy value: $Context" }
        if ($Expected -is [pscustomobject]) {
            $want = @($Expected.PSObject.Properties.Name | Sort-Object)
            $have = @($Actual.PSObject.Properties.Name | Sort-Object)
            if (($want -join '|') -cne ($have -join '|')) { throw "Policy properties differ: $Context" }
            foreach ($name in $want) { Compare-PolicyNode $Actual.$name $Expected.$name ($Context+'.'+$name) }
        } elseif ($Expected -is [array]) {
            if ($Actual -isnot [array] -or $Actual.Count -ne $Expected.Count) { throw "Policy array differs: $Context" }
            for ($i=0;$i -lt $Expected.Count;$i++) { Compare-PolicyNode $Actual[$i] $Expected[$i] ($Context+'['+$i+']') }
        } elseif ($Expected -is [bool]) {
            if ($Actual -isnot [bool] -or $Actual -ne $Expected) { throw "Policy boolean differs: $Context" }
        } elseif ($Expected -is [string]) {
            if ($Actual -isnot [string] -or $Actual -cne $Expected) { throw "Policy string differs: $Context" }
        } else {
            if (($Actual -isnot [int] -and $Actual -isnot [long] -and $Actual -isnot [double] -and $Actual -isnot [decimal]) -or
                [double]::IsNaN($Actual) -or [double]::IsInfinity($Actual) -or $Actual -ne $Expected) { throw "Policy number differs: $Context" }
        }
    }
    Compare-PolicyNode $Identity $expected 'canary'
}

Export-ModuleMember -Function Get-V1026ReleasePins,Assert-V1026ReleaseClaims,Test-V1026ReleaseCandidate,Get-V1026CanaryPolicy,Assert-V1026CanaryPolicy
