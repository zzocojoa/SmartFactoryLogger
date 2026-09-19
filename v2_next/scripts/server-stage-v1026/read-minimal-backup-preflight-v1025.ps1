& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $savedPath = $env:PATH
    $savedModulePath = $env:PSModulePath
    $clock = [Diagnostics.Stopwatch]::StartNew()

    $roamingRoot = 'C:\Users\user\AppData\Roaming'
    $appDataRoot = $roamingRoot + '\SmartFactoryLogger'
    $electronRoot = $roamingRoot + '\smart-factory-logger-v2'
    $installRoot = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $opsRoot = 'C:\ProgramData\SFLOps'
    $expectedCommit = 'a203baf62b544d38072a32d71ef411c7cf8b6490'
    $expectedConfigHash = '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'

    function Need {
        param([bool]$OK, [string]$Code)
        if (-not $OK) { throw ('MINIMAL_BACKUP_PREFLIGHT:' + $Code) }
    }

    function Required {
        param([object]$Object, [string]$Name)
        Need ($null -ne $Object -and $Object -isnot [Array]) ('object-' + $Name)
        $property = $Object.PSObject.Properties[$Name]
        Need ($null -ne $property -and $property.Value -isnot [Array]) ('field-' + $Name)
        return ,$property.Value
    }

    function FullLocalPath {
        param([object]$Value)
        Need ($Value -is [string] -and $Value.Length -ge 4 -and $Value.Length -le 240) 'path-shape'
        Need ($Value -cmatch '^[A-Za-z]:[\\/]' -and $Value -notmatch '[\x00-\x1F<>"|?*~]' -and
            $Value.Substring(2) -notmatch ':') 'path-syntax'
        $path = $Value.Replace('/', '\').TrimEnd('\')
        Need ($path.Length -gt 3) 'broad-root-rejected'
        foreach ($part in $path.Substring(3).Split('\')) {
            Need ($part.Length -gt 0 -and $part -ne '.' -and $part -ne '..' -and $part -notmatch '[ .]$' -and
                $part -notmatch '^(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)') 'path-component'
        }
        return [IO.Path]::GetFullPath($path)
    }

    function IsWithin {
        param([string]$Path, [string]$Root)
        return $Path.Equals($Root, [StringComparison]::OrdinalIgnoreCase) -or
            $Path.StartsWith($Root + '\', [StringComparison]::OrdinalIgnoreCase)
    }

    function GetAttributesOrMissing {
        param([string]$Path)
        try { return [IO.File]::GetAttributes($Path) }
        catch {
            $exception = $_.Exception
            while ($null -ne $exception.InnerException) { $exception = $exception.InnerException }
            if ($exception -is [IO.FileNotFoundException] -or
                $exception -is [IO.DirectoryNotFoundException]) { return $null }
            throw 'MINIMAL_BACKUP_PREFLIGHT:metadata-access-failed'
        }
    }

    function AssertPlainAncestors {
        param([string]$Path, [bool]$RequireLeaf)
        $full = FullLocalPath $Path
        $nodes = [Collections.Generic.List[string]]::new()
        $node = [IO.FileInfo]::new($full)
        while ($null -ne $node) {
            $nodes.Add($node.FullName)
            if ($node -is [IO.FileInfo]) { $node = $node.Directory }
            else { $node = $node.Parent }
        }
        for ($index = $nodes.Count - 1; $index -ge 0; $index--) {
            $attributes = GetAttributesOrMissing $nodes[$index]
            if ($null -eq $attributes) {
                Need (-not $RequireLeaf -and $index -eq 0) 'required-path-missing'
                return $false
            }
            Need (($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path-rejected'
        }
        return $true
    }

    function GetFixedFileMetadata {
        param([string]$Label, [string]$Path, [bool]$RequiredFile)
        $full = FullLocalPath $Path
        Need (IsWithin $full $appDataRoot) 'state-file-outside-root'
        $exists = AssertPlainAncestors $full $RequiredFile
        if (-not $exists) {
            return [pscustomobject]@{ label = $Label; exists = $false; bytes = $null; last_write_utc = $null }
        }
        $info = [IO.FileInfo]::new($full)
        $info.Refresh()
        Need ($info.Exists -and ($info.Attributes -band [IO.FileAttributes]::Directory) -eq 0 -and
            ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'state-file-shape'
        return [pscustomobject]@{
            label = $Label
            exists = $true
            bytes = [long]$info.Length
            last_write_utc = $info.LastWriteTimeUtc.ToString('o')
        }
    }

    function GetTreeSummary {
        param(
            [string]$Label,
            [string]$Root,
            [bool]$RequiredRoot,
            [int]$MaximumEntries = 100000,
            [int]$MaximumSeconds = 60
        )
        Need ($MaximumEntries -ge 1 -and $MaximumEntries -le 200000 -and
            $MaximumSeconds -ge 1 -and $MaximumSeconds -le 300) 'inventory-budget'
        $fullRoot = FullLocalPath $Root
        Need ($fullRoot -ieq $electronRoot -or $fullRoot -ieq ($appDataRoot + '\layouts')) 'tree-root-not-approved'
        $exists = AssertPlainAncestors $fullRoot $RequiredRoot
        if (-not $exists) {
            return [pscustomobject]@{label=$Label;exists=$false;files=0;directories=0;bytes=[long]0;
                max_relative_path_chars=0;unsupported_attribute_count=0;enumeration_complete=$true}
        }
        $rootAttributes = GetAttributesOrMissing $fullRoot
        Need (($rootAttributes -band [IO.FileAttributes]::Directory) -ne 0) 'tree-root-not-directory'
        $queue = [Collections.Generic.Queue[string]]::new()
        $queue.Enqueue($fullRoot)
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $entries = 0
        $files = 0
        $directories = 0
        $bytes = [long]0
        $maxRelative = 0
        $unsupported = 0
        while ($queue.Count -gt 0) {
            Need ($timer.Elapsed.TotalSeconds -le $MaximumSeconds) 'inventory-time-budget'
            $directory = $queue.Dequeue()
            foreach ($child in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
                $entries++
                Need ($entries -le $MaximumEntries) 'inventory-entry-budget'
                $full = FullLocalPath $child
                Need (IsWithin $full $fullRoot) 'inventory-boundary'
                $attributes = GetAttributesOrMissing $full
                Need ($null -ne $attributes) 'inventory-race'
                Need (($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'inventory-reparse-rejected'
                if (($attributes -band ([IO.FileAttributes]::Encrypted -bor [IO.FileAttributes]::Offline -bor
                    [IO.FileAttributes]::SparseFile)) -ne 0) { $unsupported++ }
                $relativeChars = $full.Length - $fullRoot.Length - 1
                if ($relativeChars -gt $maxRelative) { $maxRelative = $relativeChars }
                if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) {
                    $directories++
                    $queue.Enqueue($full)
                }
                else {
                    $info = [IO.FileInfo]::new($full)
                    $info.Refresh()
                    Need ($info.Exists) 'inventory-file-race'
                    $files++
                    $bytes += [long]$info.Length
                }
            }
            if (($entries % 1000) -eq 0 -and $entries -gt 0) {
                Write-Host ('[METADATA] ' + $Label + ' entries=' + $entries + ' elapsed=' +
                    [Math]::Round($timer.Elapsed.TotalSeconds, 1) + 's; contents not read')
            }
        }
        Need ($unsupported -eq 0) ('unsupported-file-attributes-' + $Label)
        return [pscustomobject]@{label=$Label;exists=$true;files=$files;directories=$directories;bytes=$bytes;
            max_relative_path_chars=$maxRelative;unsupported_attribute_count=$unsupported;enumeration_complete=$true}
    }

    function GetPinnedConfigHash {
        param([string]$Path, [string]$Expected)
        $full = FullLocalPath $Path
        Need ($full -ieq ($appDataRoot + '\config.ini')) 'config-path'
        [void](AssertPlainAncestors $full $true)
        $stream = [IO.File]::Open($full, 'Open', 'Read',
            ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            Need ($stream.Length -gt 0 -and $stream.Length -le 1048576) 'config-size'
            $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
            Need ($actual -ceq $Expected) 'config-hash'
            return [pscustomobject]@{bytes=[long]$stream.Length;sha256=$actual;matches_pin=$true}
        }
        finally { $sha.Dispose(); $stream.Dispose() }
    }

    function DecodeJsonObject {
        param([string]$Text)
        Need (-not [string]::IsNullOrWhiteSpace($Text) -and
            $Text.TrimStart().StartsWith('{', [StringComparison]::Ordinal)) 'json-root'
        $value = ConvertFrom-Json -InputObject $Text
        Need ($value -is [pscustomobject] -and $value -isnot [Array]) 'json-shape'
        return ,$value
    }

    function LocalHealth {
        $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:8000/health')
        $request.Method = 'GET'
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        $request.Timeout = 10000
        $request.ReadWriteTimeout = 10000
        $response = $null
        $reader = $null
        try {
            $response = $request.GetResponse()
            Need ([int]$response.StatusCode -eq 200) 'health-status'
            $reader = [IO.StreamReader]::new($response.GetResponseStream(),
                [Text.UTF8Encoding]::new($false, $true), $true)
            $text = $reader.ReadToEnd()
            Need ($text.Length -le 1048576) 'health-response-size'
            return DecodeJsonObject $text
        }
        finally {
            if ($null -ne $reader) { $reader.Dispose() }
            if ($null -ne $response) { $response.Dispose() }
        }
    }

    function GetRuntimeAnchor {
        $backends = @(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
        $apps = @(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
        $owners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        Need ($backends.Count -eq 1 -and $owners.Count -eq 1 -and
            $owners[0] -eq $backends[0].Id) 'runtime-listener'
        $backend = $backends[0]
        $backendCim = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $backend.Id)
        $main = @($apps | Where-Object Id -eq $backendCim.ParentProcessId)
        Need ($main.Count -eq 1 -and
            $backend.Path -ieq ($installRoot + '\resources\backend\SmartFactoryBackend.exe')) 'backend-path-parent'
        foreach ($app in $apps) {
            Need ($app.Path -ieq ($installRoot + '\smart-factory.exe')) 'app-path'
        }
        $owner = Invoke-CimMethod -InputObject $backendCim -MethodName GetOwnerSid
        $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        Need ($owner.ReturnValue -eq 0 -and $owner.Sid -ceq $currentSid) 'runtime-owner'
        return [pscustomobject]@{
            main_pid = $main[0].Id
            main_start_utc_ticks = $main[0].StartTime.ToUniversalTime().Ticks
            backend_pid = $backend.Id
            backend_start_utc_ticks = $backend.StartTime.ToUniversalTime().Ticks
            app_process_count = $apps.Count
            owner_matches_current_user = $true
        }
    }

    function AssertSameRuntime {
        param([object]$Before, [object]$After)
        foreach ($name in @('main_pid','main_start_utc_ticks','backend_pid','backend_start_utc_ticks')) {
            Need ($Before.$name -eq $After.$name) 'runtime-changed'
        }
    }

    function GetOpsRootReview {
        param([string]$Path)
        $full = FullLocalPath $Path
        Need ($full -ceq 'C:\ProgramData\SFLOps') 'ops-root-path'
        $parent = [IO.Path]::GetDirectoryName($full)
        [void](AssertPlainAncestors $parent $true)
        if (-not [IO.Directory]::Exists($full)) {
            return [pscustomobject]@{path=$full;exists=$false;creation_required=$true;plain_path=$true;
                owner_sid=$null;broad_write_allow_count=$null;acl_safe_for_reuse=$null}
        }
        [void](AssertPlainAncestors $full $true)
        $directory = [IO.DirectoryInfo]::new($full)
        $security = $directory.GetAccessControl([Security.AccessControl.AccessControlSections]::Owner -bor
            [Security.AccessControl.AccessControlSections]::Access)
        $ownerSid = $security.GetOwner([Security.Principal.SecurityIdentifier]).Value
        $broadSids = @('S-1-1-0','S-1-5-11','S-1-5-32-545')
        $broadWrite = 0
        foreach ($rule in $security.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            $rights = [Security.AccessControl.FileSystemRights]$rule.FileSystemRights
            $writeMask = [Security.AccessControl.FileSystemRights]::Write -bor
                [Security.AccessControl.FileSystemRights]::Modify -bor
                [Security.AccessControl.FileSystemRights]::FullControl
            if ($rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
                $rule.IdentityReference.Value -cin $broadSids -and ($rights -band $writeMask) -ne 0) {
                $broadWrite++
            }
        }
        $safeOwner = $ownerSid -cin @('S-1-5-18','S-1-5-32-544')
        return [pscustomobject]@{path=$full;exists=$true;creation_required=$false;plain_path=$true;
            owner_sid=$ownerSid;broad_write_allow_count=$broadWrite;acl_safe_for_reuse=($safeOwner -and $broadWrite -eq 0)}
    }

    try {
        $native = [IO.Path]::Combine([Environment]::SystemDirectory,
            'WindowsPowerShell\v1.0\powershell.exe')
        $principal = [Security.Principal.WindowsPrincipal]::new(
            [Security.Principal.WindowsIdentity]::GetCurrent())
        Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and
            $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and
            [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native -and
            $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51-required'
        Need ((FullLocalPath $env:APPDATA) -ieq $roamingRoot) 'operator-profile-differs'
        $env:PATH = [Environment]::SystemDirectory + ';' + [IO.Path]::GetDirectoryName($native)
        $env:PSModulePath = [IO.Path]::GetDirectoryName($native) + '\Modules'

        Write-Host '[STEP 1/4] Verify current v1.0.25 runtime and pinned config. Read only.' -ForegroundColor Cyan
        $runtime = GetRuntimeAnchor
        $health = LocalHealth
        Need ((Required $health 'app_version') -ceq '1.0.25') 'version'
        Need ((Required (Required $health 'spot_temperature') 'build_git_commit') -ceq $expectedCommit) 'commit'
        $configHash = GetPinnedConfigHash ($appDataRoot + '\config.ini') $expectedConfigHash

        Write-Host '[STEP 2/4] Inventory fixed configuration/UI state and Electron profile metadata.' -ForegroundColor Cyan
        $stateSpecs = @(
            @('config_ini','config.ini',$true),
            @('config_backup','config.bak',$false),
            @('config_pending','config.pending.json',$false),
            @('config_meta','config_meta.json',$false),
            @('config_cache','config_cache.json',$false),
            @('layout_current','layout.json',$false),
            @('layout_backup','layout.backup.json',$false),
            @('operator_metadata','operator_metadata.json',$false),
            @('operator_metadata_runtime','operator_metadata_runtime_state.json',$false),
            @('facility_state','state.json',$false)
        )
        $stateFiles = @(foreach ($spec in $stateSpecs) {
            GetFixedFileMetadata $spec[0] ($appDataRoot + '\' + $spec[1]) ([bool]$spec[2])
        })
        $layouts = GetTreeSummary 'layouts' ($appDataRoot + '\layouts') $false
        $electron = GetTreeSummary 'electron_profile' $electronRoot $true
        $stateBytes = [long]0
        $stateCount = 0
        foreach ($item in $stateFiles) {
            if ($item.exists) { $stateBytes += [long]$item.bytes; $stateCount++ }
        }
        $selectedBytes = $stateBytes + [long]$layouts.bytes + [long]$electron.bytes
        $selectedFiles = $stateCount + [int]$layouts.files + [int]$electron.files
        Need ($selectedFiles -gt 0 -and $selectedBytes -gt 0) 'empty-backup-scope'

        Write-Host '[STEP 3/4] Review C:\ProgramData\SFLOps and capacity; nothing is created.' -ForegroundColor Cyan
        $ops = GetOpsRootReview $opsRoot
        if ($ops.exists) { Need ($ops.acl_safe_for_reuse -eq $true) 'existing-sflops-acl-review' }
        $drive = [IO.DriveInfo]::new('C:\')
        $requiredBytes = [long][Math]::Ceiling(($selectedBytes * 2.2) + ($selectedFiles * 16384) + 1GB)
        Need ($drive.AvailableFreeSpace -ge $requiredBytes) 'insufficient-space'
        $projectedTarget = 'C:\ProgramData\SFLOps\backups\v1025-min-YYYYMMDD-HHMMSS'
        $maxRelative = [Math]::Max([int]$layouts.max_relative_path_chars,
            [int]$electron.max_relative_path_chars)
        Need (($projectedTarget.Length + '\restore\electron_profile\'.Length + $maxRelative) -le 240) 'projected-path-budget'

        Write-Host '[STEP 4/4] Recheck runtime and report. No backup or install is authorized.' -ForegroundColor Cyan
        AssertSameRuntime $runtime (GetRuntimeAnchor)
        $healthAfter = LocalHealth
        Need ((Required $healthAfter 'app_version') -ceq '1.0.25') 'version-after'
        Need ((Required (Required $healthAfter 'spot_temperature') 'build_git_commit') -ceq $expectedCommit) 'commit-after'

        [pscustomobject][ordered]@{
            schema_version = 'v1025-minimal-backup-preflight-v1'
            result = 'V1025_MINIMAL_BACKUP_PREFLIGHT_READY_NOT_BACKED_UP'
            checked_at = [DateTimeOffset]::Now.ToString('o')
            elapsed_seconds = [Math]::Round($clock.Elapsed.TotalSeconds, 3)
            product_version = '1.0.25'
            product_commit = $expectedCommit
            runtime = $runtime
            config_hash = $configHash
            selected_state_files = $stateFiles
            selected_trees = @($layouts, $electron)
            selected_file_count = $selectedFiles
            selected_logical_bytes = $selectedBytes
            estimated_required_free_bytes = $requiredBytes
            available_free_bytes = [long]$drive.AvailableFreeSpace
            sflops_root = $ops
            projected_backup_parent = $projectedTarget
            excluded_from_minimal_backup = @(
                'SmartFactoryLogger\logs (CSV, images, facts, diagnostics)',
                'SmartFactoryLogger\snapshots',
                'installed program directory'
            )
            exclusion_risk = 'Minimal backup cannot recover accumulated CSV/image/fact data if upgrade or later runtime damages it.'
            alternate_data_streams_checked = $false
            live_metadata_is_atomic_snapshot = $false
            backup_created = $false
            restore_rehearsal_performed = $false
            application_stop_performed = $false
            application_restart_performed = $false
            installation_started = $false
            product_changes_made = $false
            production_promotion_allowed = $false
            next_action = 'PREPARE_SEPARATE_HASH_BOUND_COLD_MINIMAL_BACKUP_HELPER'
        } | ConvertTo-Json -Depth 9
        Write-Host '[DONE] Read-only scope/capacity review complete. Return the complete output.' -ForegroundColor Green
    }
    catch {
        Write-Host '[HOLD] Preserve output. No automatic retry, backup, cleanup, install, restart or rollback.' -ForegroundColor Yellow
        throw
    }
    finally {
        $env:PATH = $savedPath
        $env:PSModulePath = $savedModulePath
    }
}
