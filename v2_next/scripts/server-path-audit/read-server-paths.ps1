& {
    # Metadata-only discovery. No server helper, archive, or application is executed.
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    function Get-AuditPlainPathState {
        param([string]$Path)
        if ($Path -notmatch '^[A-Za-z]:\\' -or $Path.Substring(2).Contains(':') -or
            $Path -match '[\x00-\x1F<>"|?*]' -or $Path.Length -gt 240) {
            return 'UNSUPPORTED_PATH'
        }
        try {
            $full = [IO.Path]::GetFullPath($Path)
            if ($full.TrimEnd('\') -ine $Path.TrimEnd('\')) { return 'NONCANONICAL_PATH' }
            $parts = [Collections.Generic.List[string]]::new()
            $node = [IO.FileInfo]::new($full)
            while ($null -ne $node) {
                $parts.Add($node.FullName)
                if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
            }
            for ($i = $parts.Count - 1; $i -ge 0; $i--) {
                $attrs = [IO.File]::GetAttributes($parts[$i])
                if (($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return 'REPARSE_SKIPPED' }
            }
            return 'PLAIN'
        } catch {
            $cause = $_.Exception
            while ($null -ne $cause.InnerException) { $cause = $cause.InnerException }
            if ($cause -is [IO.FileNotFoundException] -or $cause -is [IO.DirectoryNotFoundException]) {
                return 'ABSENT'
            }
            return 'UNREADABLE'
        }
    }

    function Get-AuditDirectoryWindow {
        param([string]$Path, [string]$Pattern = '', [int]$Limit = 5000)
        $state = Get-AuditPlainPathState $Path
        $found = [Collections.Generic.List[object]]::new()
        $summary = [ordered]@{
            path = $Path; state = $state; observed_entries = 0
            immediate_files = 0; immediate_directories = 0; immediate_file_bytes = [long]0
            reparse_entries = 0; markers = @(); matches = @()
            recursive = $false; total_tree_size_known = $false; deletion_approved = $false
        }
        if ($state -cne 'PLAIN') { return [pscustomobject]$summary }
        $enumerator = $null
        try {
            $attrs = [IO.File]::GetAttributes($Path)
            if (($attrs -band [IO.FileAttributes]::Directory) -eq 0) {
                $file = [IO.FileInfo]::new($Path)
                $summary.state = 'FILE_METADATA_ONLY'
                $summary.immediate_files = 1; $summary.immediate_file_bytes = $file.Length
                return [pscustomobject]$summary
            }
            $markers = [Collections.Generic.List[string]]::new()
            $enumerator = [IO.DirectoryInfo]::new($Path).EnumerateFileSystemInfos().GetEnumerator()
            while ($enumerator.MoveNext()) {
                if ($summary.observed_entries -ge $Limit) { $summary.state = 'ENTRY_LIMIT_PARTIAL'; break }
                $item = $enumerator.Current
                $summary.observed_entries++
                $reparse = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
                if ($reparse) { $summary.reparse_entries++ }
                elseif ($item -is [IO.DirectoryInfo]) { $summary.immediate_directories++ }
                else { $summary.immediate_files++; $summary.immediate_file_bytes += $item.Length }
                if ($item.Name -cin @('result.json','hold.json','intent.json','preflight-result.json',
                    'files.manifest.tsv','backup','restore','payload','release','kit','sanitized_share','raw_private')) {
                    $markers.Add($item.Name)
                }
                if ($Pattern -ne '' -and $item.Name -match $Pattern) {
                    if ($found.Count -lt 100) {
                        $found.Add([pscustomobject]@{path=$item.FullName;reparse=$reparse})
                    } else { $summary.state = 'MATCH_LIMIT_PARTIAL' }
                }
            }
            $summary.markers = @($markers.ToArray())
            if ($summary.state -ceq 'PLAIN') { $summary.state = 'DIRECT_CHILDREN_ONLY' }
        } catch { $summary.state = 'ENUMERATION_ERROR_PARTIAL' }
        finally { if ($null -ne $enumerator) { $enumerator.Dispose() } }
        $summary.matches = @($found.ToArray())
        return [pscustomobject]$summary
    }

    function Get-AuditProtectionClass {
        param([string]$Path)
        foreach ($root in @(
            'C:\Users\user\AppData\Roaming\SmartFactoryLogger',
            'C:\Users\user\AppData\Roaming\smart-factory-logger-v2',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2')) {
            if ($Path -ieq $root -or $Path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) {
                return 'PROTECT_RUNTIME_DATA_OR_INSTALL'
            }
        }
        return 'REVIEW_ONLY_NOT_DELETE_APPROVED'
    }

    $native = [IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native) {
        throw 'Use native x64 Windows PowerShell 5.1.'
    }
    $savedAuditModules = $env:PSModulePath; $savedAuditPath = $env:PATH
    $auditClock = [Diagnostics.Stopwatch]::StartNew()
    try {
        $env:PSModulePath = [IO.Path]::GetDirectoryName($native)+'\Modules'
        $env:PATH = [Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        $roots = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($root in @(
            'C:\Users\user\Desktop\SmartFactory','C:\Users\user\Desktop\SmartFactoryLogger_Evidence',
            'C:\SFLCanary','C:\Users\user\AppData\Local\SFLCanary',
            'C:\Users\user\AppData\Roaming\SmartFactoryLogger',
            'C:\Users\user\AppData\Roaming\smart-factory-logger-v2',
            'C:\Users\user\AppData\Local\SmartFactoryLogger',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2\resources\backend\logs',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2\resources\backend\snapshots',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2\resources\backend\config.ini',
            'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2\resources\backend\config\config.ini',
            'C:\Users\user\AppData\Local\Temp\SmartFactoryLogger',
            'C:\Users\user\AppData\Local\Temp\debug_electron.log',
            'C:\Users\user\AppData\Local\Temp\smart-factory-startup-traces',
            'C:\ProgramData\SFLOps')) { $null = $roots.Add($root) }

        $searches = @(
            @('C:\','^(SFL|SmartFactory|smart-factory)'),
            @('C:\ProgramData','^SFL'),
            @('C:\Users\user\Desktop','^(SFL|SmartFactory|smart-factory|v102[0-9])'),
            @('C:\Users\user\Downloads','^(SFL|SmartFactory|smart-factory|v102[0-9])'),
            @('C:\Users\user\AppData\Local','^(SFL|SmartFactory|smart-factory)'),
            @('C:\Users\user\AppData\Roaming','^(SFL|SmartFactory|smart-factory)'),
            @('C:\Users\user\AppData\Local\Temp','^(SFL|SmartFactory|smart-factory|spot-|runtime_validation_|debug_electron)'),
            @('C:\Windows\Temp','^(SFL|SmartFactory|smart-factory|spot-|runtime_validation_|debug_electron)'),
            @('C:\tmp','^(sfl-|spot-|capture-spot|qa_spot|plc-transient-check|pr65-server-readonly)'),
            @('C:\temp','^(SFL|SmartFactory|smart-factory|spot-|runtime_validation_|debug_electron)')
        )
        $searchResults = [Collections.Generic.List[object]]::new()
        $details = [Collections.Generic.List[object]]::new()
        $partial = $false
        foreach ($search in $searches) {
            if ($auditClock.Elapsed.TotalSeconds -gt 90) { $partial = $true; break }
            Write-Host ('[DISCOVER] '+$search[0]+' elapsed='+[Math]::Round($auditClock.Elapsed.TotalSeconds,1)+'s')
            $window = Get-AuditDirectoryWindow -Path $search[0] -Pattern $search[1]
            $searchResults.Add($window)
            foreach ($match in $window.matches) {
                if ($roots.Count -ge 150) { $partial = $true; break }
                # A reparse candidate is reported below, never enumerated through.
                $null = $roots.Add($match.path)
            }
        }
        foreach ($root in @($roots | Sort-Object)) {
            if ($auditClock.Elapsed.TotalSeconds -gt 90) { $partial = $true; break }
            Write-Host ('[INSPECT] '+$root)
            $window = Get-AuditDirectoryWindow -Path $root
            $details.Add([pscustomobject]@{protection=Get-AuditProtectionClass $root;metadata=$window})
        }
        $runtime = [Collections.Generic.List[object]]::new()
        $runtimeStatus = 'READ_ONLY_SNAPSHOT'
        try {
            foreach ($process in @(Get-Process | Where-Object { $_.ProcessName -cin @('smart-factory','SmartFactoryBackend') })) {
                $runtime.Add([pscustomobject]@{name=$process.ProcessName;pid=$process.Id;path=$process.Path})
                if ([string]::IsNullOrWhiteSpace($process.Path)) { $runtimeStatus = 'PARTIAL_OR_UNREADABLE' }
            }
        } catch { $runtimeStatus = 'PARTIAL_OR_UNREADABLE' }
        $drive = [IO.DriveInfo]::new('C:\')
        [pscustomobject][ordered]@{
            result='SERVER_PATH_DISCOVERY_ONLY_NOT_DELETE_READY'
            coverage='BOUNDED_DIRECT_CHILD_DISCOVERY_NOT_EXHAUSTIVE'
            checked_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$auditClock.Elapsed.TotalSeconds
            scan_budget_or_root_limit_reached=$partial;searches=@($searchResults.ToArray());paths=@($details.ToArray())
            runtime_status=$runtimeStatus;runtime=@($runtime.ToArray())
            free_gib=[Math]::Round($drive.AvailableFreeSpace/1GB,2)
            file_contents_read=$false;archives_opened=$false;recursive_scan=$false
            source_file_writes_performed=$false;deletion_performed=$false;move_performed=$false
            application_restart_performed=$false;local_api_queries=$false
            exclusions=@('Other users/drives and UNC paths not scanned','No task/service/shortcut references checked',
                'No file hashes, backup completeness, retention or file handle ownership checked',
                'Custom config/env paths not resolved; renamed or deeper unknown artifacts may be missed',
                'Byte totals cover direct regular files only, not subtrees or reclaimable disk space',
                'Reparse and unreadable paths are unresolved, not absent; no hostile path-race guarantee',
                '90-second budget checked between directories; a blocked OS enumeration cannot be preempted')
        } | ConvertTo-Json -Depth 9
        Write-Host '[DONE] Metadata only. Keep app running; do not delete or move based on this output alone.'
    } finally {
        $env:PSModulePath=$savedAuditModules; $env:PATH=$savedAuditPath
    }
}
