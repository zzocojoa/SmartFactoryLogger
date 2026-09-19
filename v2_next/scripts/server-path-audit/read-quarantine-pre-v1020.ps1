& {
    # Fixed historical input; report only. Never dot-source or execute inspected files.
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'

    function Assert-QPlain {
        param([string]$Path)
        if ($Path -notmatch '^[A-Za-z]:\\' -or $Path.Substring(2).Contains(':') -or
            $Path -match '[\x00-\x1F<>"|?*]' -or $Path.Length -gt 259 -or
            [IO.Path]::GetFullPath($Path).TrimEnd('\') -ine $Path.TrimEnd('\')) {
            throw 'Unsupported or noncanonical local path.'
        }
        $nodes = [Collections.Generic.List[string]]::new()
        $node = [IO.FileInfo]::new($Path)
        while ($null -ne $node) {
            $nodes.Add($node.FullName)
            if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
        }
        for ($i = $nodes.Count - 1; $i -ge 0; $i--) {
            if (([IO.File]::GetAttributes($nodes[$i]) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse path not inspected.'
            }
        }
    }

    function Assert-QRelative {
        param([string]$Path)
        if ([string]::IsNullOrWhiteSpace($Path) -or [IO.Path]::IsPathRooted($Path) -or
            $Path -match '[:/\x00-\x1F<>"|?*]') { throw 'Invalid manifest relative path.' }
        foreach ($part in $Path.Split('\')) {
            if ($part -in @('', '.', '..') -or $part -match '[. ]$' -or
                $part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') {
                throw 'Ambiguous manifest path component.'
            }
        }
    }

    function Get-QHash {
        param([IO.Stream]$Stream)
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $Stream.Position = 0
            return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-', '')
        } finally { $sha.Dispose() }
    }

    function Open-QPinned {
        param([string]$Path, [long]$Length, [string]$Sha256,
            [Collections.Generic.List[IDisposable]]$Pins)
        Assert-QPlain $Path
        $stream = [IO.File]::Open($Path, 'Open', 'Read', 'Read')
        try {
            if ($stream.Length -ne $Length -or (Get-QHash $stream) -cne $Sha256) {
                throw 'File length or SHA256 differs from the reviewed manifest.'
            }
            $Pins.Add($stream)
            return ,$stream
        } catch { $stream.Dispose(); throw }
    }

    function Read-QText {
        param([IO.Stream]$Stream)
        if ($Stream.Length -gt 1MB) { throw 'Text size limit reached.' }
        $Stream.Position = 0
        $reader = [IO.StreamReader]::new($Stream, [Text.UTF8Encoding]::new($false, $true), $true, 4096, $true)
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    }

    function Get-QContract {
        param([object]$Manifest)
        $tops = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $files = @{}; $dirs = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $total = [long]0
        foreach ($top in @($Manifest.top_level_items)) {
            Assert-QRelative $top
            if ($top.Contains('\') -or -not $tops.Add($top)) { throw 'Invalid or duplicate top-level item.' }
        }
        foreach ($row in @($Manifest.files)) {
            $relative = [string]$row.relative_path
            Assert-QRelative $relative
            if (-not $tops.Contains($relative.Split('\')[0]) -or $files.ContainsKey($relative) -or
                $row.length -isnot [ValueType] -or $row.length -lt 0 -or
                ($row.length -isnot [int] -and $row.length -isnot [long]) -or
                [string]$row.sha256 -cnotmatch '^[A-F0-9]{64}$') { throw 'Invalid manifest row.' }
            $files[$relative] = $row
            $total += [long]$row.length
            $parent = [IO.Path]::GetDirectoryName($relative)
            while (-not [string]::IsNullOrEmpty($parent)) {
                $null = $dirs.Add($parent); $parent = [IO.Path]::GetDirectoryName($parent)
            }
        }
        foreach ($dir in $dirs) { if ($files.ContainsKey($dir)) { throw 'File/directory conflict.' } }
        foreach ($top in $tops) {
            if (-not $files.ContainsKey($top) -and -not $dirs.Contains($top)) { throw 'Unrepresented top item.' }
        }
        foreach ($keep in @($Manifest.critical_keep)) {
            Assert-QRelative $keep
            if ($tops.Contains($keep.Split('\')[0])) { throw 'Keep item overlaps moved items.' }
        }
        if ($total -ne $Manifest.total_bytes -or $files.Count -ne $Manifest.file_count) {
            throw 'Manifest counts or byte total differ.'
        }
        return [pscustomobject]@{tops=$tops;files=$files;dirs=$dirs;bytes=$total}
    }

    function Get-QTree {
        param([string]$Root, [int]$MaxDepth = 30, [int]$MaxEntries = 3000, [int]$Seconds = 60)
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $rows = [Collections.Generic.List[object]]::new()
        $issues = [Collections.Generic.List[object]]::new()
        $queue = [Collections.Generic.Queue[object]]::new()
        $queue.Enqueue([pscustomobject]@{path=$Root;depth=0})
        while ($queue.Count -gt 0) {
            if ($clock.Elapsed.TotalSeconds -gt $Seconds -or $rows.Count -ge $MaxEntries) {
                $issues.Add([pscustomobject]@{path=$Root;kind='BUDGET_PARTIAL'}); break
            }
            $next = $queue.Dequeue(); $enumerator = $null
            try {
                Assert-QPlain $next.path
                $enumerator = [IO.DirectoryInfo]::new($next.path).EnumerateFileSystemInfos().GetEnumerator()
                while ($enumerator.MoveNext()) {
                    if ($rows.Count -ge $MaxEntries -or $clock.Elapsed.TotalSeconds -gt $Seconds) {
                        $issues.Add([pscustomobject]@{path=$next.path;kind='BUDGET_PARTIAL'}); break
                    }
                    $item = $enumerator.Current
                    $relative = $item.FullName.Substring($Root.TrimEnd('\').Length + 1)
                    if (-not $item.FullName.StartsWith($Root.TrimEnd('\')+'\', [StringComparison]::OrdinalIgnoreCase)) {
                        throw 'Enumeration escaped root.'
                    }
                    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                        $issues.Add([pscustomobject]@{path=$item.FullName;kind='REPARSE_SKIPPED'}); continue
                    }
                    $directory = $item -is [IO.DirectoryInfo]
                    $rows.Add([pscustomobject]@{relative=$relative;path=$item.FullName;directory=$directory;
                        length=$(if ($directory) {0L} else {$item.Length});write_ticks=$item.LastWriteTimeUtc.Ticks})
                    if ($directory) {
                        if ($next.depth -lt $MaxDepth) {
                            $queue.Enqueue([pscustomobject]@{path=$item.FullName;depth=$next.depth+1})
                        } else { $issues.Add([pscustomobject]@{path=$item.FullName;kind='DEPTH_NOT_INSPECTED'}) }
                    }
                }
            } catch { $issues.Add([pscustomobject]@{path=$next.path;kind='UNREADABLE_OR_UNSUPPORTED'}) }
            finally { if ($null -ne $enumerator) { $enumerator.Dispose() } }
        }
        return [pscustomobject]@{rows=$rows.ToArray();issues=$issues.ToArray();complete=($issues.Count -eq 0)}
    }

    function Compare-QTree {
        param([object]$Tree, [object]$Contract, [string[]]$Metadata)
        $found = @{}; $unknown = [Collections.Generic.List[object]]::new()
        foreach ($row in @($Tree.rows)) {
            if ($found.ContainsKey($row.relative)) { throw 'Duplicate filesystem relative path.' }
            $found[$row.relative] = $row
            if ($row.directory) {
                if (-not $Contract.dirs.Contains($row.relative)) {
                    $unknown.Add([pscustomobject]@{relative=$row.relative;kind='DIRECTORY_NOT_DESCRIBED_BY_MANIFEST'})
                }
            } elseif (-not $Contract.files.ContainsKey($row.relative) -and $row.relative -cnotin $Metadata) {
                $unknown.Add([pscustomobject]@{relative=$row.relative;kind='EXTRA_FILE'})
            }
        }
        $missing = @($Contract.files.Keys | Where-Object {
            -not $found.ContainsKey($_) -or $found[$_].directory
        } | Sort-Object)
        return [pscustomobject]@{missing=$missing;unlisted=$unknown.ToArray()}
    }

    function Find-QReferences {
        param([AllowNull()][string]$Text, [string[]]$Needles)
        # Substring matches are conservative leads, not proof of active use. No raw text is returned.
        if ([string]::IsNullOrEmpty($Text)) { return }
        $normal = $Text.Replace('/', '\')
        foreach ($needle in $Needles) {
            if ($normal.IndexOf($needle, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $needle }
        }
    }

    function Get-QSystemReferences {
        param([string[]]$Needles)
        $hits = [Collections.Generic.List[object]]::new(); $coverage = [Collections.Generic.List[object]]::new()
        foreach ($spec in @(@('process','Win32_Process',@('ExecutablePath','CommandLine'),'ProcessId'),
                @('service','Win32_Service',@('PathName'),'Name'),
                @('startup','Win32_StartupCommand',@('Command','Location'),'Name'))) {
            $count = 0; $unreadable = 0; $status = 'SNAPSHOT_QUERIED'; $omitted = 0
            try {
                foreach ($row in @(Get-CimInstance -ClassName $spec[1] -OperationTimeoutSec 15 -ErrorAction Stop)) {
                    $count++
                    foreach ($field in $spec[2]) {
                        $value = $row.PSObject.Properties[$field]
                        if ($null -eq $value -or $null -eq $value.Value) { $unreadable++; continue }
                        $matched = @(Find-QReferences ([string]$value.Value) $Needles)
                        if ($matched.Count -gt 0) {
                            if ($hits.Count -lt 200) {
                                $hits.Add([pscustomobject]@{kind=$spec[0];id=[string]$row.($spec[3]);field=$field;matched_names=$matched})
                            } else { $omitted++ }
                        }
                    }
                }
            } catch { $status = 'QUERY_ERROR_PARTIAL' }
            $coverage.Add([pscustomobject]@{scope=$spec[0];status=$status;rows=$count;null_fields=$unreadable;omitted_hits=$omitted})
        }
        $count=0; $unknown=0; $omitted=0; $status='SNAPSHOT_QUERIED'
        try {
            foreach ($task in @(Get-ScheduledTask -ErrorAction Stop)) {
                $count++
                foreach ($action in @($task.Actions)) {
                    if ($null -eq $action.PSObject.Properties['Execute']) { $unknown++; continue }
                    foreach ($field in @('Execute','Arguments','WorkingDirectory')) {
                        $property=$action.PSObject.Properties[$field]
                        if ($null -eq $property) { $unknown++; continue }
                        $matched=@(Find-QReferences ([string]$property.Value) $Needles)
                        if ($matched.Count -gt 0) {
                            if ($hits.Count -lt 200) {
                                $hits.Add([pscustomobject]@{kind='task';id=$task.TaskPath+$task.TaskName;field=$field;matched_names=$matched})
                            } else { $omitted++ }
                        }
                    }
                }
            }
        } catch { $status='QUERY_ERROR_PARTIAL' }
        $coverage.Add([pscustomobject]@{scope='scheduled_tasks';status=$status;rows=$count;non_exec_or_missing_action_fields=$unknown;omitted_hits=$omitted})
        return [pscustomobject]@{coverage=$coverage.ToArray();hits=$hits.ToArray()}
    }

    function Get-QFileReferences {
        param([string[]]$Needles, [object[]]$Scopes)
        $hits=[Collections.Generic.List[object]]::new(); $coverage=[Collections.Generic.List[object]]::new()
        $shell=$null; $bytes=[long]0; $clock=[Diagnostics.Stopwatch]::StartNew()
        try {
            foreach ($scope in $Scopes) {
                Write-Host ('[REFERENCES] '+$scope.path)
                if ($clock.Elapsed.TotalSeconds -gt 120) {
                    $coverage.Add([pscustomobject]@{path=$scope.path;status='BUDGET_NOT_INSPECTED'}); continue
                }
                $tree=Get-QTree $scope.path -MaxDepth $scope.depth -MaxEntries 3000 -Seconds 15
                $checked=0; $errors=0; $skipped=0; $omitted=0
                foreach ($file in @($tree.rows | Where-Object {-not $_.directory})) {
                    $extension=[IO.Path]::GetExtension($file.relative).ToLowerInvariant()
                    if (($scope.kind -ceq 'shortcut' -and $extension -cne '.lnk') -or
                        ($scope.kind -ceq 'text' -and $extension -cnotin @('.ps1','.psm1','.cmd','.bat','.txt','.md','.json'))) { continue }
                    if ($clock.Elapsed.TotalSeconds -gt 120 -or $file.length -gt 1MB -or $bytes+$file.length -gt 32MB) { $skipped++; continue }
                    $stream=$null; $link=$null
                    try {
                        Assert-QPlain $file.path
                        $stream=[IO.File]::Open($file.path,'Open','Read','Read')
                        if ($stream.Length -gt 1MB -or $bytes+$stream.Length -gt 32MB) { $skipped++; continue }
                        $bytes+=$stream.Length
                        if ($scope.kind -ceq 'shortcut') {
                            if ($null -eq $shell) { $shell=New-Object -ComObject WScript.Shell }
                            # Existing local .lnk only, never Save/Run/Resolve its target.
                            $link=$shell.CreateShortcut($file.path)
                            $value=[string]$link.TargetPath+' '+[string]$link.Arguments+' '+[string]$link.WorkingDirectory
                        } else { $value=Read-QText $stream }
                        $matched=@(Find-QReferences $value $Needles); $checked++
                        if ($matched.Count -gt 0) {
                            if ($hits.Count -lt 200) {
                                $hits.Add([pscustomobject]@{kind=$scope.kind;path=$file.path;matched_names=$matched;active_use_proven=$false})
                            } else { $omitted++ }
                        }
                    } catch { $errors++ }
                    finally {
                        if ($null -ne $stream) { $stream.Dispose() }
                        if ($null -ne $link) { $null=[Runtime.InteropServices.Marshal]::FinalReleaseComObject($link) }
                    }
                }
                $coverage.Add([pscustomobject]@{path=$scope.path;kind=$scope.kind;depth=$scope.depth;
                    enumeration_complete=$tree.complete;enumeration_issues=$tree.issues;
                    checked_files=$checked;read_errors=$errors;size_or_budget_skipped=$skipped;omitted_hits=$omitted})
            }
        } finally { if ($null -ne $shell) { $null=[Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) } }
        return [pscustomobject]@{coverage=$coverage.ToArray();hits=$hits.ToArray();bytes_read=$bytes}
    }

    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
        -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Use administrator native x64 Windows PowerShell 5.1.'
    }
    $savedQPath=$env:PATH; $savedQModules=$env:PSModulePath
    $pins=[Collections.Generic.List[IDisposable]]::new(); $clock=[Diagnostics.Stopwatch]::StartNew()
    $root='C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302'
    $specs=@(
        @('quarantine_manifest_before_move.json',198366L,'F918CAF4ABCC65124E86F50D2DD79DFCC962ECC221FD8E0997DB2402FE468752'),
        @('quarantine_verification_after_move.json',656L,'4CB03191D3E8816A713EA4A65D6EC03FDAC6FB94606E06B62B7F4EB1D9893D14'),
        @('quarantine_verification_after_move_R1_1.json',1628L,'4D6A6984ED3B1E2AEEEA58C9C8403FC0E3543F649EBE296E5BB2DCB671C20671'))
    try {
        $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
        Write-Host '[1/5] Pin the three reviewed historical JSONs; no app/API/camera query.'
        $documents=@{}; $metadata=[Collections.Generic.List[string]]::new()
        foreach ($spec in $specs) {
            $stream=Open-QPinned (Join-Path $root $spec[0]) $spec[1] $spec[2] $pins
            $documents[$spec[0]]=ConvertFrom-Json -InputObject (Read-QText $stream)
            $metadata.Add($spec[0]); $sidecar=Join-Path $root ($spec[0]+'.sha256.txt')
            Assert-QPlain $sidecar
            $side=[IO.File]::Open($sidecar,'Open','Read','Read'); $pins.Add($side)
            if ($side.Length -gt 70 -or (Read-QText $side) -cnotmatch ('\A'+$spec[2]+'(?:\r?\n)?\z')) {
                throw 'Historical SHA256 sidecar differs.'
            }
            $metadata.Add($spec[0]+'.sha256.txt')
        }
        $manifest=$documents[$specs[0][0]]; $receipt=$documents[$specs[2][0]]
        if ($manifest.quarantine_root -cne $root -or $manifest.file_count -ne 558 -or
            $manifest.total_bytes -ne 1077165719L -or @($manifest.top_level_items).Count -ne 136 -or
            $receipt.source_manifest_sha256 -cne $specs[0][2] -or $receipt.superseded_verification_sha256 -cne $specs[1][2]) {
            throw 'Historical receipt binding differs.'
        }
        $contract=Get-QContract $manifest
        Write-Host '[2/5] Enumerate the quarantine only; reparse paths are not followed.'
        $before=Get-QTree $root
        $comparison=Compare-QTree $before $contract $metadata.ToArray()
        Write-Host '[3/5] Rehash 558 retained files (about 1.08 GB); originals are read-locked until completion.'
        $failed=[Collections.Generic.List[object]]::new(); $verified=0; $verifiedBytes=[long]0; $attempted=0
        foreach ($relative in @($contract.files.Keys | Sort-Object)) {
            if ($clock.Elapsed.TotalSeconds -gt 300) {
                $failed.Add([pscustomobject]@{relative='';kind='HASH_BUDGET_PARTIAL'}); break
            }
            $attempted++; $row=$contract.files[$relative]
            try {
                $null=Open-QPinned (Join-Path $root $relative) $row.length $row.sha256 $pins
                $verified++; $verifiedBytes+=$row.length
            } catch {
                $failed.Add([pscustomobject]@{relative=$relative;kind='MISSING_CHANGED_UNREADABLE_OR_REPARSE'})
            }
            if ($attempted % 50 -eq 0) { Write-Host ('[HASH] checked='+$attempted+'/558 elapsed='+[Math]::Round($clock.Elapsed.TotalSeconds,1)+'s') }
        }
        Write-Host '[4/5] Read bounded references. Command lines and document contents are never printed.'
        $needles=@($manifest.top_level_items)+@('pre_v1020_quarantine_20260813_092302','SmartFactory_Archive')
        $system=Get-QSystemReferences $needles
        $scopes=@(
            [pscustomobject]@{path='C:\Users\user\Desktop';depth=0;kind='shortcut'},
            [pscustomobject]@{path='C:\Users\Public\Desktop';depth=0;kind='shortcut'},
            [pscustomobject]@{path='C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
            [pscustomobject]@{path='C:\ProgramData\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
            [pscustomobject]@{path='C:\Users\user\Desktop\SmartFactory';depth=0;kind='text'})
        foreach ($stage in @('SFL-76B317D0A2901C6EFC649404211C8109','SFL-9B645BE54EB0C6C7A7F1C482248174EB',
                'SFL-B63483AD9AB07924E5F291076F911BDA','SFL-v1023-v11-8C1B97EF0F3BA3DAC26F38CD7B8D5656',
                'SFL26S-29aee83c36044389828d6d20eb645503','SFL26S-ae681d39b54a40c59da518292d259f95')) {
            $scopes += [pscustomobject]@{path=('C:\ProgramData\'+$stage);depth=3;kind='text'}
        }
        $fileRefs=Get-QFileReferences $needles $scopes
        Write-Host '[5/5] Re-enumerate the pinned quarantine and report; deletion stays unauthorized.'
        $after=Get-QTree $root
        $finalComparison=Compare-QTree $after $contract $metadata.ToArray()
        $beforeRows=@($before.rows | ForEach-Object { $_ | ConvertTo-Json -Compress })
        $afterRows=@($after.rows | ForEach-Object { $_ | ConvertTo-Json -Compress })
        $changes=@(Compare-Object -ReferenceObject $beforeRows -DifferenceObject $afterRows)
        $matches=($verified -eq 558 -and $verifiedBytes -eq 1077165719L -and $failed.Count -eq 0 -and
            $before.complete -and $after.complete -and $comparison.missing.Count -eq 0 -and
            $comparison.unlisted.Count -eq 0 -and $finalComparison.missing.Count -eq 0 -and
            $finalComparison.unlisted.Count -eq 0 -and $changes.Count -eq 0)
        [pscustomobject][ordered]@{
            result=$(if ($matches) {'QUARANTINE_BYTES_MATCH_REVIEW_ONLY'} else {'QUARANTINE_RECHECK_HOLD'})
            checked_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$clock.Elapsed.TotalSeconds
            root=$root;manifest_sha256=$specs[0][2];corrected_receipt_sha256=$specs[2][2]
            expected_top_items=136;expected_files=558;expected_bytes=1077165719L
            attempted_files=$attempted;verified_files=$verified;verified_bytes=$verifiedBytes
            failed_files=$failed.ToArray();enumeration_before_issues=$before.issues;enumeration_after_issues=$after.issues
            manifest_comparison_before=$comparison;manifest_comparison_after=$finalComparison
            enumeration_changed=($changes.Count -gt 0);system_references=$system;file_references=$fileRefs
            historical_backup_present_in_manifest=$true;historical_backup_is_current_full_backup=$false
            deletion_approved=$false;deletion_performed=$false;move_performed=$false;source_file_writes_performed=$false
            app_stop_or_restart_performed=$false;installation_started=$false;canary_observation_started=$false
            limitations=@('Historical root includes old config/log backups and unique evidence; names alone do not establish disposability.',
                'Reference search is bounded and literal; no-hit is not proof of non-use. Matching text is not proof of active use.',
                'Other users/drives, custom config/env paths, encoded/indirect paths, COM task handlers and all open handles are not resolved.',
                'Desktop shortcuts/text: direct children only. Start Menu depth 5 and six protected roots text depth 3 only.',
                'Text: selected extensions, 1 MiB/file, 32 MiB total; read/decode failures and limits are reported.',
                'Empty directories have no historical directory manifest and require review. No ZIP contents or file retention decisions audited.',
                'Existing paths up to 259 chars are read; no new output directory is created. Future output root remains C:\ProgramData\SFLOps.',
                'Read pins prevent ordinary file writes/deletes, not hostile ancestor swaps or filesystem snapshot races.',
                'Time budgets checked between operations; blocked OS/COM calls cannot be preempted. OS access/audit metadata may change.')
        } | ConvertTo-Json -Depth 12
        Write-Host '[DONE] Return complete output. Do not delete or move based on this report alone.'
    } catch {
        Write-Host '[HOLD] Input or inspection failed. Preserve all evidence; no automatic retry or cleanup.'
        throw
    } finally {
        foreach ($pin in $pins) { $pin.Dispose() }
        $env:PATH=$savedQPath; $env:PSModulePath=$savedQModules
    }
}
