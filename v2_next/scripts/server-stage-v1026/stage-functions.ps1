# Pure staging functions. No host queries or filesystem writes occur when this file is loaded.
function Assert-StageEntryName {
    param([string]$Name)
    Assert-EvidenceEntryName $Name
    # This private transfer has an ASCII-only file contract. Also reject DOS device basenames with extensions.
    if ($Name -cnotmatch '^[A-Za-z0-9_./ ()-]+$') { throw 'Non-allowlisted transfer filename characters.' }
    foreach ($part in $Name.Split('/')) {
        if ($part.Split('.')[0] -match '^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])$') { throw 'Windows reserved transfer filename.' }
    }
}
function Read-StageJson {
    param([string]$Path)
    $text=[Text.UTF8Encoding]::new($false,$true).GetString([IO.File]::ReadAllBytes($Path))
    if ($text.Length -gt 0 -and [int]$text[0] -eq 0xFEFF) { $text=$text.Substring(1) }
    return ConvertFrom-Json -InputObject $text
}
function Write-StageBytesNew {
    param([string]$Path,[byte[]]$Bytes)
    Assert-EvidencePlainPath $Path
    $stream=[IO.File]::Open($Path,'CreateNew','Write','None')
    try { $stream.Write($Bytes,0,$Bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}
function Get-StageMutableConfigFact {
    param([string]$Path)
    Assert-EvidencePlainPath $Path
    # Let the live app save/replace its config. Every invocation opens the current path anew.
    $stream=[IO.File]::Open($Path,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        $length=$stream.Length
        if ($length -gt 1048576) { throw 'Unexpected configuration file size.' }
        $hash=Get-EvidenceStreamHash $stream
        if ($stream.Length -ne $length -or (Get-EvidenceStreamHash $stream) -cne $hash) { throw 'Config changed during shared read.' }
        return [pscustomobject]@{length=$length;sha256=$hash;sharing='ReadWrite,Delete; fresh path open per sample'}
    } finally { $stream.Dispose() }
}
function Assert-StageContract {
    param([object]$Manifest)
    if ($Manifest.schema_version -cne 'v1026-static-stage-transfer-v1' -or
        $Manifest.product_commit -cne 'd7a1b20f96711fb07fc7add0867e79ee36506fce' -or
        $Manifest.tooling_commit -cne 'c03f7c76ff6e75bfe330275ac0fa01326f357261' -or
        $Manifest.classification -cne 'UNSIGNED_INTERNAL_DEVELOPMENT_STATIC_STAGE_ONLY') { throw 'Transfer identity differs.' }
    foreach ($n in @('installation_authorized','observation_authorized','production_promotion_allowed')) {
        $p=$Manifest.PSObject.Properties[$n]
        if ($null -eq $p -or $p.Value -isnot [bool] -or $p.Value) { throw 'Transfer approval flags must be false.' }
    }
    $entries=@($Manifest.files)
    if ($entries.Count -ne 31) { throw 'Transfer requires 31 exact payload files.' }
    $names=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $total=[long]0
    foreach ($e in $entries) {
        Assert-StageEntryName $e.name
        if (-not $names.Add($e.name) -or
            $e.name -cnotmatch '^(release/[^/]+|kit/[^/]+|server-stage\.ps1|SERVER_GUIDE\.md)$' -or
            ($e.length -isnot [int] -and $e.length -isnot [long]) -or
            $e.length -lt 0 -or $e.length -gt 170000000 -or $e.sha256 -cnotmatch '^[A-F0-9]{64}$') {
            throw 'Invalid transfer file contract.'
        }
        $total+=$e.length
    }
    if ($total -gt 180000000 -or
        @($entries | Where-Object name -CLike 'release/*').Count -ne 14 -or
        @($entries | Where-Object name -CLike 'kit/*').Count -ne 15 -or
        -not $names.Contains('server-stage.ps1') -or -not $names.Contains('SERVER_GUIDE.md')) { throw 'Transfer membership differs.' }
}
function Assert-StageProtectedRoot {
    param([string]$Path)
    Assert-EvidencePlainPath $Path
    $acl=[IO.Directory]::GetAccessControl($Path)
    Assert-StageAcl $acl
}
function Assert-StageAcl {
    param([Security.AccessControl.DirectorySecurity]$Acl)
    if (-not $Acl.AreAccessRulesProtected) { throw 'Staging ACL must be protected.' }
    $owner=$Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($owner -cnotin @('S-1-5-32-544','S-1-5-18')) { throw 'Untrusted staging owner.' }
    $rules=@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) { throw 'Unexpected staging ACL membership.' }
    $sids=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($r in $rules) {
        if (-not $sids.Add($r.IdentityReference.Value) -or $r.IsInherited -or
            $r.IdentityReference.Value -cnotin @('S-1-5-32-544','S-1-5-18') -or
            $r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $r.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
            $r.InheritanceFlags -ne ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit) -or
            $r.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None) { throw 'Unexpected staging ACL rule.' }
    }
}
function New-StageProtectedRoot {
    param([string]$Path)
    Assert-EvidencePlainPath $Path
    if ([IO.Directory]::Exists($Path) -or [IO.File]::Exists($Path)) { throw 'Existing staging target preserved.' }
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach ($sid in @('S-1-5-32-544','S-1-5-18')) {
        $rule=[Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    # Native .NET Framework creates the directory with its restrictive DACL, not after file copying.
    $null=[IO.Directory]::CreateDirectory($Path,$acl)
    Assert-StageProtectedRoot $Path
}
function Expand-StageArchiveNew {
    param([string]$ZipPath,[string]$Destination,[object[]]$Entries,[string]$ExpectedSha256)
    # This function is also exercised with owned local fixtures; callers protect the enclosing root.
    Assert-EvidencePlainPath $Destination
    if ([IO.Directory]::Exists($Destination) -or [IO.File]::Exists($Destination)) { throw 'Existing extraction target preserved.' }
    $pin=[IO.File]::Open($ZipPath,'Open','Read','Read')
    $archive=$null
    try {
        foreach ($spec in $Entries) { Assert-StageEntryName $spec.name }
        $null=Test-VerifiedEvidenceZip -Path $ZipPath -Entries $Entries -ExpectedSha256 $ExpectedSha256
        $null=[IO.Directory]::CreateDirectory($Destination)
        $root=[IO.Path]::GetFullPath($Destination).TrimEnd('\')
        $archive=[IO.Compression.ZipArchive]::new($pin,'Read',$true)
        foreach ($entry in $archive.Entries) {
            $target=[IO.Path]::GetFullPath((Join-Path $root $entry.FullName.Replace('/','\')))
            if (-not $target.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or $target.Length -gt 240) { throw 'Extraction path exceeds boundary.' }
            Assert-EvidencePlainPath $target
            $null=[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
            Assert-EvidencePlainPath $target
            $input=$entry.Open(); $output=$null
            try {
                $output=[IO.File]::Open($target,'CreateNew','Write','None')
                $buffer=New-Object byte[] 81920; $count=[long]0
                while (($n=$input.Read($buffer,0,$buffer.Length)) -gt 0) {
                    $count+=$n
                    if ($count -gt $entry.Length) { throw 'Extraction exceeds entry size.' }
                    $output.Write($buffer,0,$n)
                }
                if ($count -ne $entry.Length) { throw 'Incomplete extraction.' }
                $output.Flush($true)
            } finally { if ($null -ne $output) { $output.Dispose() }; $input.Dispose() }
        }
        $names=Get-EvidenceFileNames $root
        $want=@($Entries.name | Sort-Object)
        if ((@($names | Sort-Object) -join '|') -cne ($want -join '|')) { throw 'Extracted membership differs.' }
        foreach ($e in $Entries) {
            $fact=Get-EvidenceFileFact (Join-Path $root $e.name.Replace('/','\'))
            if ($fact.sha256 -cne $e.sha256 -or $fact.length -ne $e.length) { throw 'Extracted file differs.' }
        }
    } finally { if ($null -ne $archive) { $archive.Dispose() }; $pin.Dispose() }
}
function Get-StageRequired {
    param([AllowNull()][object]$Object,[string]$Name)
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties[$Name]) { throw ('Missing local API field: '+$Name) }
    return $Object.PSObject.Properties[$Name].Value
}
function Select-StageStatus {
    param([object]$Config)
    $image=Get-StageRequired $Config 'image'
    $record=[ordered]@{}
    foreach ($name in @('image_status','image_source','last_success_at','last_error_at','last_error_code',
        'source_port_enforcement_active','image_refresh_success_count','image_refresh_failure_count',
        'source_port_transport_failure_count','source_port_reuse_violation_count','source_port_bind_retry_exhaustion_count')) {
        $p=$image.PSObject.Properties[$name]
        # Optional diagnostic values remain explicitly missing/null; never coerce them to zero or health PASS.
        $record[$name]=[ordered]@{present=($null -ne $p);value=$(if ($null -ne $p) { $p.Value } else { $null })}
    }
    return [pscustomobject]$record
}
function Get-StageLocalJson {
    param([ValidateSet('health','api/spot/config')][string]$Endpoint)
    $request=[Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
    $request.Method='GET'; $request.Proxy=$null; $request.AllowAutoRedirect=$false
    $request.Timeout=10000; $request.ReadWriteTimeout=10000
    $response=$null; $stream=$null; $buffer=[IO.MemoryStream]::new()
    $clock=[Diagnostics.Stopwatch]::StartNew()
    try {
        $response=$request.GetResponse()
        if ([int]$response.StatusCode -ne 200) { throw 'Local API response not 200.' }
        $stream=$response.GetResponseStream(); $chunk=New-Object byte[] 8192
        while (($read=$stream.Read($chunk,0,$chunk.Length)) -gt 0) {
            if ($buffer.Length+$read -gt 2097152 -or $clock.Elapsed.TotalSeconds -gt 20) { throw 'Local status size/time budget exceeded.' }
            $buffer.Write($chunk,0,$read)
        }
        return ConvertFrom-Json -InputObject ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
    } finally { if ($null -ne $stream) { $stream.Dispose() }; if ($null -ne $response) { $response.Dispose() }; $buffer.Dispose() }
}
function Get-StageRuntime {
    $install='C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $backends=@(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
    $owners=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($backends.Count -ne 1 -or $owners.Count -ne 1 -or $owners[0] -ne $backends[0].Id) { throw 'Backend/listener identity is ambiguous.' }
    $backend=$backends[0]
    if ($backend.Path -ine ($install+'\resources\backend\SmartFactoryBackend.exe')) { throw 'Unexpected current backend path.' }
    Assert-EvidencePlainPath $backend.Path
    $cim=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$backend.Id)
    $apps=@(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
    $main=@($apps | Where-Object Id -eq $cim.ParentProcessId)
    if ($main.Count -ne 1) { throw 'Current app parent is ambiguous.' }
    foreach ($app in $apps) { if ($app.Path -ine ($install+'\smart-factory.exe')) { throw 'Unexpected current app path.' } }
    return [pscustomobject]@{main_pid=$main[0].Id;main_start_utc_ticks=$main[0].StartTime.ToUniversalTime().Ticks;
        backend_pid=$backend.Id;backend_start_utc_ticks=$backend.StartTime.ToUniversalTime().Ticks;app_process_count=$apps.Count}
}
function Assert-StageSameRuntime {
    param([object]$Before,[object]$After)
    foreach ($n in @('main_pid','main_start_utc_ticks','backend_pid','backend_start_utc_ticks')) {
        if ($Before.$n -ne $After.$n) { throw 'Runtime changed during staging; preserve output and review.' }
    }
}
