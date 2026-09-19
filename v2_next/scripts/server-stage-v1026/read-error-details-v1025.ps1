& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    $savedDiagnosticPath = $env:PATH
    $savedDiagnosticModules = $env:PSModulePath
    $diagnosticClock = [Diagnostics.Stopwatch]::StartNew()
    $install = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $expectedCommit = 'a203baf62b544d38072a32d71ef411c7cf8b6490'

    function Need { param([bool]$OK,[string]$Message) if (-not $OK) { throw $Message } }
    function Field {
        param([object]$Object,[string]$Name)
        Need ($Object -is [pscustomobject] -and $Object -isnot [Array]) ('Expected object for field: '+$Name)
        $p = $Object.PSObject.Properties[$Name]
        Need ($null -ne $p) ('Missing field: '+$Name)
        return ,($p.Value)
    }
    function Scalar {
        param([object]$Object,[string]$Name)
        $v = Field $Object $Name
        Need ($v -isnot [Array] -and $v -isnot [pscustomobject]) ('Expected scalar: '+$Name)
        return ,$v
    }
    function CountValue {
        param([object]$Object,[string]$Name)
        $v = Scalar $Object $Name
        Need (($v -is [int] -or $v -is [long]) -and $v -ge 0) ('Invalid counter: '+$Name)
        return [long]$v
    }
    function NumberValue {
        param([object]$Value)
        Need (($Value -is [int] -or $Value -is [long] -or $Value -is [decimal] -or $Value -is [double]) -and
            -not [double]::IsNaN($Value) -and -not [double]::IsInfinity($Value) -and $Value -ge 0) 'Invalid nonnegative number.'
        return $Value
    }
    function Epoch {
        param([object]$Value)
        if ($null -eq $Value) { return $null }
        $v = NumberValue $Value
        Need ($v -le 253402214400) 'Timestamp outside supported range.'
        if ($v -eq 0) { return [pscustomobject]@{epoch=$v;kst=$null;recorded=$false} }
        $date = [DateTimeOffset]::FromUnixTimeMilliseconds([long][Math]::Floor([decimal]$v*1000))
        return [pscustomobject]@{epoch=$v;kst=$date.ToOffset([TimeSpan]::FromHours(9)).ToString('o');recorded=$true}
    }
    function ListValue {
        param([object]$Object,[string]$Name,[int]$Maximum)
        $v = Field $Object $Name
        Need ($v -is [Array] -and $v.Count -le $Maximum) ('Invalid bounded array: '+$Name)
        foreach ($item in $v) { Need ($item -is [pscustomobject] -and $item -isnot [Array]) ('Invalid array item: '+$Name) }
        return ,$v
    }
    function TextHash {
        param([string]$Text)
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return [BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($Text))).Replace('-','') }
        finally { $sha.Dispose() }
    }
    function SafeText {
        param([object]$Value)
        if ($null -eq $Value) { return [pscustomobject]@{present=$false;preview=$null;sha256=$null;chars=0;filtered=$false} }
        Need ($Value -is [string]) 'Expected diagnostic text or null.'
        # Shared output is default-deny. A scrubber cannot recognize every secret or internal hostname.
        $allowed = @('No Body','No Header','Body too large','Extruder send timeout','Extruder recv timeout',
            'Extruder cycle timeout','LS send timeout','LS recv timeout','LS cycle timeout',
            'SPOT image upstream failure','SPOT image unexpected failure','capture writer failed',
            'ConnectTimeout','ReadTimeout','WriteTimeout','PoolTimeout','TimeoutError','ConnectionResetError',
            'ConnectionRefusedError','ConnectionAbortedError','ConnectionError','OSError','RuntimeError','ValueError',
            'ReadError','WriteError','ConnectError','RemoteProtocolError','ProtocolError','RequestError',
            'SpotTransportError','SpotPortPoolError','SpotPortPoolInitError','SpotPortReuseViolation','SpotPortPoolExhausted',
            'SpotPortBindError','SpotTransportTimeout','SpotTransportConnectTimeout','SpotTransportReadTimeout',
            'SpotTransportRequestError','SpotTransportProtocolError','SpotTransportClosedError',
            'ok','error','idle','upstream','cache','image','temperature','internal_temperature','diagnostic','connection_test',
            'focus_read','focus_write','actuator_read','actuator_write',
            'failure','shutdown_cancelled','caller_cancelled','late_worker_success','late_worker_failure',
            'upstream-timeout','upstream-http-error','upstream-request-error','empty-body','shutdown',
            'invalid-image-html','invalid-image-payload',
            'Use administrator native x64 Windows PowerShell 5.1.',
            'Runtime changed; do not join new counters to historical evidence.','Expected exact current v1.0.25 build.')
        $preview = if ($Value -cin $allowed) { $Value } else { '<text withheld: not an approved diagnostic literal>' }
        return [pscustomobject]@{present=$true;preview=$preview;sha256=(TextHash $Value);chars=$Value.Length;filtered=($preview -cne $Value)}
    }
    function SpotDetail {
        param([object]$Value)
        if ($null -eq $Value) { return [pscustomobject]@{present=$false;known_fields=[pscustomobject]@{};unparsed=$false} }
        Need ($Value -is [string]) 'Invalid error detail type.'
        $selected = [ordered]@{}
        if ($Value.Length -le 8192) {
            foreach ($key in @('code','upstream_status','transport_error_type','transport_os_error_code','request_elapsed_ms','payload_rejection','error_type')) {
                # Python dict repr is NOT JSON. Select only literal known key/value tokens; never execute it.
                $pattern = "(?:\{|,\s*)'"+$key+"':\s*(?<v>None|True|False|-?\d+(?:\.\d+)?|'[A-Za-z0-9_.-]{1,80}')(?=,|\})"
                $matches = [regex]::Matches($Value,$pattern)
                if ($matches.Count -eq 1) {
                    $literal = $matches[0].Groups['v'].Value
                    if ($literal -ceq 'None') { $selected[$key] = $null }
                    elseif ($literal -ceq 'True') { $selected[$key] = $true }
                    elseif ($literal -ceq 'False') { $selected[$key] = $false }
                    elseif ($literal.StartsWith("'")) { $selected[$key] = (SafeText $literal.Trim("'")).preview }
                    else { $selected[$key] = [decimal]::Parse($literal,[Globalization.CultureInfo]::InvariantCulture) }
                }
            }
        }
        return [pscustomobject]@{present=$true;sha256=(TextHash $Value);known_fields=[pscustomobject]$selected;unparsed=($selected.Count -eq 0);complete_parse_claimed=$false}
    }
    function DecodeObject {
        param([string]$Text)
        Need (-not [string]::IsNullOrWhiteSpace($Text) -and $Text.TrimStart().StartsWith('{',[StringComparison]::Ordinal)) 'Expected single JSON object.'
        $value = ConvertFrom-Json -InputObject $Text
        Need ($value -is [pscustomobject] -and $value -isnot [Array]) 'Invalid JSON root shape.'
        return ,$value
    }
    function LocalGet {
        param([string]$Endpoint)
        Need ($Endpoint -cin @('health','api/observability/errors?limit=200','api/spot/config','api/config')) 'Unapproved diagnostic endpoint.'
        $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
        $request.Method='GET'; $request.Proxy=$null; $request.AllowAutoRedirect=$false
        $request.Timeout=10000; $request.ReadWriteTimeout=10000
        $response=$null; $stream=$null; $buffer=[IO.MemoryStream]::new(); $budget=[Diagnostics.Stopwatch]::StartNew()
        try {
            $response=$request.GetResponse()
            Need ([int]$response.StatusCode -eq 200) 'Diagnostic response is not HTTP 200.'
            $stream=$response.GetResponseStream(); $chunk=New-Object byte[] 8192
            while (($count=$stream.Read($chunk,0,$chunk.Length)) -gt 0) {
                Need ($buffer.Length+$count -le 2097152 -and $budget.Elapsed.TotalSeconds -le 20) 'Diagnostic response size/time budget exceeded.'
                $buffer.Write($chunk,0,$count)
            }
            return DecodeObject ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
        } finally {
            if ($null -ne $stream) { $stream.Dispose() }
            if ($null -ne $response) { $response.Dispose() }
            $buffer.Dispose()
        }
    }
    function RuntimeAnchor {
        $backends=@(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
        $apps=@(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
        $owners=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
        Need ($backends.Count -eq 1 -and $owners.Count -eq 1 -and $owners[0] -eq $backends[0].Id) 'Backend/listener identity is ambiguous.'
        $backend=$backends[0]
        $parent=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$backend.Id)
        $main=@($apps | Where-Object Id -eq $parent.ParentProcessId)
        Need ($main.Count -eq 1 -and $backend.Path -ieq ($install+'\resources\backend\SmartFactoryBackend.exe')) 'Unexpected app/backend identity.'
        foreach ($app in $apps) { Need ($app.Path -ieq ($install+'\smart-factory.exe')) 'Unexpected app path.' }
        return [pscustomobject]@{main_pid=$main[0].Id;main_ticks=$main[0].StartTime.ToUniversalTime().Ticks;backend_pid=$backend.Id;backend_ticks=$backend.StartTime.ToUniversalTime().Ticks}
    }
    function SameRuntime {
        param([object]$A,[object]$B)
        foreach ($n in @('main_pid','main_ticks','backend_pid','backend_ticks')) { Need ($A.$n -eq $B.$n) 'Runtime changed; do not join new counters to historical evidence.' }
    }
    function ErrorSnapshot {
        param([object]$Response)
        $items=ListValue $Response 'items' 200; $summary=Field $Response 'summary'
        $size=CountValue $summary 'queue_size'; $repeats=CountValue $summary 'repeat_total'
        $rows=[Collections.Generic.List[object]]::new(); $sum=[long]0
        foreach ($item in $items) {
            $source=Scalar $item 'source'; Need ($source -is [string]) 'Invalid error source.'
            $sourceLabel=if($source -cin @('extruder','ls_plc','spot_image','spot','http','backend')) {$source} else {'other-source'}
            $repeat=CountValue $item 'repeat'; Need ($repeat -gt 0) 'Error repeat must be positive.'; $sum+=$repeat
            $status=Scalar $item 'status_code'
            if ($null -ne $status) { Need (($status -is [int] -or $status -is [long]) -and $status -ge 100 -and $status -le 599) 'Invalid error HTTP status.' }
            $time=Epoch (Scalar $item 'time'); Need ($null -ne $time -and $time.recorded) 'Missing error event timestamp.'
            $detail=Scalar $item 'detail'
            if ($null -ne $detail) { Need ($detail -is [string]) 'Invalid detail type.' }
            $detailView=if ($source -ceq 'spot_image') {SpotDetail $detail} else {[pscustomobject]@{withheld=$true;reason='device address or unapproved detail';present=($null -ne $detail)}}
            $rows.Add([pscustomobject]@{source=$sourceLabel;time=$time;repeat=$repeat;status_code=$status;
                error_type=(SafeText (Scalar $item 'error_type'));message=(SafeText (Scalar $item 'message'));detail=$detailView})
        }
        return [pscustomobject]@{checked_at=[DateTimeOffset]::Now.ToString('o');queue_size=$size;repeat_total=$repeats;returned_entries=$items.Count;
            items_summary_counts_match=($size -eq $items.Count -and $sum -eq $repeats);last_error=(Epoch (Scalar $summary 'last_error_at'));
            items_sha256=(TextHash ($items|ConvertTo-Json -Depth 8 -Compress));items=$rows.ToArray();
            limitation='Retained memory queue only; repeats may merge within 5 seconds. Items and summary are not atomic. No historical completeness or recovery approval.'}
    }
    function CommSnapshot {
        param([object]$Health)
        $comm=Field $Health 'comm'; $out=[ordered]@{}
        foreach ($name in @('extruder','ls_plc')) {
            $item=Field $comm $name; $connected=Scalar $item 'connected'; Need ($connected -is [bool]) 'Invalid connected flag.'
            $v=[ordered]@{connected=$connected}
            foreach ($n in @('read_failures','connect_failures','backoff_count','recovery_count','invalid_responses')) {$v[$n]=CountValue $item $n}
            foreach ($n in @('last_error_time','last_success_time','last_recovery_at')) {$v[$n]=Epoch (Scalar $item $n)}
            $v.current_downtime_sec=NumberValue (Scalar $item 'current_downtime_sec')
            $v.last_error=SafeText (Scalar $item 'last_error')
            $v.snapshot_error=SafeText (Scalar $item 'snapshot_error')
            $out[$name]=[pscustomobject]$v
        }
        return [pscustomobject]$out
    }
    function CaptureSnapshot {
        param([object]$Spot,[object]$Configuration)
        $image=Field $Spot 'image'; $capture=Field $Spot 'image_capture'
        $settings=Field (Field (Field $Configuration 'values') 'spot') 'image_capture'
        $enabled=Scalar $capture 'enabled'; Need ($enabled -is [bool]) 'Invalid capture enabled flag.'
        $mode=Scalar $capture 'mode'; Need ($mode -cin @('off','all','interval','event')) 'Invalid capture mode.'
        $counts=[ordered]@{}
        foreach ($n in @('queue_size','queue_capacity','enqueued_count','written_count','fact_row_count','dropped_count','failure_count')) {$counts[$n]=CountValue $capture $n}
        $times=[ordered]@{}
        foreach ($n in @('last_enqueue_at','last_write_at','last_error_at')) {$times[$n]=Epoch (Scalar $capture $n)}
        $port=[ordered]@{}
        foreach ($n in @('image_refresh_success_count','image_refresh_failure_count','source_port_transport_failure_count','source_port_reuse_violation_count','source_port_request_failure_event_count_total','source_port_request_failure_event_drop_count')) {$port[$n]=CountValue $image $n}
        $events=ListValue $image 'source_port_recent_request_failure_events' 256
        $eventRows=[Collections.Generic.List[object]]::new()
        foreach ($event in $events) {
            $when=Scalar $event 'event_at_utc'
            Need ($when -is [string] -and $when -cmatch '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$') 'Invalid transport event timestamp.'
            $date=[DateTimeOffset]::ParseExact($when,"yyyy-MM-dd'T'HH:mm:ss.fff'Z'",[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
            $kind=Scalar $event 'request_kind'; $state=Scalar $event 'state'
            $exception=$event.PSObject.Properties['exception_class']
            $exceptionView=if($null -eq $exception){[pscustomobject]@{present=$false}}else{SafeText $exception.Value}
            $eventRows.Add([pscustomobject]@{sequence=(CountValue $event 'event_sequence');at_utc=$when;at_kst=$date.ToOffset([TimeSpan]::FromHours(9)).ToString('o');
                request_kind=(SafeText $kind);state=(SafeText $state);exception=$exceptionView})
        }
        $max=CountValue $settings 'max_bytes'; Need ($max -gt 0) 'Invalid configured image limit.'
        $restart=Scalar $Configuration 'restart_required'; Need ($restart -is [bool]) 'Invalid pending restart flag.'
        $retained=$port.source_port_request_failure_event_count_total
        $overwritten=$port.source_port_request_failure_event_drop_count
        return [pscustomobject]@{checked_at=[DateTimeOffset]::Now.ToString('o');enabled=$enabled;mode=$mode;counts=[pscustomobject]$counts;times=[pscustomobject]$times;
            last_capture_error_code=(SafeText (Scalar $capture 'last_error_code'));image_status=(SafeText (Scalar $image 'image_status'));
            last_image_success=(Epoch (Scalar $image 'last_success_at'));last_image_error=(Epoch (Scalar $image 'last_error_at'));
            counters=[pscustomobject]$port;recent_transport_failures=$eventRows.ToArray();retained_transport_event_count=$events.Count;
            transport_retention_counts_match=($retained -eq $overwritten+$events.Count);
            configured_max_bytes=$max;configured_min_interval_sec=(NumberValue (Scalar $settings 'min_interval_sec'));configuration_restart_required=$restart;
            configured_values_are_effective_runtime_proof=$false;historical_drop_cause='UNDETERMINED_SIZE_LIMIT_OR_QUEUE_FULL';
            per_drop_time_or_reason_recorded_by_this_version=$false;previous_same_runtime_drop_count=467;
            delta_from_previous_sample=([long]$counts.dropped_count-467);counter_decreased_since_previous_sample=($counts.dropped_count -lt 467);
            limitation='Current queue occupancy cannot establish past queue fullness. Saved facts exclude pre-enqueue drops. Written count is per-process; fact row count may include older data. No saved images or fact files were scanned.'}
    }

    try {
        $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
        $current=[Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
        $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and
            $PSVersionTable.PSVersion.Minor -eq 1 -and $current -ieq $native -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Use administrator native x64 Windows PowerShell 5.1.'
        $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
        Write-Host '[STEP 1/4] Read-only error/capture detail inspection. Keep the app unchanged; no reset, clear, image requests or final YES.' -ForegroundColor Cyan
        $anchor=RuntimeAnchor
        SameRuntime ([pscustomobject]@{main_pid=6728;main_ticks=639245234920357237;backend_pid=7620;backend_ticks=639245234936285878}) $anchor
        $health=LocalGet 'health'
        Need ((Scalar $health 'app_version') -ceq '1.0.25' -and (Scalar (Field $health 'spot_temperature') 'build_git_commit') -ceq $expectedCommit) 'Expected exact current v1.0.25 build.'
        $comm=CommSnapshot $health
        Write-Host '[COMMUNICATION SNAPSHOT]'
        $comm|ConvertTo-Json -Depth 9
        Write-Host '[STEP 2/4] Read retained errors without removing them.'
        $before=ErrorSnapshot (LocalGet 'api/observability/errors?limit=200')
        Write-Host '[ERRORS BEFORE]'
        $before|ConvertTo-Json -Depth 10
        Write-Host '[STEP 3/4] Read capture counters, retained SPOT failure events and cached capture settings.'
        $capture=CaptureSnapshot (LocalGet 'api/spot/config') (LocalGet 'api/config')
        Write-Host '[CAPTURE AND SPOT FAILURE DETAILS]'
        $capture|ConvertTo-Json -Depth 10
        Write-Host '[STEP 4/4] Re-read retained errors and verify the same runtime; no automatic retry.'
        $after=ErrorSnapshot (LocalGet 'api/observability/errors?limit=200')
        SameRuntime $anchor (RuntimeAnchor)
        $unchanged=($before.items_sha256 -ceq $after.items_sha256 -and $before.queue_size -eq $after.queue_size -and $before.repeat_total -eq $after.repeat_total)
        if (-not $unchanged) { Write-Host '[ERRORS AFTER: CHANGED]'; $after|ConvertTo-Json -Depth 10 }
        [pscustomobject]@{result='V1025_ERROR_DETAILS_COLLECTED_REVIEW_REQUIRED';checked_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$diagnosticClock.Elapsed.TotalSeconds;
            runtime=$anchor;current_commit=$expectedCommit;queue_entries_before=$before.queue_size;queue_entries_after=$after.queue_size;
            queue_repeats_after=$after.repeat_total;queue_unchanged_during_reads=$unchanged;
            queue_consistency_before=$before.items_summary_counts_match;queue_consistency_after=$after.items_summary_counts_match;
            local_get_count=5;new_camera_requests=$false;file_writes_performed=$false;error_queue_cleared=$false;
            app_restart_performed=$false;product_changes_made=$false;packet_capture_started=$false;backup_or_restore_performed=$false;
            historical_drops_resolved=$false;installation_ready=$false;installation_started=$false;production_promotion_allowed=$false;
            limitation='Inspection only, not an all-clear. Only approved diagnostic literals are shown; unknown text is hash/length only. PLC device details and arbitrary error paths are omitted. Normal app request logging may occur. No config/tree re-verification or continuous observation.'}|ConvertTo-Json -Depth 8
        Write-Host '[DONE] Return all output. No files to move, no final YES and no error clearing.' -ForegroundColor Green
    } catch {
        Write-Host '[HOLD] Diagnostic stopped. Preserve output. No automatic retry, clear, restart, installation or rollback.' -ForegroundColor Yellow
        SafeText $_.Exception.Message | ConvertTo-Json -Depth 3
        throw 'Read-only diagnostic HOLD. See filtered reason above.'
    } finally {
        $env:PATH=$savedDiagnosticPath
        $env:PSModulePath=$savedDiagnosticModules
    }
}
