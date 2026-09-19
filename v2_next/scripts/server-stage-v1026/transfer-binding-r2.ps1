# Build-host-only validation functions. No server entrypoint or approval bypass.
Set-StrictMode -Version Latest

function Invoke-TransferGit {
    param([string]$Root,[string[]]$Arguments)
    $lines=@(& git -C $Root @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw 'Transfer Git identity query failed.' }
    return ($lines -join "`n").Trim()
}

function Get-TransferSourceBinding {
    param([Parameter(Mandatory=$true)][string]$CanarySource)
    $repo=Invoke-TransferGit $CanarySource @('rev-parse','--show-toplevel')
    $relative='v2_next/scripts/canary-v1026'
    if ([IO.Path]::GetFullPath($CanarySource).TrimEnd('\','/') -ine
        [IO.Path]::GetFullPath((Join-Path $repo $relative))) { throw 'Unexpected Canary source location.' }
    $head=Invoke-TransferGit $repo @('rev-parse','HEAD')
    $tree=Invoke-TransferGit $repo @('rev-parse',('HEAD:'+$relative))
    # The unchanged reviewed subtree, not the pre-commit repository HEAD.
    if ($head -cnotmatch '^[a-f0-9]{40}$' -or
        $tree -cne 'df4ebc25261b78f355bad5f52884a18a77ba66b9') { throw 'Reviewed Canary tree differs.' }
    $status=Invoke-TransferGit $repo @('status','--porcelain','--untracked-files=all','--',$relative)
    if ($status -ne '') { throw 'Canary source must be clean, including untracked files.' }
    $records=Invoke-TransferGit $repo @('ls-tree','-r',('HEAD:'+$relative))
    $names=@(foreach ($record in ($records -split "`n")) {
        if ($record -cnotmatch '^100644 blob ([a-f0-9]{40})\t([A-Za-z0-9_.-]+)$') { throw 'Unexpected Canary tree entry.' }
        $blob=$Matches[1]; $name=$Matches[2]
        $path=Join-Path $CanarySource $name
        $node=[IO.FileInfo]::new($path)
        while ($null -ne $node) {
            if ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Missing or reparse Canary source path.'
            }
            if ($node -is [IO.FileInfo]) { $node=$node.Directory } else { $node=$node.Parent }
        }
        # Do not let skip-worktree, assume-unchanged or clean filters hide changed bytes.
        if ((Invoke-TransferGit $repo @('hash-object','--no-filters','--',$path)) -cne $blob) {
            throw 'Canary working bytes differ from the reviewed Git blob.'
        }
        $name
    })
    return [pscustomobject]@{head=$head;canary_tree=$tree;names=$names}
}

function Read-TransferCanaryReceipt {
    param([string]$Path,[string]$ExpectedSha256,[string]$CanarySource,[object]$Binding)
    Assert-EvidencePlainPath $Path
    $pin=[IO.File]::Open($Path,'Open','Read','Read')
    try {
        if ((Get-EvidenceStreamHash $pin) -cne $ExpectedSha256) { throw 'Canary receipt SHA256 differs.' }
        $pin.Position=0
        $reader=[IO.StreamReader]::new($pin,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try { $receipt=ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
    } finally { $pin.Dispose() }
    if ($receipt.schema_version -cne 'v1026-canary-offline-build-v1' -or
        $receipt.result -cne 'V1026_CANARY_PORT_OFFLINE_VERIFIED' -or
        $receipt.tooling_parent_commit -cne $Binding.head -or
        $receipt.port_regression.tests_passed -isnot [int] -or $receipt.port_regression.tests_passed -ne 71 -or
        $receipt.loopback_integration_passed -isnot [bool] -or -not $receipt.loopback_integration_passed) {
        throw 'Fresh current-HEAD release-review evidence required; OfflineCi is not distributable.'
    }
    foreach ($flag in @('server_execution_authorized','observation_started','full_120m_allowed','production_promotion_allowed')) {
        if ($receipt.$flag -isnot [bool] -or $receipt.$flag) { throw 'Canary approval flags must be boolean false.' }
    }
    $current=@((Get-EvidenceFileNames $CanarySource) | Sort-Object)
    $expected=@($Binding.names | Sort-Object)
    $snapshot=@($receipt.tooling_source_snapshot.entries)
    if (($current -join '|') -cne ($expected -join '|') -or
        (@($snapshot.name | Sort-Object) -join '|') -cne ($expected -join '|')) {
        throw 'Canary source snapshot membership differs, including ignored files.'
    }
    foreach ($entry in $snapshot) {
        Assert-EvidenceEntryName $entry.name
        $fact=Get-EvidenceFileFact (Join-Path $CanarySource $entry.name)
        if (($entry.length -isnot [int] -and $entry.length -isnot [long]) -or
            $entry.sha256 -isnot [string] -or $fact.sha256 -cne $entry.sha256 -or $fact.length -ne $entry.length) {
            throw 'Canary source snapshot bytes differ.'
        }
    }
    return $receipt
}

function Assert-TransferHistoricalInputs {
    param([string]$StageSource)
    $pins=[ordered]@{
        'server-stage.ps1'='D6A8862019EF996FC9B382A698F64499107CD5B5978F50E061385F15D286F515'
        'stage-functions.ps1'='66ADC9B727D029977CEF72C4184470F76CEE1B983545755A05D24C85E0E11963'
        'launch-template.ps1'='B59A8EEA10E3BBDB09EBBFB1F2D90E4185C9B4821FDAF75672BD3463C899BEFC'
        'SERVER_GUIDE.md'='3DAE000F71CB0FC81B45C85E07B047FBE6729432DCA6B21E781DEA4AB1481FEB'
    }
    foreach ($name in $pins.Keys) {
        if ((Get-EvidenceFileFact (Join-Path $StageSource $name)).sha256 -cne $pins[$name]) {
            throw ('Historical stage input differs: '+$name)
        }
    }
}
