& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $savedReadOnlyPath = $env:PATH
    $savedReadOnlyModules = $env:PSModulePath
    $readPins = [Collections.Generic.List[IDisposable]]::new()
    $readClock = [Diagnostics.Stopwatch]::StartNew()
    $base = 'C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109'
    $release = $base + '\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z'
    $install = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $configFile = 'C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
    $commit = 'a203baf62b544d38072a32d71ef411c7cf8b6490'
    $stageRoot = 'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503'
    $stageReceiptHash = 'F4B2FA04536CCC8B3CF095E2D643E7CB6BE0766CF3BB98D5F7FAF301C5AA5C86'

    function Need {
        param([bool]$Ok, [string]$Message)
        if (-not $Ok) { throw $Message }
    }
    function Required {
        param([object]$Object, [string]$Name)
        Need ($null -ne $Object) ('Missing object: ' + $Name)
        $p = $Object.PSObject.Properties[$Name]
        Need ($null -ne $p) ('Missing field: ' + $Name)
        # Every field selected by this checker is an object or scalar, never an array.
        # Reject arrays before PowerShell can enumerate a singleton into a valid-looking scalar.
        Need ($p.Value -isnot [Array]) ('Unexpected array field: ' + $Name)
        return ,($p.Value)
    }
    function CountValue {
        param([object]$Object, [string]$Name)
        $v = Required $Object $Name
        Need (($v -is [int] -or $v -is [long]) -and $v -ge 0) ('Invalid counter: ' + $Name)
        return [long]$v
    }
    function PlainPath {
        param([string]$Path)
        $node = [IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
        while ($null -ne $node) {
            Need (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) ('Reparse path: ' + $Path)
            if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
        }
    }
    function FileFacts {
        param([string]$Path, [string]$Expected = '')
        PlainPath $Path
        $s = [IO.File]::Open($Path, 'Open', 'Read', 'Read')
        $readPins.Add($s)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash($s)).Replace('-', '') }
        finally { $sha.Dispose() }
        if ($Expected -ne '') { Need ($hash -ceq $Expected) ('Hash mismatch: ' + $Path) }
        return [pscustomobject]@{path=$Path;length=$s.Length;sha256=$hash}
    }
    function DecodeJsonObject {
        param([string]$Text)
        # Reject root arrays before ConvertFrom-Json/PowerShell can unfold them.
        Need (-not [string]::IsNullOrWhiteSpace($Text) -and $Text.TrimStart().StartsWith('{',[StringComparison]::Ordinal)) 'Expected one JSON object, not an array or scalar.'
        $value = ConvertFrom-Json -InputObject $Text
        Need ($value -is [pscustomobject] -and $value -isnot [Array]) 'Invalid JSON object shape.'
        return ,$value
    }
    function ReadJsonFile {
        param([string]$Path, [string]$Expected = '')
        $fact = FileFacts $Path $Expected
        Need ($fact.length -le 1048576) 'JSON exceeds read budget.'
        $pin = $readPins[$readPins.Count-1]
        $pin.Position = 0
        $reader = [IO.StreamReader]::new($pin,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try { return DecodeJsonObject $reader.ReadToEnd() }
        finally { $reader.Dispose() }
    }
    function ConfigFacts {
        param([string]$Path)
        PlainPath $Path
        # Do not block the running app's normal config writes or atomic replacements.
        $stream = [IO.File]::Open($Path,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $size = $stream.Length
            Need ($size -gt 0 -and $size -le 1048576) 'Config size outside read budget.'
            $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')
            $stream.Position = 0
            $again = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')
            Need ($stream.Length -eq $size -and $again -ceq $hash) 'Config changed during shared read.'
            return [pscustomobject]@{length=$size;sha256=$hash;sharing='ReadWrite,Delete; short read, fresh path each time'}
        } finally { $sha.Dispose(); $stream.Dispose() }
    }
    function SameConfig {
        param([object]$Before,[object]$After)
        Need ($Before.length -eq $After.length -and $Before.sha256 -ceq $After.sha256) 'Config changed since staging or during the current check.'
    }
    function AssertStageReceipt {
        param([object]$Receipt)
        Need ((Required $Receipt 'schema_version') -ceq 'v1026-static-stage-result-v1') 'Unexpected staging receipt schema.'
        Need ((Required $Receipt 'result') -ceq 'V1026_TRANSFER_STAGED_RUNTIME_RECORDED_NOT_INSTALL_READY') 'Staging result differs.'
        Need ((Required $Receipt 'product_commit') -ceq 'd7a1b20f96711fb07fc7add0867e79ee36506fce') 'Staged product identity differs.'
        Need ((Required $Receipt 'tooling_commit') -ceq 'c03f7c76ff6e75bfe330275ac0fa01326f357261') 'Staged tooling identity differs.'
        Need ((Required $Receipt 'current_version') -ceq '1.0.25' -and (Required $Receipt 'current_commit') -ceq $commit) 'Staging baseline identity differs.'
        Need ((Required $Receipt 'protected_stage_root') -ceq $stageRoot) 'Staging root differs.'
        Need ((Required $Receipt 'transfer_sha256') -ceq 'F3FBC91CE687DAD1085F34F34C4F014B7D198B941210DB397B442BFA7334796B') 'Staged transfer hash differs.'
        Need ((Required $Receipt 'transfer_manifest_sha256') -ceq 'A32E25C0901AC9CF438517E55DE2B85E03AE7243C9DC997410A1E5D04683286E') 'Staged manifest hash differs.'
        Need ((CountValue $Receipt 'verified_payload_files') -eq 32) 'Staged payload count differs.'
        foreach ($name in @('installation_ready','installation_authorized','installation_started','application_restart_performed',
            'product_changes_made','automatic_rollback_performed','observation_started','packet_capture_started',
            'added_spot_image_requests','full_120m_allowed','production_promotion_allowed')) {
            $value = Required $Receipt $name
            Need ($value -is [bool] -and -not $value) ('Unexpected staging approval/change flag: '+$name)
        }
        $r = Required $Receipt 'current_runtime_after'
        return [pscustomobject]@{
            main_pid=CountValue $r 'main_pid';main_start_ticks=CountValue $r 'main_start_utc_ticks'
            backend_pid=CountValue $r 'backend_pid';backend_start_ticks=CountValue $r 'backend_start_utc_ticks'
        }
    }
    function LocalGet {
        param([string]$Endpoint)
        Need ($Endpoint -cin @('health','api/spot/config','stats','api/config')) 'Unapproved local endpoint.'
        $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:8000/' + $Endpoint)
        $request.Method = 'GET'; $request.Proxy = $null; $request.AllowAutoRedirect = $false
        $request.Timeout = 10000; $request.ReadWriteTimeout = 10000
        $response = $null; $stream = $null; $buffer = [IO.MemoryStream]::new()
        $budget = [Diagnostics.Stopwatch]::StartNew()
        try {
            $response = $request.GetResponse()
            Need ([int]$response.StatusCode -eq 200) ('Local query not 200: ' + $Endpoint)
            $stream = $response.GetResponseStream(); $chunk = New-Object byte[] 8192
            while (($count = $stream.Read($chunk,0,$chunk.Length)) -gt 0) {
                Need ($buffer.Length+$count -le 2097152 -and $budget.Elapsed.TotalSeconds -le 20) ('Local response size/time limit: '+$Endpoint)
                $buffer.Write($chunk,0,$count)
            }
            return DecodeJsonObject ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
        } finally {
            if ($null -ne $stream) { $stream.Dispose() }
            if ($null -ne $response) { $response.Dispose() }
            $buffer.Dispose()
        }
    }
    function SelectStorageSettings {
        param([object]$Configuration)
        Need ((Required $Configuration 'config_path') -ceq $configFile) 'API active config path differs from the pinned config file.'
        $values = Required $Configuration 'values'
        $settings = Required $values 'settings'
        $capture = Required (Required $values 'spot') 'image_capture'
        $record = [ordered]@{config_path=$configFile}
        foreach ($name in @('logpath','snapshotpath')) {
            $value = Required $settings $name
            Need ($value -is [string] -and $value.Length -le 1024) ('Invalid storage setting: '+$name)
            $record[$name] = $value
        }
        $capturePath = Required $capture 'path'
        Need ($capturePath -is [string] -and $capturePath.Length -le 1024) 'Invalid configured image capture path.'
        $record.image_capture_path = $capturePath
        $record.restart_required = Required $Configuration 'restart_required'
        Need ($record.restart_required -is [bool]) 'Invalid restart-required flag.'
        $record.source = 'api/config cached configured values only; not resolved active runtime storage paths'
        $record.paths_followed = $false
        $record.active_storage_paths_verified = $false
        return [pscustomobject]$record
    }
    function RuntimeAnchor {
        $backends = @(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
        $apps = @(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
        $owners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        Need ($backends.Count -eq 1 -and $owners.Count -eq 1 -and $owners[0] -eq $backends[0].Id) 'Backend/listener identity is ambiguous.'
        $backend = $backends[0]
        $parent = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $backend.Id)
        $main = @($apps | Where-Object Id -eq $parent.ParentProcessId)
        Need ($main.Count -eq 1 -and $backend.Path -ieq ($install+'\resources\backend\SmartFactoryBackend.exe')) 'Unexpected backend path or parent.'
        foreach ($app in $apps) { Need ($app.Path -ieq ($install+'\smart-factory.exe')) 'Unexpected app path.' }
        return [pscustomobject]@{
            main_pid=$main[0].Id;main_start_ticks=$main[0].StartTime.ToUniversalTime().Ticks
            backend_pid=$backend.Id;backend_start_ticks=$backend.StartTime.ToUniversalTime().Ticks
            backend_started_at=$backend.StartTime.ToString('o');app_process_count=$apps.Count
        }
    }
    function SameRuntime {
        param([object]$A,[object]$B)
        foreach ($n in @('main_pid','main_start_ticks','backend_pid','backend_start_ticks')) {
            Need ($A.$n -eq $B.$n) 'Runtime changed during this check; comparison is invalid.'
        }
    }
    function FailureNames {
        return @('source_port_pool_acquire_wait_count','source_port_pool_exhaustion_count',
            'source_port_reuse_violation_count','source_port_transport_failure_count',
            'source_port_bind_retry_exhaustion_count','source_port_image_failure_count',
            'source_port_temperature_failure_count','source_port_internal_temperature_failure_count',
            'source_port_diagnostic_failure_count','source_port_connection_test_failure_count',
            'source_port_request_failure_event_count_total','source_port_request_failure_event_drop_count',
            'image_refresh_failure_count','image_cache_clock_anomaly_count')
    }
    function Snapshot {
        $a = RuntimeAnchor
        $health = LocalGet 'health'
        Need ((Required $health 'app_version') -ceq '1.0.25') 'Current version differs.'
        Need ((Required (Required $health 'spot_temperature') 'build_git_commit') -ceq $commit) 'Current build commit differs.'
        $spot = LocalGet 'api/spot/config'
        $image = Required $spot 'image'; $capture = Required $spot 'image_capture'
        $stats = LocalGet 'stats'; $errors = Required $stats 'errors'
        $v = [ordered]@{checked_at=[DateTimeOffset]::Now.ToString('o');clock_seconds=$readClock.Elapsed.TotalSeconds;runtime=$a}
        $v.storage_settings = SelectStorageSettings (LocalGet 'api/config')
        foreach ($n in @('image_status','image_source','last_success_at','last_error_at','last_error_code',
            'source_port_policy_version','source_port_enforcement_supported','source_port_enforcement_active',
            'source_port_minimum_reuse_interval_seconds','source_port_minimum_required_reuse_interval_seconds')) {
            $v[$n] = Required $image $n
        }
        $names = @(FailureNames) + @('image_downstream_request_count','image_upstream_request_count',
            'image_refresh_success_count','source_port_transport_started_count','source_port_transport_success_count',
            'source_port_bind_collision_count','source_port_pool_capacity','source_port_pool_guarded_count',
            'source_port_pool_leased_count','source_port_pool_quarantined_count','source_port_pool_rebind_pending_count')
        foreach ($n in $names) { $v[$n] = CountValue $image $n }
        $enabled = Required $capture 'enabled'
        Need ($enabled -is [bool]) 'Invalid capture enabled field.'
        $v.capture_enabled = $enabled
        $v.capture_mode = Required $capture 'mode'
        foreach ($n in @('enqueued_count','written_count','fact_row_count','dropped_count','failure_count','queue_size')) {
            $v['capture_'+$n] = CountValue $capture $n
        }
        $v.http_5xx_count = CountValue $stats 'total_http_5xx_count'
        $v.error_queue_size = CountValue $errors 'queue_size'
        $v.error_repeat_total = CountValue $errors 'repeat_total'
        $v.error_last_at = Required $errors 'last_error_at'
        SameRuntime $a (RuntimeAnchor)
        $lastSuccess = $v['last_success_at']
        $timeType = if ($null -eq $lastSuccess) {'null'} else {$lastSuccess.GetType().FullName}
        $timeValue = if ($lastSuccess -is [decimal] -or $lastSuccess -is [double] -or $lastSuccess -is [long] -or $lastSuccess -is [int]) {
            $lastSuccess.ToString([Globalization.CultureInfo]::InvariantCulture)
        } else {'<not-a-number>'}
        Write-Host ('[TIMESTAMP] checked_at='+$v['checked_at']+' last_success_type='+$timeType+' last_success_value='+$timeValue)
        return [pscustomobject]$v
    }
    function TreeFacts {
        param([string]$Root,[int]$ExpectedFileCount=0,[long]$ExpectedTotalBytes=-1)
        PlainPath $Root
        $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
        $queue = [Collections.Generic.Queue[string]]::new()
        $files = [Collections.Generic.List[object]]::new()
        $records = [Collections.Generic.List[string]]::new()
        $queue.Enqueue($rootFull); $bytes = [long]0; $inventoryBytes = [long]0
        while ($queue.Count -gt 0) {
            $directory = $queue.Dequeue(); PlainPath $directory
            foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
                PlainPath $item.FullName
                if ($item.PSIsContainer) {$queue.Enqueue($item.FullName);continue}
                $relative = $item.FullName.Substring($rootFull.Length+1).Replace('\','/')
                Need ($relative -notmatch '[\x00\r\n]') 'Invalid payload name.'
                $files.Add([pscustomobject]@{path=$item.FullName;relative=$relative})
                $inventoryBytes += $item.Length
                Need ($files.Count -le 2000) 'Unexpected extra installed files.'
            }
        }
        # Refuse unexpected installed-directory data before retaining any file read locks.
        if ($ExpectedFileCount -gt 0) { Need ($files.Count -eq $ExpectedFileCount) 'Installed file inventory differs; no payload file locks were taken.' }
        if ($ExpectedTotalBytes -ge 0) { Need ($inventoryBytes -eq $ExpectedTotalBytes) 'Installed byte inventory differs; no payload file locks were taken.' }
        foreach ($file in $files) {
            $f = FileFacts $file.path
            $relative = $file.relative
            $records.Add("$relative`0$($f.length)`0$($f.sha256)`n"); $bytes += $f.length
            if (($records.Count % 250) -eq 0) { Write-Host ('[PAYLOAD] checked='+$records.Count+' / 1648') }
        }
        $sorted = $records.ToArray(); [Array]::Sort($sorted,[StringComparer]::Ordinal)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hash = [BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($sorted)))).Replace('-','') }
        finally {$sha.Dispose()}
        return [pscustomobject]@{file_count=$records.Count;total_bytes=$bytes;tree_sha256=$hash}
    }
    function InstalledTree {
        param([string]$Root)
        $facts = TreeFacts $Root -ExpectedFileCount 1648 -ExpectedTotalBytes 539280902
        Need ($facts.file_count -eq 1648 -and $facts.total_bytes -eq 539280902 -and $facts.tree_sha256 -ceq '4CD4ACB613A7E75011F8DCB33209BF3E50C71F8F0F79D4E01949116D0AD90860') 'Installed payload differs from the approved installer.'
        return $facts
    }
    function CompareSnapshots {
        param([object]$Before,[object]$After)
        SameRuntime $Before.runtime $After.runtime
        $holds = [Collections.Generic.List[string]]::new()
        $rows = [Collections.Generic.List[object]]::new()
        $failNames = @(FailureNames) + @('capture_dropped_count','capture_failure_count','http_5xx_count')
        $progressNames = @('image_downstream_request_count','image_upstream_request_count','image_refresh_success_count',
            'source_port_transport_started_count','source_port_transport_success_count',
            'capture_enqueued_count','capture_written_count','capture_fact_row_count')
        foreach ($n in ($failNames+$progressNames+@('source_port_bind_collision_count'))) {
            $b = CountValue $Before $n; $a = CountValue $After $n; $d = $a-$b
            Need ($d -ge 0) ('Counter decreased: '+$n)
            $rows.Add([pscustomobject]@{name=$n;before=$b;after=$a;delta=$d})
            if ($n -cin $failNames -and $d -gt 0) {$holds.Add('new-failure:'+ $n)}
            if ($n -cin $progressNames -and $d -le 0) {$holds.Add('no-progress:'+ $n)}
        }
        foreach ($s in @($Before,$After)) {
            if ($s.storage_settings.restart_required) { $holds.Add('pending-config-restart-needs-review') }
            if ($s.image_status -cne 'ok' -or $s.image_source -cne 'upstream') {$holds.Add('image-not-ok-upstream')}
            foreach ($n in @('source_port_enforcement_supported','source_port_enforcement_active','capture_enabled')) {
                Need ($s.$n -is [bool]) ('Invalid boolean: '+$n)
                if (-not $s.$n) {$holds.Add('inactive:'+ $n)}
            }
            if ($s.source_port_policy_version -cne 'spot-source-port-quarantine-v3') {$holds.Add('unexpected-port-policy')}
            foreach ($n in @('source_port_minimum_reuse_interval_seconds','source_port_minimum_required_reuse_interval_seconds')) {
                $v = $s.$n
                Need (($v -is [int] -or $v -is [long] -or $v -is [double] -or $v -is [decimal]) -and -not [double]::IsNaN($v) -and -not [double]::IsInfinity($v)) ('Invalid reuse interval: '+$n)
            }
            if ($s.source_port_minimum_required_reuse_interval_seconds -ne 75 -or $s.source_port_minimum_reuse_interval_seconds -lt 75) {$holds.Add('reuse-interval-below-policy')}
            if ($s.error_queue_size -gt 0) {$holds.Add('app-error-queue-needs-review')}
        }
        foreach ($name in @('logpath','snapshotpath','image_capture_path','restart_required')) {
            if ($Before.storage_settings.$name -cne $After.storage_settings.$name) { $holds.Add('configured-storage-settings-changed') }
        }
        Need ($After.error_repeat_total -ge $Before.error_repeat_total) 'App error counter decreased; comparison is invalid.'
        if ($Before.error_last_at -cne $After.error_last_at -or $After.error_repeat_total -gt $Before.error_repeat_total) {$holds.Add('app-error-summary-changed')}
        $bSuccess = $Before.last_success_at; $aSuccess = $After.last_success_at
        foreach ($v in @($bSuccess,$aSuccess)) {
            # Windows PowerShell 5.1 ConvertFrom-Json returns Decimal for fractional JSON numbers.
            # Accept numeric types without coercing null, text, booleans or arrays into timestamps.
            Need (($v -is [decimal] -or $v -is [double] -or $v -is [long] -or $v -is [int]) -and -not [double]::IsNaN($v) -and -not [double]::IsInfinity($v) -and $v -gt 0) 'Invalid last-success timestamp; see TIMESTAMP type/value output.'
        }
        if ($aSuccess -le $bSuccess) {$holds.Add('last-success-not-advancing')}
        $seconds = $After.clock_seconds-$Before.clock_seconds
        Need ($seconds -ge 30 -and $seconds -le 120) 'Sample outside the 30-to-120-second comparison window.'
        return [pscustomobject]@{
            sample_result=$(if ($holds.Count -eq 0) {'CURRENT_SAMPLE_OK_NOT_OPERATIONAL_APPROVAL'}else{'CURRENT_SAMPLE_HOLD_REVIEW_REQUIRED'})
            elapsed_seconds=$seconds;holds=@($holds.ToArray() | Select-Object -Unique);counters=@($rows.ToArray())
            historical_failure_counters_nonzero=@($rows | Where-Object {$_.name -cin $failNames -and $_.before -gt 0} | Select-Object -ExpandProperty name)
        }
    }

    try {
        $native = [IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
        $current = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
        $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and $current -ieq $native -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Use administrator native 64-bit Windows PowerShell 5.1.'
        $env:PATH = [Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        $env:PSModulePath = [IO.Path]::GetDirectoryName($native)+'\Modules'
        Write-Host '[READ ONLY] Keep SmartFactory and its normal SPOT screen unchanged. No reset, error clear, restart, install, capture or final YES.' -ForegroundColor Cyan
        Write-Host '[STEP 1/4] Verify the exact completed staging receipt and current v1.0.25 recovery EXE.'
        $receipt = ReadJsonFile ($stageRoot+'\preflight-result.json') $stageReceiptHash
        $receiptRuntime = AssertStageReceipt $receipt
        $anchor = RuntimeAnchor
        SameRuntime $receiptRuntime $anchor
        $configBefore = ConfigFacts $configFile
        SameConfig (Required $receipt 'config') $configBefore
        $verifiedFiles = @(
            FileFacts ($release+'\release_identity.json') '82C12F0A3BB2AC2D0A5A2DE4479FD36E79AD7A1C98C5688670366F5D21FA64AD'
            FileFacts ($release+'\smart-factory-logger-v2 Setup 1.0.25.exe') '9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
        )
        Write-Host '[STEP 2/4] Check installed inventory before hashing 1648 payload files. Config and external app-data directories are not read-locked.'
        $tree = InstalledTree $install
        $provenance = ReadJsonFile ($install+'\resources\backend\_internal\backend\build_provenance.json')
        Need ((Required $provenance 'git_commit') -ceq $commit) 'Installed build provenance differs.'
        SameRuntime $anchor (RuntimeAnchor)
        Write-Host '[STEP 3/4] Read local health/spot-config/stats/storage-settings twice, with a 30-second wait.'
        $before = Snapshot
        SameRuntime $anchor $before.runtime
        Write-Host '[BEFORE]'
        $before | ConvertTo-Json -Depth 6
        for ($i=1;$i -le 3;$i++) {
            Start-Sleep -Seconds 10
            Write-Host ('[WAIT] elapsed='+($i*10)+'s remaining='+(30-$i*10)+'s percent='+[int](100*$i/3)+'%; local clock only.')
        }
        $after = Snapshot
        Write-Host '[AFTER]'
        $after | ConvertTo-Json -Depth 6
        $comparison = CompareSnapshots $before $after
        SameRuntime $anchor (RuntimeAnchor)
        $configAfter = ConfigFacts $configFile
        SameConfig $configBefore $configAfter
        Write-Host '[STEP 4/4] Report current sample only. No installation or recovery approval is granted.'
        $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
        $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($install))
        [pscustomobject][ordered]@{
            schema_version='v1026-preinstall-current-baseline-v1'
            result=$comparison.sample_result;checked_at=[DateTimeOffset]::Now.ToString('o')
            current_product_version='1.0.25';current_product_commit=$commit
            target_version='1.0.26';target_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce'
            staging_receipt_path=($stageRoot+'\preflight-result.json');staging_receipt_sha256=$stageReceiptHash
            same_runtime_as_staging=$true;last_boot_at=$boot.ToString('o')
            installed_tree=$tree;verified_static_files=$verifiedFiles
            config_before=$configBefore;config_after=$configAfter
            before=$before;after=$after;comparison=$comparison
            disk_free_gib=[Math]::Round($drive.AvailableFreeSpace/1GB,2)
            recovery_candidate_version='1.0.25';recovery_candidate_commit=$commit
            recovery_candidate_sha256='9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
            recovery_operational_suitability='PENDING_CONFIG_DATA_BACKUP_RESTORE_AND_INCIDENT_REVIEW'
            remaining_review=@('CURRENT_SAMPLE_AND_HISTORICAL_ERRORS','DATA_LOCATION_AND_CONSISTENT_BACKUP_RESTORE',
                'INSTALL_RUNTIME_TOKEN_AND_LAUNCH_CAPABILITY','DEVELOPMENT_TEST_WINDOW_AND_STOP_RECOVERY_CONDITIONS',
                'FRESH_V1026_INSTALLED_TREE_AND_UI_COMPARISON_AFTER_SEPARATE_INSTALL_APPROVAL')
            deployment_context='COMMERCIAL_FACTORY_DEVELOPER_MANAGED_INTERNAL_DEVELOPMENT_ONLY'
            source_file_writes_performed=$false;data_backup_performed=$false;data_restore_tested=$false
            active_storage_paths_verified=$false;process_tokens_audited=$false
            product_changes_made=$false;application_restart_performed=$false
            installation_ready=$false;installation_authorized=$false;installation_started=$false
            automatic_rollback_performed=$false;new_canary_observation_started=$false
            added_spot_image_requests=$false;packet_capture_started=$false;production_promotion_allowed=$false
            limitation='Point-in-time installed-tree check and short local counter sample only. Not continuous health, UI attestation, config history, process-token audit, backup/restore proof or operating approval. Normal app request logging may occur.'
        } | ConvertTo-Json -Depth 12
        Write-Host '[DONE] Return complete output and say whether images are visibly updating now. No final YES. No server evidence files were written.' -ForegroundColor Green
    }
    catch {
        Write-Host '[HOLD] Read-only check stopped. Preserve output; no automatic retry, restart, installation, rollback or observation.' -ForegroundColor Yellow
        throw
    }
    finally {
        foreach ($pin in $readPins) { $pin.Dispose() }
        $env:PATH=$savedReadOnlyPath
        $env:PSModulePath=$savedReadOnlyModules
    }
}
