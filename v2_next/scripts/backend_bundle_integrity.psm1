Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ObjectPropertyValue {
    param(
        [AllowNull()]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-Utf8Sha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    $encoding = New-Object System.Text.UTF8Encoding($false)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $encoding.GetBytes($Text)
        $hash = $hasher.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "")
    } finally {
        $hasher.Dispose()
    }
}

function Test-SafeBundleRelativePath {
    param(
        [AllowEmptyString()]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }
    if ($Path.Contains("\") -or $Path.Contains(":")) {
        return $false
    }
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $false
    }
    $segments = @($Path.Split("/"))
    if ($segments.Count -eq 0) {
        return $false
    }
    foreach ($segment in $segments) {
        if (
            [string]::IsNullOrWhiteSpace($segment) -or
            $segment -eq "." -or
            $segment -eq ".."
        ) {
            return $false
        }
    }
    return $true
}

function Test-BackendBundleIntegrity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BackendRoot
    )

    $errors = New-Object System.Collections.Generic.List[string]
    $missingFiles = New-Object System.Collections.Generic.List[string]
    $unexpectedFiles = New-Object System.Collections.Generic.List[string]
    $mismatchFiles = New-Object System.Collections.Generic.List[string]
    $invalidPaths = New-Object System.Collections.Generic.List[string]
    $expectedBundleSha256 = ""
    $actualBundleSha256 = ""
    $buildGitCommit = ""
    $schemaVersion = ""
    $packagingMode = ""
    $expectedFileCount = 0
    $actualFileCount = 0
    $verifiedFileCount = 0
    $manifestPath = Join-Path $BackendRoot "bundle-manifest.json"

    if (-not (Test-Path -LiteralPath $BackendRoot -PathType Container)) {
        [void]$errors.Add("backend-root-missing")
    } elseif (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        [void]$errors.Add("manifest-missing")
    }

    $manifest = $null
    if ($errors.Count -eq 0) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        } catch {
            [void]$errors.Add("manifest-invalid-json")
        }
    }

    if ($null -ne $manifest) {
        $schemaVersion = [string](Get-ObjectPropertyValue $manifest "schema_version")
        $packagingMode = [string](Get-ObjectPropertyValue $manifest "packaging_mode")
        $buildGitCommit = [string](Get-ObjectPropertyValue $manifest "build_git_commit")
        $expectedBundleSha256 = [string](Get-ObjectPropertyValue $manifest "bundle_sha256")
        $declaredFileCount = Get-ObjectPropertyValue $manifest "file_count"
        if ($null -ne $declaredFileCount) {
            $expectedFileCount = [int]$declaredFileCount
        }

        if ($schemaVersion -ne "smartfactory-backend-bundle-v1") {
            [void]$errors.Add("schema-version-invalid")
        }
        if ($packagingMode -ne "onedir") {
            [void]$errors.Add("packaging-mode-invalid")
        }
        if ($buildGitCommit -notmatch "^[0-9a-f]{40}$") {
            [void]$errors.Add("build-git-commit-invalid")
        }
        if ($expectedBundleSha256 -notmatch "^[0-9A-Fa-f]{64}$") {
            [void]$errors.Add("bundle-sha256-invalid")
        }

        $rootFullPath = (Get-Item -LiteralPath $BackendRoot).FullName.TrimEnd("\")
        $rootPrefix = $rootFullPath + "\"
        $manifestFullPath = (Get-Item -LiteralPath $manifestPath).FullName
        $actualRelativePaths = [string[]]@(
            Get-ChildItem -LiteralPath $rootFullPath -Recurse -File |
                Where-Object { $_.FullName -ne $manifestFullPath } |
                ForEach-Object {
                    $_.FullName.Substring($rootPrefix.Length).Replace("\", "/")
                }
        )
        [System.Array]::Sort($actualRelativePaths, [System.StringComparer]::Ordinal)
        $actualFileCount = $actualRelativePaths.Count

        $manifestEntries = @(Get-ObjectPropertyValue $manifest "files")
        $expectedSet = @{}
        $entryPaths = New-Object System.Collections.Generic.List[string]
        $actualAggregateLines = New-Object System.Collections.Generic.List[string]
        foreach ($entry in $manifestEntries) {
            $relativePath = [string](Get-ObjectPropertyValue $entry "path")
            if (-not (Test-SafeBundleRelativePath $relativePath)) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            if ($expectedSet.ContainsKey($relativePath)) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            $expectedSet[$relativePath] = $true
            [void]$entryPaths.Add($relativePath)

            $nativeRelativePath = $relativePath.Replace("/", "\")
            $candidatePath = [System.IO.Path]::GetFullPath(
                (Join-Path $rootFullPath $nativeRelativePath)
            )
            if (-not $candidatePath.StartsWith(
                $rootPrefix,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                [void]$invalidPaths.Add($relativePath)
                continue
            }
            if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
                [void]$missingFiles.Add($relativePath)
                continue
            }

            $actualFile = Get-Item -LiteralPath $candidatePath
            $actualSha256 = (
                Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256
            ).Hash.ToUpperInvariant()
            $expectedLength = [int64](Get-ObjectPropertyValue $entry "length")
            $expectedSha256 = [string](Get-ObjectPropertyValue $entry "sha256")
            if (
                $actualFile.Length -ne $expectedLength -or
                $actualSha256 -cne $expectedSha256.ToUpperInvariant()
            ) {
                [void]$mismatchFiles.Add($relativePath)
            } else {
                $verifiedFileCount++
            }
            [void]$actualAggregateLines.Add(
                "$relativePath`t$($actualFile.Length)`t$actualSha256"
            )
        }

        if ($expectedFileCount -ne $manifestEntries.Count) {
            [void]$errors.Add("manifest-file-count-invalid")
        }
        $sortedEntryPaths = [string[]]$entryPaths.ToArray()
        [System.Array]::Sort($sortedEntryPaths, [System.StringComparer]::Ordinal)
        if (($sortedEntryPaths -join "`n") -cne ($entryPaths.ToArray() -join "`n")) {
            [void]$errors.Add("manifest-file-order-invalid")
        }
        foreach ($relativePath in $actualRelativePaths) {
            if (-not $expectedSet.ContainsKey($relativePath)) {
                [void]$unexpectedFiles.Add($relativePath)
            }
        }
        if ($missingFiles.Count -eq 0 -and $invalidPaths.Count -eq 0) {
            $aggregatePayload = ($actualAggregateLines.ToArray() -join "`n") + "`n"
            $actualBundleSha256 = Get-Utf8Sha256 -Text $aggregatePayload
        }
        if ($actualBundleSha256 -cne $expectedBundleSha256.ToUpperInvariant()) {
            [void]$errors.Add("bundle-sha256-mismatch")
        }
    }

    $ok = (
        $errors.Count -eq 0 -and
        $missingFiles.Count -eq 0 -and
        $unexpectedFiles.Count -eq 0 -and
        $mismatchFiles.Count -eq 0 -and
        $invalidPaths.Count -eq 0 -and
        $expectedFileCount -eq $actualFileCount -and
        $verifiedFileCount -eq $expectedFileCount
    )
    return [pscustomobject][ordered]@{
        ok                     = $ok
        manifest_path          = $manifestPath
        schema_version         = $schemaVersion
        packaging_mode         = $packagingMode
        build_git_commit       = $buildGitCommit
        expected_bundle_sha256 = $expectedBundleSha256
        actual_bundle_sha256   = $actualBundleSha256
        expected_file_count    = $expectedFileCount
        actual_file_count      = $actualFileCount
        verified_file_count    = $verifiedFileCount
        missing_files          = @($missingFiles.ToArray())
        unexpected_files       = @($unexpectedFiles.ToArray())
        mismatch_files         = @($mismatchFiles.ToArray())
        invalid_paths          = @($invalidPaths.ToArray())
        errors                 = @($errors.ToArray())
    }
}

Export-ModuleMember -Function Get-Utf8Sha256, Test-BackendBundleIntegrity
