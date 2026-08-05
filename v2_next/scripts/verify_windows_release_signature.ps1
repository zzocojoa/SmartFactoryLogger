[CmdletBinding(DefaultParameterSetName = "Verify")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$InstallerPath,

    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$AppExecutablePath,

    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$BundleManifestPath,

    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$BuildProvenancePath,

    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$ExpectedBuildCommit,

    [Parameter(Mandatory = $true, ParameterSetName = "Verify")]
    [string]$ExpectedSignerSHA1,

    [Parameter(ParameterSetName = "Verify")]
    [string]$EvidencePath = "",

    [Parameter(Mandatory = $true, ParameterSetName = "SelfTest")]
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Import-Module `
    (Join-Path $PSScriptRoot "backend_bundle_integrity.psm1") `
    -Force `
    -ErrorAction Stop

function ConvertTo-NormalizedSHA1 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = ($Value -replace "\s", "").ToUpperInvariant()
    if ($normalized -cnotmatch "^[0-9A-F]{40}$") {
        throw "Expected signer SHA-1 must contain exactly 40 hexadecimal characters."
    }

    return $normalized
}

function Get-PropertyValue {
    param(
        [AllowNull()]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name,

        [AllowNull()]
        [object]$Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

function Get-AuthenticodeCheckResult {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Signature,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedSigner
    )

    $signer = Get-PropertyValue -InputObject $Signature -Name "SignerCertificate"
    $timestamp = Get-PropertyValue -InputObject $Signature -Name "TimeStamperCertificate"
    $status = [string](
        Get-PropertyValue -InputObject $Signature -Name "Status" -Default ""
    )
    $actualSigner = [string](
        Get-PropertyValue -InputObject $signer -Name "Thumbprint" -Default ""
    )
    $actualSigner = ($actualSigner -replace "\s", "").ToUpperInvariant()

    return [pscustomobject]@{
        Status                      = $status
        SignerSubject               = [string](
            Get-PropertyValue -InputObject $signer -Name "Subject" -Default ""
        )
        SignerSHA1                  = $actualSigner
        TimestampSubject            = [string](
            Get-PropertyValue -InputObject $timestamp -Name "Subject" -Default ""
        )
        SignatureValid              = $status -ceq "Valid"
        SignerCertificatePresent    = $null -ne $signer
        SignerSHA1Match             = $actualSigner -ceq $ExpectedSigner
        TimestampCertificatePresent = $null -ne $timestamp
    }
}

function Invoke-WindowsReleaseVerification {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Installer,

        [Parameter(Mandatory = $true)]
        [string]$Application,

        [Parameter(Mandatory = $true)]
        [string]$Manifest,

        [Parameter(Mandatory = $true)]
        [string]$Provenance,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedCommit,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedSigner,

        [Parameter(Mandatory = $true)]
        [scriptblock]$SignatureProvider,

        [string]$OutputEvidencePath = ""
    )

    $normalizedCommit = $ExpectedCommit.Trim().ToLowerInvariant()
    if ($normalizedCommit -cnotmatch "^[0-9a-f]{40}$") {
        throw "Expected build commit must be a 40-character lowercase Git SHA."
    }
    $normalizedSigner = ConvertTo-NormalizedSHA1 $ExpectedSigner

    $requiredFiles = [ordered]@{
        Installer = $Installer
        Application = $Application
        BundleManifest = $Manifest
        BuildProvenance = $Provenance
    }
    foreach ($item in $requiredFiles.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $item.Value -PathType Leaf)) {
            throw "$($item.Key) file was not found: $($item.Value)"
        }
    }

    $manifestObject = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
    $provenanceObject = Get-Content -LiteralPath $Provenance -Raw | ConvertFrom-Json
    $manifestCommit = [string](
        Get-PropertyValue -InputObject $manifestObject -Name "build_git_commit" -Default ""
    )
    $provenanceCommit = [string](
        Get-PropertyValue -InputObject $provenanceObject -Name "git_commit" -Default ""
    )

    $applicationFullPath = (Get-Item -LiteralPath $Application).FullName
    $applicationRoot = Split-Path -Parent $applicationFullPath
    $expectedManifestPath = [IO.Path]::GetFullPath(
        (Join-Path $applicationRoot "resources\backend\bundle-manifest.json")
    )
    $expectedProvenancePath = [IO.Path]::GetFullPath(
        (
            Join-Path `
                $applicationRoot `
                "resources\backend\_internal\backend\build_provenance.json"
        )
    )
    $manifestFullPath = (Get-Item -LiteralPath $Manifest).FullName
    $provenanceFullPath = (Get-Item -LiteralPath $Provenance).FullName
    $backendRoot = Split-Path -Parent $manifestFullPath
    $bundleIntegrity = Test-BackendBundleIntegrity -BackendRoot $backendRoot

    $installerSignature = & $SignatureProvider $Installer
    $applicationSignature = & $SignatureProvider $Application
    $installerResult = Get-AuthenticodeCheckResult `
        -Signature $installerSignature `
        -ExpectedSigner $normalizedSigner
    $applicationResult = Get-AuthenticodeCheckResult `
        -Signature $applicationSignature `
        -ExpectedSigner $normalizedSigner

    $checks = [ordered]@{
        ExtractedPayloadLayoutMatch = (
            $manifestFullPath -ceq $expectedManifestPath -and
            $provenanceFullPath -ceq $expectedProvenancePath
        )
        BackendBundleIntegrityVerified = [bool]$bundleIntegrity.ok
        ManifestCommitMatch = $manifestCommit -ceq $normalizedCommit
        ProvenanceCommitMatch = $provenanceCommit -ceq $normalizedCommit
        InstallerSignatureValid = $installerResult.SignatureValid
        InstallerSignerPresent = $installerResult.SignerCertificatePresent
        InstallerSignerMatch = $installerResult.SignerSHA1Match
        InstallerTimestampPresent = $installerResult.TimestampCertificatePresent
        ApplicationSignatureValid = $applicationResult.SignatureValid
        ApplicationSignerPresent = $applicationResult.SignerCertificatePresent
        ApplicationSignerMatch = $applicationResult.SignerSHA1Match
        ApplicationTimestampPresent = $applicationResult.TimestampCertificatePresent
    }
    $failedChecks = @(
        $checks.GetEnumerator() |
            Where-Object { -not [bool]$_.Value } |
            ForEach-Object { $_.Key }
    )

    $evidence = [ordered]@{
        schema_version = 2
        captured_at_utc = [datetime]::UtcNow.ToString("o")
        expected_build_commit = $normalizedCommit
        expected_signer_sha1 = $normalizedSigner
        manifest_build_commit = $manifestCommit
        provenance_build_commit = $provenanceCommit
        bundle_manifest = [ordered]@{
            file_name = [IO.Path]::GetFileName($Manifest)
            sha256 = (Get-FileHash -LiteralPath $Manifest -Algorithm SHA256).Hash
            schema_version = $bundleIntegrity.schema_version
            packaging_mode = $bundleIntegrity.packaging_mode
            expected_bundle_sha256 = $bundleIntegrity.expected_bundle_sha256
            actual_bundle_sha256 = $bundleIntegrity.actual_bundle_sha256
            expected_file_count = $bundleIntegrity.expected_file_count
            actual_file_count = $bundleIntegrity.actual_file_count
            verified_file_count = $bundleIntegrity.verified_file_count
            missing_files = @($bundleIntegrity.missing_files)
            unexpected_files = @($bundleIntegrity.unexpected_files)
            mismatch_files = @($bundleIntegrity.mismatch_files)
            invalid_paths = @($bundleIntegrity.invalid_paths)
            errors = @($bundleIntegrity.errors)
        }
        build_provenance = [ordered]@{
            file_name = [IO.Path]::GetFileName($Provenance)
            sha256 = (Get-FileHash -LiteralPath $Provenance -Algorithm SHA256).Hash
        }
        installer = [ordered]@{
            file_name = [IO.Path]::GetFileName($Installer)
            length = (Get-Item -LiteralPath $Installer).Length
            sha256 = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash
            status = $installerResult.Status
            signer_subject = $installerResult.SignerSubject
            signer_sha1 = $installerResult.SignerSHA1
            timestamp_subject = $installerResult.TimestampSubject
        }
        application = [ordered]@{
            file_name = [IO.Path]::GetFileName($Application)
            length = (Get-Item -LiteralPath $Application).Length
            sha256 = (Get-FileHash -LiteralPath $Application -Algorithm SHA256).Hash
            status = $applicationResult.Status
            signer_subject = $applicationResult.SignerSubject
            signer_sha1 = $applicationResult.SignerSHA1
            timestamp_subject = $applicationResult.TimestampSubject
        }
        checks = $checks
        passed = $failedChecks.Count -eq 0
        failed_checks = $failedChecks
    }

    if (-not [string]::IsNullOrWhiteSpace($OutputEvidencePath)) {
        $evidenceDirectory = Split-Path -Parent $OutputEvidencePath
        if (
            -not [string]::IsNullOrWhiteSpace($evidenceDirectory) -and
            -not (Test-Path -LiteralPath $evidenceDirectory -PathType Container)
        ) {
            New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
        }

        $evidence | ConvertTo-Json -Depth 8 |
            Set-Content -LiteralPath $OutputEvidencePath -Encoding UTF8
    }

    return [pscustomobject]@{
        Evidence = $evidence
        FailedChecks = $failedChecks
    }
}

function Assert-SelfTest {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw "Self-test failed: $Message"
    }
}

function Assert-WindowsReleaseVerification {
    param(
        [Parameter(Mandatory = $true)]
        [object]$VerificationResult
    )

    if ($VerificationResult.FailedChecks.Count -ne 0) {
        throw (
            "Windows release signature verification failed: " +
            ($VerificationResult.FailedChecks -join ", ")
        )
    }
}

function Write-SelfTestBackendBundleManifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BackendRoot,

        [Parameter(Mandatory = $true)]
        [string]$BuildCommit
    )

    $root = (Get-Item -LiteralPath $BackendRoot).FullName.TrimEnd("\")
    $rootPrefix = $root + "\"
    $manifestPath = Join-Path $root "bundle-manifest.json"
    $relativePaths = [string[]]@(
        Get-ChildItem -LiteralPath $root -Recurse -File |
            Where-Object { $_.FullName -ne $manifestPath } |
            ForEach-Object {
                $_.FullName.Substring($rootPrefix.Length).Replace("\", "/")
            }
    )
    [Array]::Sort($relativePaths, [StringComparer]::Ordinal)

    $entries = New-Object System.Collections.Generic.List[object]
    $aggregateLines = New-Object System.Collections.Generic.List[string]
    foreach ($relativePath in $relativePaths) {
        $path = Join-Path $root $relativePath.Replace("/", "\")
        $file = Get-Item -LiteralPath $path
        $sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        [void]$entries.Add([ordered]@{
            path = $relativePath
            length = [int64]$file.Length
            sha256 = $sha256
        })
        [void]$aggregateLines.Add("$relativePath`t$($file.Length)`t$sha256")
    }
    $aggregatePayload = ($aggregateLines.ToArray() -join "`n") + "`n"
    [ordered]@{
        schema_version = "smartfactory-backend-bundle-v1"
        packaging_mode = "onedir"
        build_git_commit = $BuildCommit
        file_count = $entries.Count
        bundle_sha256 = Get-Utf8Sha256 -Text $aggregatePayload
        files = $entries.ToArray()
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}

function Invoke-SelfTest {
    $expected = "00112233445566778899AABBCCDDEEFF00112233"
    $commit = "0123456789abcdef0123456789abcdef01234567"
    Assert-SelfTest `
        -Condition (
            (ConvertTo-NormalizedSHA1 "00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff 00 11 22 33") `
                -ceq $expected
        ) `
        -Message "SHA-1 normalization"

    $validSignature = [pscustomobject]@{
        Status = "Valid"
        SignerCertificate = [pscustomobject]@{
            Subject = "CN=Example Production Code Signing"
            Thumbprint = $expected
        }
        TimeStamperCertificate = [pscustomobject]@{
            Subject = "CN=Example Timestamp Authority"
        }
    }
    $validResult = Get-AuthenticodeCheckResult `
        -Signature $validSignature `
        -ExpectedSigner $expected
    Assert-SelfTest -Condition $validResult.SignatureValid -Message "valid status"
    Assert-SelfTest -Condition $validResult.SignerSHA1Match -Message "matching signer"
    Assert-SelfTest `
        -Condition $validResult.TimestampCertificatePresent `
        -Message "timestamp presence"

    $wrongSigner = Get-AuthenticodeCheckResult `
        -Signature $validSignature `
        -ExpectedSigner "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
    Assert-SelfTest `
        -Condition (-not $wrongSigner.SignerSHA1Match) `
        -Message "wrong signer rejection"

    $unsignedSignature = [pscustomobject]@{
        Status = "NotSigned"
        SignerCertificate = $null
        TimeStamperCertificate = $null
    }
    $unsignedResult = Get-AuthenticodeCheckResult `
        -Signature $unsignedSignature `
        -ExpectedSigner $expected
    Assert-SelfTest `
        -Condition (-not $unsignedResult.SignatureValid) `
        -Message "unsigned status rejection"
    Assert-SelfTest `
        -Condition (-not $unsignedResult.SignerCertificatePresent) `
        -Message "missing signer rejection"
    Assert-SelfTest `
        -Condition (-not $unsignedResult.TimestampCertificatePresent) `
        -Message "missing timestamp rejection"

    $invalidSHARejected = $false
    try {
        ConvertTo-NormalizedSHA1 "not-a-thumbprint" | Out-Null
    } catch {
        $invalidSHARejected = $true
    }
    Assert-SelfTest -Condition $invalidSHARejected -Message "invalid SHA-1 rejection"

    $testRoot = Join-Path ([IO.Path]::GetTempPath()) (
        "sfl-signature-verifier-selftest-" + [guid]::NewGuid().ToString("N")
    )
    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    try {
        $installer = Join-Path $testRoot "installer.exe"
        $payloadRoot = Join-Path $testRoot "extracted"
        $backendRoot = Join-Path $payloadRoot "resources\backend"
        $provenance = Join-Path $backendRoot "_internal\backend\build_provenance.json"
        $manifest = Join-Path $backendRoot "bundle-manifest.json"
        $application = Join-Path $payloadRoot "smart-factory.exe"
        $runtimeFixture = Join-Path $backendRoot "SmartFactoryBackend.exe"
        $evidence = Join-Path $testRoot "nested\signed_release_identity.json"
        New-Item -ItemType Directory -Path (Split-Path -Parent $provenance) -Force |
            Out-Null
        Set-Content -LiteralPath $installer -Value "installer-fixture" -Encoding ASCII
        Set-Content -LiteralPath $application -Value "application-fixture" -Encoding ASCII
        Set-Content -LiteralPath $runtimeFixture -Value "backend-fixture" -Encoding ASCII
        @{ git_commit = $commit } | ConvertTo-Json |
            Set-Content -LiteralPath $provenance -Encoding UTF8
        Write-SelfTestBackendBundleManifest `
            -BackendRoot $backendRoot `
            -BuildCommit $commit

        $passingProvider = {
            param($Path)
            return [pscustomobject]@{
                Status = "Valid"
                SignerCertificate = [pscustomobject]@{
                    Subject = "CN=Example Production Code Signing"
                    Thumbprint = "00112233445566778899AABBCCDDEEFF00112233"
                }
                TimeStamperCertificate = [pscustomobject]@{
                    Subject = "CN=Example Timestamp Authority"
                }
            }
        }
        $passing = Invoke-WindowsReleaseVerification `
            -Installer $installer `
            -Application $application `
            -Manifest $manifest `
            -Provenance $provenance `
            -ExpectedCommit $commit `
            -ExpectedSigner $expected `
            -SignatureProvider $passingProvider `
            -OutputEvidencePath $evidence
        Assert-SelfTest -Condition $passing.Evidence.passed -Message "passing file verification"
        Assert-SelfTest `
            -Condition (Test-Path -LiteralPath $evidence -PathType Leaf) `
            -Message "evidence creation"
        $persistedEvidence = Get-Content -LiteralPath $evidence -Raw | ConvertFrom-Json
        Assert-SelfTest `
            -Condition ($persistedEvidence.schema_version -eq 2) `
            -Message "evidence schema"
        Assert-SelfTest `
            -Condition (
                $persistedEvidence.installer.sha256 -ceq
                (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
            ) `
            -Message "installer evidence hash"
        Assert-SelfTest `
            -Condition (
                $persistedEvidence.bundle_manifest.expected_bundle_sha256 -ceq
                $persistedEvidence.bundle_manifest.actual_bundle_sha256
            ) `
            -Message "bundle aggregate evidence"

        Set-Content -LiteralPath $runtimeFixture -Value "tampered-backend" -Encoding ASCII
        $bundleTamper = Invoke-WindowsReleaseVerification `
            -Installer $installer `
            -Application $application `
            -Manifest $manifest `
            -Provenance $provenance `
            -ExpectedCommit $commit `
            -ExpectedSigner $expected `
            -SignatureProvider $passingProvider
        Assert-SelfTest `
            -Condition (
                $bundleTamper.FailedChecks -ccontains "BackendBundleIntegrityVerified"
            ) `
            -Message "backend bundle tamper rejection"
        Set-Content -LiteralPath $runtimeFixture -Value "backend-fixture" -Encoding ASCII
        Write-SelfTestBackendBundleManifest `
            -BackendRoot $backendRoot `
            -BuildCommit $commit

        @{ build_git_commit = "ffffffffffffffffffffffffffffffffffffffff" } |
            ConvertTo-Json |
            Set-Content -LiteralPath $manifest -Encoding UTF8
        $mismatch = Invoke-WindowsReleaseVerification `
            -Installer $installer `
            -Application $application `
            -Manifest $manifest `
            -Provenance $provenance `
            -ExpectedCommit $commit `
            -ExpectedSigner $expected `
            -SignatureProvider $passingProvider
        Assert-SelfTest `
            -Condition ($mismatch.FailedChecks -ccontains "ManifestCommitMatch") `
            -Message "manifest commit mismatch"
        Assert-SelfTest `
            -Condition (-not $mismatch.Evidence.passed) `
            -Message "failed evidence verdict"
        $failedVerdictRejected = $false
        try {
            Assert-WindowsReleaseVerification -VerificationResult $mismatch
        } catch {
            $failedVerdictRejected = (
                $_.Exception.Message -like
                "Windows release signature verification failed: *ManifestCommitMatch*"
            )
        }
        Assert-SelfTest `
            -Condition $failedVerdictRejected `
            -Message "failed-check throw"

        @{ build_git_commit = $commit } | ConvertTo-Json |
            Set-Content -LiteralPath $manifest -Encoding UTF8
        @{ git_commit = "ffffffffffffffffffffffffffffffffffffffff" } |
            ConvertTo-Json |
            Set-Content -LiteralPath $provenance -Encoding UTF8
        $provenanceMismatch = Invoke-WindowsReleaseVerification `
            -Installer $installer `
            -Application $application `
            -Manifest $manifest `
            -Provenance $provenance `
            -ExpectedCommit $commit `
            -ExpectedSigner $expected `
            -SignatureProvider $passingProvider
        Assert-SelfTest `
            -Condition (
                $provenanceMismatch.FailedChecks -ccontains "ProvenanceCommitMatch"
            ) `
            -Message "provenance commit mismatch"

        @{ git_commit = $commit } | ConvertTo-Json |
            Set-Content -LiteralPath $provenance -Encoding UTF8
        Write-SelfTestBackendBundleManifest `
            -BackendRoot $backendRoot `
            -BuildCommit $commit
        $applicationPathForProvider = $application
        $mixedProvider = {
            param($Path)
            if ($Path -ceq $applicationPathForProvider) {
                return [pscustomobject]@{
                    Status = "NotSigned"
                    SignerCertificate = $null
                    TimeStamperCertificate = $null
                }
            }
            return [pscustomobject]@{
                Status = "Valid"
                SignerCertificate = [pscustomobject]@{
                    Subject = "CN=Example Production Code Signing"
                    Thumbprint = "00112233445566778899AABBCCDDEEFF00112233"
                }
                TimeStamperCertificate = [pscustomobject]@{
                    Subject = "CN=Example Timestamp Authority"
                }
            }
        }.GetNewClosure()
        $signatureFailure = Invoke-WindowsReleaseVerification `
            -Installer $installer `
            -Application $application `
            -Manifest $manifest `
            -Provenance $provenance `
            -ExpectedCommit $commit `
            -ExpectedSigner $expected `
            -SignatureProvider $mixedProvider
        Assert-SelfTest `
            -Condition (
                $signatureFailure.FailedChecks -ccontains "ApplicationSignatureValid" -and
                $signatureFailure.FailedChecks -ccontains "ApplicationSignerPresent" -and
                $signatureFailure.FailedChecks -ccontains "ApplicationTimestampPresent"
            ) `
            -Message "application signature failure aggregation"

        $missingFileRejected = $false
        try {
            Invoke-WindowsReleaseVerification `
                -Installer (Join-Path $testRoot "missing.exe") `
                -Application $application `
                -Manifest $manifest `
                -Provenance $provenance `
                -ExpectedCommit $commit `
                -ExpectedSigner $expected `
                -SignatureProvider $passingProvider | Out-Null
        } catch {
            $missingFileRejected = $_.Exception.Message -like "Installer file was not found:*"
        }
        Assert-SelfTest -Condition $missingFileRejected -Message "missing file rejection"

        $invalidCommitRejected = $false
        try {
            Invoke-WindowsReleaseVerification `
                -Installer $installer `
                -Application $application `
                -Manifest $manifest `
                -Provenance $provenance `
                -ExpectedCommit "not-a-commit" `
                -ExpectedSigner $expected `
                -SignatureProvider $passingProvider | Out-Null
        } catch {
            $invalidCommitRejected = (
                $_.Exception.Message -eq
                "Expected build commit must be a 40-character lowercase Git SHA."
            )
        }
        Assert-SelfTest `
            -Condition $invalidCommitRejected `
            -Message "invalid commit rejection"

        $evidenceWriteFailureRejected = $false
        try {
            Invoke-WindowsReleaseVerification `
                -Installer $installer `
                -Application $application `
                -Manifest $manifest `
                -Provenance $provenance `
                -ExpectedCommit $commit `
                -ExpectedSigner $expected `
                -SignatureProvider $passingProvider `
                -OutputEvidencePath $testRoot | Out-Null
        } catch {
            $evidenceWriteFailureRejected = $true
        }
        Assert-SelfTest `
            -Condition $evidenceWriteFailureRejected `
            -Message "evidence write failure rejection"

        Set-Content -LiteralPath $provenance -Value "{not-json" -Encoding ASCII
        $malformedJsonRejected = $false
        try {
            Invoke-WindowsReleaseVerification `
                -Installer $installer `
                -Application $application `
                -Manifest $manifest `
                -Provenance $provenance `
                -ExpectedCommit $commit `
                -ExpectedSigner $expected `
                -SignatureProvider $passingProvider | Out-Null
        } catch {
            $malformedJsonRejected = $true
        }
        Assert-SelfTest -Condition $malformedJsonRejected -Message "malformed JSON rejection"
    } finally {
        Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[PASS] Windows release signature verifier self-tests passed."
}

if ($SelfTest.IsPresent) {
    Invoke-SelfTest
    exit 0
}

$signatureProvider = {
    param($Path)
    Get-AuthenticodeSignature -LiteralPath $Path
}
$result = Invoke-WindowsReleaseVerification `
    -Installer $InstallerPath `
    -Application $AppExecutablePath `
    -Manifest $BundleManifestPath `
    -Provenance $BuildProvenancePath `
    -ExpectedCommit $ExpectedBuildCommit `
    -ExpectedSigner $ExpectedSignerSHA1 `
    -SignatureProvider $signatureProvider `
    -OutputEvidencePath $EvidencePath

$result.Evidence | ConvertTo-Json -Depth 8
Assert-WindowsReleaseVerification -VerificationResult $result

Write-Host "[PASS] Windows installer, application, signer, timestamp, and build provenance are verified."
