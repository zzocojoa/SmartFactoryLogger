[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-Contract {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw "Windows release workflow contract failed: $Message"
    }
}

function Assert-Matches {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [string]$Pattern,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Assert-Contract -Condition ([regex]::IsMatch($Text, $Pattern)) -Message $Message
}

function Assert-DoesNotMatch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [string]$Pattern,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Assert-Contract -Condition (-not [regex]::IsMatch($Text, $Pattern)) -Message $Message
}

function Invoke-SemanticActionVerification {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$WorkflowPaths
    )

    $verifierPath = Join-Path $PSScriptRoot "verify_windows_release_workflow_actions.cjs"
    Assert-Contract `
        -Condition (Test-Path -LiteralPath $verifierPath -PathType Leaf) `
        -Message "semantic workflow action verifier is missing"

    & node $verifierPath --self-test
    Assert-Contract `
        -Condition ($LASTEXITCODE -eq 0) `
        -Message "semantic workflow action verifier self-tests failed"

    & node $verifierPath @WorkflowPaths
    Assert-Contract `
        -Condition ($LASTEXITCODE -eq 0) `
        -Message "semantic workflow action verification failed"
}

function Assert-PinnedOfficialActionTextIsPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Workflow
    )

    $pins = [ordered]@{
        "actions/checkout" = "d23441a48e516b6c34aea4fa41551a30e30af803"
        "actions/setup-node" = "249970729cb0ef3589644e2896645e5dc5ba9c38"
        "actions/setup-python" = "ece7cb06caefa5fff74198d8649806c4678c61a1"
        "actions/upload-artifact" = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    }

    foreach ($item in $pins.GetEnumerator()) {
        Assert-Matches `
            -Text $Workflow `
            -Pattern ([regex]::Escape("uses: $($item.Key)@$($item.Value)")) `
            -Message "$($item.Key) must use the approved immutable commit pin"
    }
}

function ConvertTo-NormalizedPythonPackageName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return ($Name.ToLowerInvariant() -replace "[-_.]+", "-")
}

function Assert-HashLockedWindowsReleaseDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $backendRoot = Join-Path $RepositoryRoot "v2_next\backend"
    $lockPath = Join-Path $backendRoot "requirements-windows-release.lock"
    Assert-Contract `
        -Condition (Test-Path -LiteralPath $lockPath -PathType Leaf) `
        -Message "Windows signing dependency lock file is missing"

    $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8
    Assert-DoesNotMatch -Text $lock -Pattern "(?im)^# WARNING:" `
        -Message "Windows signing dependency lock must not contain unresolved warnings"
    Assert-DoesNotMatch -Text $lock -Pattern "(?im)^\s*(-e|--editable|git\+|https?://)" `
        -Message "Windows signing dependency lock must not contain editable, VCS, or URL requirements"

    $packageMatches = [regex]::Matches(
        $lock,
        "(?m)^([A-Za-z0-9_.-]+)==([^\s\\]+)\s*\\\s*$"
    )
    Assert-Contract -Condition ($packageMatches.Count -gt 0) `
        -Message "Windows signing dependency lock contains no exact package pins"
    $lockedPackages = @{}
    for ($index = 0; $index -lt $packageMatches.Count; $index++) {
        $match = $packageMatches[$index]
        $name = ConvertTo-NormalizedPythonPackageName $match.Groups[1].Value
        Assert-Contract -Condition (-not $lockedPackages.ContainsKey($name)) `
            -Message "Windows signing dependency lock contains a duplicate package: $name"
        $lockedPackages[$name] = $true
        $blockStart = $match.Index
        $blockEnd = if ($index + 1 -lt $packageMatches.Count) {
            $packageMatches[$index + 1].Index
        } else {
            $lock.Length
        }
        $block = $lock.Substring($blockStart, $blockEnd - $blockStart)
        Assert-Matches `
            -Text $block `
            -Pattern "--hash=sha256:[0-9a-f]{64}" `
            -Message "exact package pin is missing a SHA-256 hash: $name"
    }

    foreach ($inputName in @(
        "requirements.txt",
        "requirements-build.txt",
        "requirements-dev.txt"
    )) {
        $inputPath = Join-Path $backendRoot $inputName
        foreach ($line in Get-Content -LiteralPath $inputPath -Encoding UTF8) {
            $trimmed = $line.Trim()
            if (
                [string]::IsNullOrWhiteSpace($trimmed) -or
                $trimmed.StartsWith("#") -or
                $trimmed.StartsWith("-r ")
            ) {
                continue
            }
            $nameMatch = [regex]::Match($trimmed, "^([A-Za-z0-9_.-]+)")
            Assert-Contract -Condition $nameMatch.Success `
                -Message "unsupported requirement syntax in ${inputName}: $trimmed"
            $name = ConvertTo-NormalizedPythonPackageName $nameMatch.Groups[1].Value
            Assert-Contract -Condition $lockedPackages.ContainsKey($name) `
                -Message "direct dependency is absent from Windows signing lock: $name"
        }
    }
}

if (-not $SelfTest.IsPresent) {
    throw "Only -SelfTest is supported."
}

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$prWorkflowPath = Join-Path $repositoryRoot ".github\workflows\windows-release-artifact.yml"
$signedWorkflowPath = Join-Path $repositoryRoot ".github\workflows\windows-signed-release.yml"
foreach ($path in @($prWorkflowPath, $signedWorkflowPath)) {
    Assert-Contract `
        -Condition (Test-Path -LiteralPath $path -PathType Leaf) `
        -Message "required workflow was not found: $path"
}

$prWorkflow = Get-Content -LiteralPath $prWorkflowPath -Raw -Encoding UTF8
$signedWorkflow = Get-Content -LiteralPath $signedWorkflowPath -Raw -Encoding UTF8
Invoke-SemanticActionVerification `
    -WorkflowPaths @($prWorkflowPath, $signedWorkflowPath)
Assert-HashLockedWindowsReleaseDependencies -RepositoryRoot $repositoryRoot

$commonValidationPatterns = [ordered]@{
    "Electron dependency installation" = "(?m)^\s*run: npm ci\s*$"
    "backend isolated virtual environment" = "python -m venv backend\\\.venv"
    "portable/backend bundle build" = "scripts\\deploy\.ps1"
    "bundle manifest verification" = "bundle-manifest\.json"
    "build provenance verification" = "build_provenance\.json"
}
foreach ($workflow in @($prWorkflow, $signedWorkflow)) {
    foreach ($item in $commonValidationPatterns.GetEnumerator()) {
        Assert-Matches `
            -Text $workflow `
            -Pattern $item.Value `
            -Message "PR and signed workflows must both include $($item.Key)"
    }
    Assert-Matches -Text $workflow -Pattern 'node-version:\s*"22\.22\.2"' `
        -Message "Windows workflows must pin the exact Node.js release runtime"
    Assert-Matches -Text $workflow -Pattern 'python-version:\s*"3\.12\.6"' `
        -Message "Windows workflows must pin the exact Python release runtime"
    Assert-Matches -Text $workflow -Pattern "--require-hashes" `
        -Message "Windows workflows must require Python package hashes"
    Assert-Matches -Text $workflow -Pattern "--only-binary=:all:" `
        -Message "Windows workflows must reject Python source distributions"
    Assert-Matches -Text $workflow -Pattern "requirements-windows-release\.lock" `
        -Message "Windows workflows must install the release dependency lock"
}

foreach ($pattern in @(
    "npm run health:electron-startup",
    "npm run health:backend:lint",
    "npm run health:backend:typecheck",
    "npm run health:backend:test"
)) {
    Assert-Matches `
        -Text $prWorkflow `
        -Pattern ([regex]::Escape($pattern)) `
        -Message "PR artifact workflow must execute $pattern"
}
foreach ($path in @(
    'v2_next/backendControlClient.js',
    'v2_next/backendProcessLifecycle.js',
    'v2_next/electronRuntimeSafety.js',
    'v2_next/electronRuntimeSafetyBackpressure.fixture.cjs',
    'v2_next/electronRuntimeSafetyBackpressure.test.cjs',
    'v2_next/shutdownDiagnosticTrace.js',
    'v2_next/shutdownDiagnosticTrace.test.cjs',
    'v2_next/shutdownDiagnosticTraceWorker.js',
    'v2_next/scripts/run_closeout_hang_reproduction.ps1',
    'v2_next/scripts/verify_packaged_electron_sources.cjs'
)) {
    Assert-Matches `
        -Text $prWorkflow `
        -Pattern ([regex]::Escape("- `"$path`"")) `
        -Message "PR artifact workflow path filter must include $path"
}
Assert-Matches -Text $signedWorkflow -Pattern "(?m)^\s*run: npm run health\s*$" `
    -Message "signed workflow must run the complete health suite on the exact release commit"

Assert-Matches -Text $prWorkflow -Pattern "(?m)^  pull_request:\s*$" `
    -Message "PR artifact workflow must run for pull requests"
Assert-DoesNotMatch -Text $prWorkflow -Pattern "(?m)^  (push|workflow_dispatch):" `
    -Message "PR artifact workflow must not publish from tags or manual dispatch"
Assert-DoesNotMatch -Text $prWorkflow -Pattern "production-signing|\$\{\{\s*secrets\." `
    -Message "PR artifact workflow must not access production signing material"
Assert-Matches -Text $prWorkflow `
    -Pattern 'run_closeout_hang_reproduction\.ps1"?\s+-SelfTest' `
    -Message "PR workflow must execute closeout reproduction helper self-tests"
Assert-Matches -Text $prWorkflow `
    -Pattern 'verify_windows_release_signature\.ps1"?\s+-SelfTest' `
    -Message "PR workflow must execute signature verifier self-tests"
Assert-Matches -Text $prWorkflow `
    -Pattern 'verify_windows_release_workflow_contract\.ps1"?\s+-SelfTest' `
    -Message "PR workflow must execute its release-workflow contract test"
Assert-Matches -Text $prWorkflow `
    -Pattern 'verify_packaged_electron_sources\.cjs[\s\S]*--asar\s+dist/win-unpacked/resources/app\.asar' `
    -Message "PR workflow must verify packaged Electron source identity"
Assert-Matches -Text $prWorkflow -Pattern "smartfactorylogger-windows-pr-unsigned-" `
    -Message "PR artifacts must be explicitly named unsigned"
Assert-PinnedOfficialActionTextIsPresent -Workflow $prWorkflow

Assert-Matches -Text $signedWorkflow -Pattern "(?m)^  workflow_dispatch:\s*$" `
    -Message "signed releases must require an explicit protected workflow dispatch"
Assert-DoesNotMatch -Text $signedWorkflow -Pattern "(?m)^  push:" `
    -Message "candidate tag workflow code must not receive signing secrets directly"
Assert-Matches -Text $signedWorkflow -Pattern "(?m)^    environment: production-signing\s*$" `
    -Message "signed release job must use the protected production-signing environment"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'DEFAULT_BRANCH:\s+\$\{\{ github\.event\.repository\.default_branch \}\}' `
    -Message "signed workflow must pass the default branch through an environment variable"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'GITHUB_REF_NAME\s+-cne\s+\$env:DEFAULT_BRANCH' `
    -Message "signed workflow must require the protected default-branch workflow ref"
Assert-DoesNotMatch -Text $signedWorkflow `
    -Pattern 'GITHUB_REF_NAME\s+-cne\s+"\$\{\{' `
    -Message "GitHub context values must not be interpolated directly into PowerShell code"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'git rev-parse "refs/tags/\$env:RELEASE_TAG\^\{commit\}"' `
    -Message "signed workflow must resolve the supplied release tag commit"
Assert-Matches -Text $signedWorkflow `
    -Pattern '\$tagCommit\s+-cne\s+\$actualCommit' `
    -Message "release tag must point to the exact protected workflow commit"
Assert-Matches -Text $signedWorkflow `
    -Pattern "WINDOWS_CODE_SIGNING_PFX_BASE64" `
    -Message "signed workflow must require the PFX secret"
Assert-Matches -Text $signedWorkflow `
    -Pattern "WINDOWS_CODE_SIGNING_PFX_PASSWORD" `
    -Message "signed workflow must require the PFX password"
Assert-Matches -Text $signedWorkflow `
    -Pattern "WINDOWS_CODE_SIGNING_CERT_SHA1" `
    -Message "signed workflow must pin the expected signer thumbprint"
Assert-DoesNotMatch -Text $signedWorkflow `
    -Pattern "(?im)Write-(Host|Output).*(SIGNING_PFX|CSC_KEY_PASSWORD|PFX_BASE64)" `
    -Message "signed workflow must not print certificate material or passwords"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'verify_windows_release_signature\.ps1"?\s+-SelfTest' `
    -Message "signed workflow must run signature verifier self-tests before signing"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'verify_windows_release_workflow_contract\.ps1"?\s+-SelfTest' `
    -Message "signed workflow must run the release-workflow contract test"
Assert-Matches -Text $signedWorkflow `
    -Pattern '-ExpectedBuildCommit\s+\$env:EXPECTED_BUILD_COMMIT' `
    -Message "signed artifact verification must bind the expected commit"
Assert-Matches -Text $signedWorkflow `
    -Pattern '-ExpectedSignerSHA1\s+\$env:EXPECTED_SIGNER_SHA1' `
    -Message "signed artifact verification must bind the expected signer"
Assert-Matches -Text $signedWorkflow `
    -Pattern 'Join-Path\s+\$env:ProgramFiles\s+"7-Zip\\7z\.exe"' `
    -Message "signed workflow must use the runner-owned 7-Zip path for exact installer extraction"
Assert-Matches -Text $signedWorkflow `
    -Pattern '\$applicationPath\s*=\s*Join-Path\s+\$payloadRoot\s+"smart-factory\.exe"' `
    -Message "signature evidence must verify the application extracted from the installer"
Assert-Matches -Text $signedWorkflow `
    -Pattern '\$manifestPath\s*=\s*Join-Path\s+\$payloadRoot\s+"resources\\backend\\bundle-manifest\.json"' `
    -Message "signature evidence must verify the manifest extracted from the installer"
Assert-Matches -Text $signedWorkflow `
    -Pattern '\$provenancePath\s*=\s*Join-Path\s+\$payloadRoot\s+"resources\\backend\\_internal\\backend\\build_provenance\.json"' `
    -Message "signature evidence must verify provenance extracted from the installer"
Assert-Matches -Text $signedWorkflow `
    -Pattern '-InstallerPath\s+\$publishedInstallerPath' `
    -Message "verification must hash the final installer copy selected for upload"
Assert-Matches -Text $signedWorkflow `
    -Pattern '\$finalInstallerSha256\s+-cne\s+\[string\]\$evidence\.installer\.sha256' `
    -Message "upload preparation must recheck the final installer against signed evidence"
Assert-DoesNotMatch -Text $signedWorkflow `
    -Pattern "(?im)Copy-Item.*Portable|Copy-Item.*portableZip" `
    -Message "unsigned portable ZIP must not be promoted as a signed artifact"
Assert-Matches -Text $signedWorkflow -Pattern "smartfactorylogger-windows-signed-" `
    -Message "production artifact must be explicitly named signed"
Assert-PinnedOfficialActionTextIsPresent -Workflow $signedWorkflow

$cleanupIndex = $signedWorkflow.IndexOf("- name: Remove signing certificate and extracted payload")
$uploadIndex = $signedWorkflow.IndexOf("- name: Upload signed Windows release")
Assert-Contract `
    -Condition ($cleanupIndex -ge 0 -and $uploadIndex -gt $cleanupIndex) `
    -Message "ephemeral PFX cleanup must be declared before artifact upload"
Assert-Matches -Text $signedWorkflow -Pattern "(?m)^        if: always\(\)\s*$" `
    -Message "ephemeral PFX cleanup must run after failures"

Write-Host "[PASS] Windows PR and signed-release workflow contracts are verified."
