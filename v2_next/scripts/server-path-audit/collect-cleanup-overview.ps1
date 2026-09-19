[CmdletBinding()]
param([switch]$SelfTest)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Metadata collection only. This is not a deletion plan or execution helper.
function Get-OverviewClass {
    param([string]$Path)
    $p = $Path.TrimEnd('\')
    $protected = @(
        'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2',
        'C:\Users\user\AppData\Roaming\SmartFactoryLogger',
        'C:\Users\user\AppData\Roaming\smart-factory-logger-v2',
        'C:\ProgramData\SFLOps',
        'C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109',
        'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503',
        'C:\Users\user\AppData\Local\SFLCanary\runtime_validation_20260909_135132',
        'C:\Users\user\AppData\Local\SFLCanary\runtime_validation_20260909_233747'
    )
    foreach ($keep in $protected) {
        if ($p -ieq $keep -or $p.StartsWith($keep+'\',[StringComparison]::OrdinalIgnoreCase)) {
            return 'KEEP_CURRENT_OR_AUDIT'
        }
    }
    $name = [IO.Path]::GetFileName($p)
    if ($name -in @('RUN_V17_PREFLIGHT.ps1','RUN_V17_PREFLIGHT.ps1.sha256.txt',
        'SERVER_STAGE_GUIDE.md','SERVER_V17_GUIDE.md','r4_closeout_evidence',
        'SPOT_120M_EVIDENCE_HOLD_20260825_161549_SHARE','health-before.json',
        'preinstall-summary.json','release_files_sha256.txt','release_identity.json')) {
        return 'KEEP_PENDING_IDENTITY_OR_EVIDENCE_REVIEW'
    }
    if ($name -match '(?i)(backup|rollback|restore|recovery|config|\.csv$|\.db$|\.sqlite(?:3)?$)') {
        return 'KEEP_PENDING_DATA_RECOVERY_REVIEW'
    }
    if ($name -match '(?i)(v?1[._]0[._]2[56]|v102[56]|a203baf|d7a1b20|ef731112|cold.backup)') {
        return 'KEEP_CURRENT_RELEASE_OR_EVIDENCE'
    }
    if ($name -match '(?i)(quarantine_manifest|quarantine_verification|cleanup|acl.repair|repair.sflops)') {
        return 'KEEP_CLEANUP_RECORD_OR_TOOL'
    }
    return 'REVIEW_RETIREMENT_CANDIDATE'
}

function Assert-OverviewPlain {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -notmatch '^[A-Za-z]:\\' -or $full.Substring(2).Contains(':')) {
        throw 'Only local ordinary filesystem paths are accepted.'
    }
    $node = [IO.DirectoryInfo]::new($full)
    while ($null -ne $node) {
        $attributes = [IO.File]::GetAttributes($node.FullName)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Reparse path is not followed.'
        }
        $node = $node.Parent
    }
}

function Get-OverviewTree {
    param([string]$Path,[int]$GroupId,[object]$State)
    $first = $State.entries.Count
    $issuesBefore = $State.issues.Count
    $bytes = 0L; $files = 0; $directories = 0
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($Path)
    while ($queue.Count -gt 0) {
        if ($State.clock.Elapsed.TotalSeconds -ge $State.max_seconds -or
            $State.entries.Count -ge $State.max_entries) {
            $State.limited = $true
            break
        }
        $current = $queue.Dequeue()
        try {
            Assert-OverviewPlain $current
            $entry = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            if (-not $entry.PSIsContainer) {
                $files++; $bytes += $entry.Length
                $State.entries.Add([pscustomobject]@{group=$GroupId;path=$entry.FullName;
                    type='file';bytes=[long]$entry.Length;last_write_utc=$entry.LastWriteTimeUtc.ToString('o')})
                continue
            }
            $directories++
            $State.entries.Add([pscustomobject]@{group=$GroupId;path=$entry.FullName;
                type='directory';bytes=$null;last_write_utc=$entry.LastWriteTimeUtc.ToString('o')})
            foreach ($child in ([IO.DirectoryInfo]::new($current)).EnumerateFileSystemInfos()) {
                if ($State.clock.Elapsed.TotalSeconds -ge $State.max_seconds -or
                    $State.entries.Count+$queue.Count -ge $State.max_entries) {
                    $State.limited = $true
                    break
                }
                if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    $State.issues.Add([pscustomobject]@{path=$child.FullName;status='REPARSE_SKIPPED'})
                    continue
                }
                $queue.Enqueue($child.FullName)
            }
        }
        catch {
            $State.issues.Add([pscustomobject]@{path=$current;status='UNREADABLE_OR_CHANGED';
                error_type=$_.Exception.GetType().Name})
        }
        if ($State.clock.Elapsed.TotalSeconds-$State.last_progress -ge 10) {
            Write-Host ('[PROGRESS] entries='+$State.entries.Count+' elapsed_seconds='+[int]$State.clock.Elapsed.TotalSeconds)
            $State.last_progress = $State.clock.Elapsed.TotalSeconds
        }
        if ($State.limited) { break }
    }
    return [pscustomobject]@{id=$GroupId;path=$Path;classification=(Get-OverviewClass $Path);
        coverage=$(if($State.limited -or $State.issues.Count -gt $issuesBefore){'PARTIAL'}else{'METADATA_ENUMERATED'});
        files=$files;directories=$directories;logical_bytes=$bytes;entries=$State.entries.Count-$first;
        deletion_authorized=$false}
}

function Write-OverviewNewFile {
    param([string]$Path,[byte[]]$Bytes)
    $stream = [IO.File]::Open($Path,'CreateNew','Write','None')
    try { $stream.Write($Bytes,0,$Bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

if ($SelfTest) {
    $checks = 0
    foreach ($case in @(
        @('C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs','KEEP_CURRENT_OR_AUDIT'),
        @('C:\ProgramData\SFLOps\tmp','KEEP_CURRENT_OR_AUDIT'),
        @('C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503','KEEP_CURRENT_OR_AUDIT'),
        @('C:\Users\user\AppData\Local\SFLCanary\runtime_validation_20260909_233747','KEEP_CURRENT_OR_AUDIT'),
        @('C:\x\backup_before_install','KEEP_PENDING_DATA_RECOVERY_REVIEW'),
        @('C:\x\production.csv','KEEP_PENDING_DATA_RECOVERY_REVIEW'),
        @('C:\x\SmartFactoryLogger_v1.0.25_a203baf.zip','KEEP_CURRENT_RELEASE_OR_EVIDENCE'),
        @('C:\x\v1026-server-stage-ready.zip','KEEP_CURRENT_RELEASE_OR_EVIDENCE'),
        @('C:\x\quarantine_manifest_before_move.json','KEEP_CLEANUP_RECORD_OR_TOOL'),
        @('C:\x\release_identity.json','KEEP_PENDING_IDENTITY_OR_EVIDENCE_REVIEW'),
        @('C:\x\r4_closeout_evidence','KEEP_PENDING_IDENTITY_OR_EVIDENCE_REVIEW'),
        @('C:\x\RUN_V17_PREFLIGHT.ps1','KEEP_PENDING_IDENTITY_OR_EVIDENCE_REVIEW'),
        @('C:\x\release_private_unsigned_v1_0_19_R1','REVIEW_RETIREMENT_CANDIDATE'),
        @('C:\Users\user\AppData\Roaming\SmartFactoryLogger-not-runtime','REVIEW_RETIREMENT_CANDIDATE')
    )) {
        if ((Get-OverviewClass $case[0]) -cne $case[1]) { throw 'Classification regression.' }
        $checks++
    }
    $fixture = Join-Path $PSScriptRoot 'fixtures\quarantine'
    $state = @{entries=[Collections.Generic.List[object]]::new();issues=[Collections.Generic.List[object]]::new();
        clock=[Diagnostics.Stopwatch]::StartNew();max_seconds=30;max_entries=100;limited=$false;last_progress=0}
    $tree = Get-OverviewTree $fixture 1 $state
    if ($tree.files -ne 2 -or $tree.directories -ne 2 -or $tree.coverage -cne 'METADATA_ENUMERATED' -or $tree.deletion_authorized) {
        throw 'Readonly fixture enumeration differs.'
    }
    $checks++
    $state.max_entries=1; $state.entries.Clear(); $state.limited=$false
    $partial = Get-OverviewTree $fixture 2 $state
    if ($partial.coverage -cne 'PARTIAL' -or -not $state.limited) { throw 'Limit must report partial.' }
    $checks++
    Write-Output ('CLEANUP_OVERVIEW_SELF_TEST_PASS checks='+$checks+' source_writes=0')
    return
}

$native = [IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
    -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Use native administrator x64 Windows PowerShell 5.1.'
}
$inventoryRoot = 'C:\ProgramData\SFLOps\inventory'
Assert-OverviewPlain $inventoryRoot
# Validate existing boundary only. Do not reset ACLs, take ownership or repair it.
$acl = [IO.Directory]::GetAccessControl($inventoryRoot)
$rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
if (-not $acl.AreAccessRulesProtected -or
    $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544') -or
    $rules.Count -ne 2 -or @($rules | Where-Object {
        $_.IdentityReference.Value -notin @('S-1-5-18','S-1-5-32-544') -or $_.AccessControlType -ne 'Allow' -or
        $_.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
        [int]$_.InheritanceFlags -ne 3 -or [int]$_.PropagationFlags -ne 0
    }).Count -gt 0 -or @($rules.IdentityReference.Value | Select-Object -Unique).Count -ne 2) {
    throw 'Inventory boundary differs; no ACL change or collection was performed.'
}
$reportDirectory = Join-Path $inventoryRoot ('cleanup-overview-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
if (Test-Path -LiteralPath $reportDirectory) { throw 'Report path collision.' }
$null = [IO.Directory]::CreateDirectory($reportDirectory)
Assert-OverviewPlain $reportDirectory
Write-Host ('[OUTPUT] '+$reportDirectory)
Write-Host '[READ ONLY SOURCES] File names, sizes and timestamps only. No deletion, hashes of source data, app queries, restart or ACL changes.'

$state = @{entries=[Collections.Generic.List[object]]::new();issues=[Collections.Generic.List[object]]::new();
    clock=[Diagnostics.Stopwatch]::StartNew();max_seconds=300;max_entries=100000;limited=$false;last_progress=0}
$groups = [Collections.Generic.List[object]]::new()
$targets = [Collections.Generic.List[string]]::new()
$discovery = [Collections.Generic.List[object]]::new()
# Parents are enumerated one level only to obtain review groups. Never delete these parents.
foreach ($parent in @('C:\Users\user\Desktop\SmartFactory',
    'C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302',
    'C:\Users\user\Desktop\SmartFactoryLogger_Evidence','C:\Users\user\AppData\Local\SFLCanary','C:\SFLCanary')) {
    try {
        Assert-OverviewPlain $parent
        foreach ($item in Get-ChildItem -LiteralPath $parent -Force -ErrorAction Stop) {
            if ($targets.Count -ge 5000) { throw 'Top-level item budget reached.' }
            $targets.Add($item.FullName)
        }
        $discovery.Add([pscustomobject]@{path=$parent;status='DIRECT_ITEMS_LISTED'})
    } catch {
        $discovery.Add([pscustomobject]@{path=$parent;status='UNREADABLE_MISSING_OR_LIMIT';error_type=$_.Exception.GetType().Name})
    }
}
foreach ($name in @('SFL-76B317D0A2901C6EFC649404211C8109','SFL-9B645BE54EB0C6C7A7F1C482248174EB',
    'SFL-B63483AD9AB07924E5F291076F911BDA','SFL-v1023-v11-8C1B97EF0F3BA3DAC26F38CD7B8D5656',
    'SFL26S-29aee83c36044389828d6d20eb645503','SFL26S-ae681d39b54a40c59da518292d259f95')) {
    $targets.Add('C:\ProgramData\'+$name)
}
foreach ($name in @('sfl-post-merge-smoke','sfl-rollover-smoke','spot-raw-capture','capture-spot-raw.ps1',
    'plc-transient-check-20260624-103946.json','pr65-server-readonly-smoke-20260624T011822Z.json',
    'qa_spot_live_server.ps1','sfl-spot-live-server-qa-20260701-094301.json','sfl-spot-live-server-qa.json',
    'sfl-spot-runtime-check-20260617-134240.json','sfl-spot-temperature-diagnostics-20260617-133519.json','spot-unattended-capture.ps1')) {
    $targets.Add('C:\tmp\'+$name)
}
$targets.Add('C:\Users\user\AppData\Local\smart-factory-logger-v2-updater')
$targets.Add('C:\ProgramData\SFLOps')
foreach ($target in @($targets | Sort-Object -Unique)) {
    $id = $groups.Count+1
    if ((Get-OverviewClass $target) -ceq 'KEEP_CURRENT_OR_AUDIT') {
        $groups.Add([pscustomobject]@{id=$id;path=$target;classification='KEEP_CURRENT_OR_AUDIT';
            coverage='INTENTIONALLY_NOT_ENUMERATED';files=$null;directories=$null;logical_bytes=$null;deletion_authorized=$false})
        continue
    }
    if (($id % 25) -eq 1) { Write-Host ('[GROUP '+$id+'/'+$targets.Count+'] Metadata enumeration') }
    $groups.Add((Get-OverviewTree $target $id $state))
}
$result = [pscustomobject][ordered]@{
    schema_version='sfl-cleanup-overview-v1'
    result=$(if($state.limited -or $state.issues.Count -gt 0 -or @($discovery | Where-Object status -ne 'DIRECT_ITEMS_LISTED').Count -gt 0){'PARTIAL_INVENTORY_NOT_DELETE_READY'}else{'SCOPED_METADATA_INVENTORY_NOT_DELETE_READY'})
    recorded_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=[Math]::Round($state.clock.Elapsed.TotalSeconds,1)
    report_directory=$reportDirectory;groups=$groups.ToArray();discovery=$discovery.ToArray();issues=$state.issues.ToArray();entries=$state.entries.ToArray()
    protected_operational_paths=@('C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2',
        'C:\Users\user\AppData\Roaming\SmartFactoryLogger','C:\Users\user\AppData\Roaming\smart-factory-logger-v2')
    deletion_performed=$false;move_performed=$false;acl_changes=$false;product_api_queries=$false;app_restart=$false
    limitations=@('Classification is advisory; unknown and unique historical evidence is not authorized for disposal.',
        'Metadata is non-atomic and does not prove current non-use or byte equality. Hard links and allocated disk space are not measured.',
        'No source content, task/service/shortcut dependencies, custom data paths or other users/drives are inspected.',
        'Reparse paths are skipped; concurrent hostile path replacement is not fully guarded.',
        '5-minute / 100000-entry budgets are checked between filesystem operations; blocked OS calls cannot be preempted.',
        'Parent discovery is restricted to the listed paths. No server-wide completeness or space-reclaim promise.')
}
$jsonPath = Join-Path $reportDirectory 'server-inventory.json'
Write-OverviewNewFile $jsonPath ([Text.UTF8Encoding]::new($false).GetBytes(($result | ConvertTo-Json -Depth 8)))
$hash = (Get-FileHash -LiteralPath $jsonPath -Algorithm SHA256).Hash
Write-OverviewNewFile ($jsonPath+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($hash+"`r`n"))
Write-Host ('[RESULT] '+$jsonPath)
Write-Host ('[SHA256] '+$hash)
Write-Host ('[SUMMARY] groups='+$groups.Count+' entries='+$state.entries.Count+' issues='+$state.issues.Count+' result='+$result.result)
Write-Host '[DONE] Return the JSON and its SHA256 sidecar to the developer. Private path metadata; do not publish. No deletion was performed.'
