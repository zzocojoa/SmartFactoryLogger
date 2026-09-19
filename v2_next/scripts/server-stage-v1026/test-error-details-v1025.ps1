param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'read-error-details-v1025.ps1'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count -ne 0) {throw ($errors|Out-String)}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$OK,[string]$Name) if(-not $OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $rejected=$false;try{& $Code|Out-Null}catch{$rejected=$true};Check $rejected $Name}
$functions=$ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)
foreach($fn in $functions) {. ([scriptblock]::Create($fn.Extent.Text))}
Check ($functions.Count -eq 17) 'parse and import functions only, never server main'
$text=[IO.File]::ReadAllText($source)
$allowed=@($functions.Name)+@('Set-StrictMode','Get-Process','Get-NetTCPConnection','Get-CimInstance','Select-Object','Where-Object','ConvertFrom-Json','ConvertTo-Json','New-Object','Write-Host')
foreach($c in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true)|ForEach-Object {$_.GetCommandName()}|Sort-Object -Unique)) {
    Check ($null -eq $c -or $c -in $allowed) ('read-only command allowlist: '+$c)
}
Check ($text -notmatch 'File\]::|Directory\]::|Start-Process|Stop-Process|Remove-Item|Set-Content|Out-File|Invoke-Expression|Start-Sleep') 'no disk API, process mutation, evaluator or sleep'
Check ($text.Contains("`$request.Method='GET'; `$request.Proxy=`$null; `$request.AllowAutoRedirect=`$false")) 'fixed GET, proxy and redirects disabled'
$calls=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst] -and $n.GetCommandName() -ceq 'LocalGet'},$true))
Check ($calls.Count -eq 5) 'exactly five main endpoint queries'
foreach($endpoint in @('api/observability/errors/clear','api/observability/export','api/spot/live_image.jpg','api/spot/focus','api/config?write=true','https://outside.invalid')) {
    Reject {LocalGet $endpoint} ('unapproved endpoint rejected before any network: '+$endpoint)
}
foreach($literal in @('[]','[{}]','null','1','true','"text"','')) {Reject {DecodeObject $literal} ('root scalar/array rejected: '+$literal)}
Check ((Scalar (DecodeObject '{"v":true}') 'v') -eq $true) 'scalar boolean survives decoder'
foreach($literal in @('null','-1','1.1','"1"','true','[]','[1]','[true]','{}')) {
    $fixture=DecodeObject ('{"v":'+$literal+'}')
    Reject {CountValue $fixture 'v'} ('invalid counter/array rejected: '+$literal)
}
Check ((CountValue (DecodeObject '{"v":12}') 'v') -eq 12) 'integer counter accepted'
Check ((ListValue (DecodeObject '{"items":[]}') 'items' 200).Count -eq 0) 'empty array shape preserved'
Check ((ListValue (DecodeObject '{"items":[{}]}') 'items' 200).Count -eq 1) 'singleton object array shape preserved'
foreach($literal in @('null','{}','[1]','[[]]','[[{}]]')) {Reject {ListValue (DecodeObject ('{"items":'+$literal+'}')) 'items' 200} ('invalid item array rejected: '+$literal)}
Reject {ListValue (DecodeObject '{"items":[{},{}]}') 'items' 1} 'array output bound enforced'
foreach($value in @('123',$true,-1,[double]::NaN,[double]::PositiveInfinity,253402214401)) {Reject {Epoch $value} ('invalid timestamp rejected: '+[string]$value)}
Check ($null -eq (Epoch $null)) 'null timestamp retained, not epoch zero'
Check (-not (Epoch 0).recorded) 'explicit zero timestamp is not a historical date'
$time=Scalar (DecodeObject '{"v":1789124873.4726768}') 'v'
Check ($time -is [decimal]) 'PS5.1 JSON fractional epoch is Decimal'
Check ((Epoch $time).kst -ceq '2026-09-11T20:07:53.4720000+09:00') 'Decimal epoch converted to KST without type rejection'
Check ((SafeText 'No Body').preview -ceq 'No Body') 'known PLC message remains readable'
Check ((SafeText 'Extruder send timeout').preview -ceq 'Extruder send timeout') 'known extruder message remains readable'
foreach($sensitive in @('password=privatevalue','Authorization: Bearer privatevalue','api_key=privatevalue','cookie: privatevalue','secret=privatevalue','token=privatevalue')) {
    $v=SafeText $sensitive;Check ($v.filtered -and $v.preview -notmatch 'privatevalue') 'sensitive text withheld'
}
foreach($sensitive in @('Bearer synthetic123','Basic dXNlcjpwYXNz','Connection to plc.example.internal:502 failed','/private/project/evidence.txt','No Body plus private-value','ReadTimeout\nprivate-value','arbitrary free-form exception')) {
    $v=SafeText $sensitive
    Check ($v.filtered -and $v.preview -ceq '<text withheld: not an approved diagnostic literal>' -and $v.sha256 -ceq (TextHash $sensitive)) 'unknown text default denied with correlation hash'
}
Check ((SafeText 'ReadTimeout').preview -ceq 'ReadTimeout') 'known exception class remains readable'
foreach($literal in @('SpotTransportReadTimeout','SpotTransportConnectTimeout','SpotPortPoolInitError','SpotTransportClosedError',
    'upstream-timeout','upstream-request-error','upstream-http-error','invalid-image-html','empty-body',
    'focus_read','focus_write','actuator_read','actuator_write')) {
    Check ((SafeText $literal).preview -ceq $literal) ('verified v1.0.25 diagnostic literal remains readable: '+$literal)
}
Check ((SafeText 'failure').preview -ceq 'failure') 'known request event state remains readable'
$mixed=SafeText 'Failure http://private-host:8000/test?key=abc at 10.22.33.44:502 and C:\private\trace.txt'
Check ($mixed.preview -notmatch 'private-host|10\.22|private\\|key=abc') 'URLs addresses and paths removed from preview'
Check ((SafeText 'Connection to [fd00:1234::1] failed').preview -notmatch 'fd00:1234') 'IPv6 endpoint removed'
Check ((SafeText ('x'*9000)).preview -like '<text withheld*') 'oversize text withheld'
Check ((SafeText $null).present -eq $false) 'null error text explicit'
Reject {SafeText @('No Body')} 'singleton message array rejected'
function QueueFixture {
    return DecodeObject '{"items":[{"time":1789124873.4726768,"source":"ls_plc","message":"No Body","detail":"10.99.88.77:2004","path":null,"status_code":null,"error_type":null,"repeat":1},{"time":1789119326.2690365,"source":"spot_image","message":"SPOT image upstream failure","detail":"{\u0027code\u0027: \u0027transport-error\u0027, \u0027upstream_status\u0027: None, \u0027transport_error_type\u0027: \u0027ReadTimeout\u0027, \u0027transport_os_error_code\u0027: 10060, \u0027request_elapsed_ms\u0027: 1001.2, \u0027payload_rejection\u0027: False}","path":"/api/spot/live_image.jpg","status_code":502,"error_type":"ReadTimeout","repeat":1},{"time":1789100000.0,"source":"extruder","message":"Extruder send timeout","detail":"10.11.22.33:3000","path":null,"status_code":null,"error_type":null,"repeat":1}],"summary":{"queue_size":3,"repeat_total":3,"last_error_at":1789124873.4726768,"last_error_message":"DO_NOT_EXPORT","top_messages":["DO_NOT_EXPORT"]}}'
}
$q=ErrorSnapshot (QueueFixture)
Check ($q.queue_size -eq 3 -and $q.returned_entries -eq 3 -and $q.items_summary_counts_match) 'real error snapshot projects all three retained entries'
Check ($q.items[0].message.preview -ceq 'No Body' -and $q.items[0].detail.withheld) 'PLC detail withheld, message retained'
Check ($q.items[1].detail.known_fields.transport_error_type -ceq 'ReadTimeout' -and $q.items[1].detail.known_fields.request_elapsed_ms -eq [decimal]1001.2) 'Python repr projected without execution or quote substitution'
Check ($null -eq $q.items[1].detail.known_fields.upstream_status -and $q.items[1].detail.known_fields.payload_rejection -eq $false) 'Python None and False remain distinct'
Check (($q|ConvertTo-Json -Depth 12) -notmatch '10\.99|10\.11|DO_NOT_EXPORT|/api/spot/live') 'device endpoint, raw summary and arbitrary route excluded'
$mut=QueueFixture;$mut.summary.queue_size=4
Check (-not (ErrorSnapshot $mut).items_summary_counts_match) 'non-atomic summary mismatch reported, no forced retry or false corruption claim'
$empty=DecodeObject '{"items":[],"summary":{"queue_size":0,"repeat_total":0,"last_error_at":null}}'
Check ((ErrorSnapshot $empty).returned_entries -eq 0) 'empty retained queue handled without false history claim'
foreach($field in @('message','detail','source','time','repeat','status_code','error_type')) {
    $mut=QueueFixture;$mut.items[0].$field=@($mut.items[0].$field)
    Reject {ErrorSnapshot $mut} ('real error projection rejects singleton array: '+$field)
}
$mut=QueueFixture;$mut.items[0].repeat=0;Reject {ErrorSnapshot $mut} 'zero repeat rejected'
$mut=QueueFixture;$mut.items[0].status_code=0;Reject {ErrorSnapshot $mut} 'invalid HTTP status rejected'
$mut=QueueFixture;$mut.items[0].PSObject.Properties.Remove('message');Reject {ErrorSnapshot $mut} 'missing message not fabricated'
$v=SpotDetail "{'code': __import__('os').system('not-executed')}"
Check ($v.unparsed -and @($v.known_fields.PSObject.Properties).Count -eq 0) 'unapproved Python expression is never evaluated'
$v=SpotDetail "{'code': 'safe', 'password': 'secret-value'}"
Check (($v|ConvertTo-Json -Depth 6) -notmatch 'secret-value|password') 'unknown detail keys not echoed'
$v=SpotDetail "{'code': 'upstream-timeout', 'transport_error_type': 'SpotTransportReadTimeout'}"
Check ($v.known_fields.code -ceq 'upstream-timeout' -and $v.known_fields.transport_error_type -ceq 'SpotTransportReadTimeout') 'actual v1.0.25 error code and transport class survive literal projection'
function CommFixture {
    $v=DecodeObject '{"connected":true,"read_failures":1,"connect_failures":0,"backoff_count":1,"recovery_count":1,"invalid_responses":0,"current_downtime_sec":0.0,"last_error_time":1789124873.4726768,"last_success_time":1789135000.0,"last_recovery_at":1789124874.0,"last_error":"No Body","snapshot_error":null}'
    return [pscustomobject]@{comm=[pscustomobject]@{extruder=$v;ls_plc=$v}}
}
$c=CommSnapshot (CommFixture)
Check ($c.ls_plc.connected -and $c.ls_plc.recovery_count -eq 1 -and $c.ls_plc.current_downtime_sec -eq 0) 'communication current and recovery metrics projected without changing them'
$mut=CommFixture;$mut.comm.ls_plc.connected='true';Reject {CommSnapshot $mut} 'string connected flag rejected'
function CaptureFixture {
    $image=[ordered]@{image_status='ok';last_success_at=1789135732.7765694;last_error_at=1789119326.2690365}
    foreach($n in @('image_refresh_success_count','image_refresh_failure_count','source_port_transport_failure_count','source_port_reuse_violation_count','source_port_request_failure_event_count_total','source_port_request_failure_event_drop_count')) {$image[$n]=0}
    $image.source_port_request_failure_event_count_total=1
    $image.source_port_recent_request_failure_events=@([pscustomobject]@{event_sequence=3;event_at_utc='2026-09-11T09:35:26.269Z';request_kind='image';state='failure';exception_class='ReadTimeout';url='DO_NOT_EXPORT'})
    $capture=[ordered]@{enabled=$true;mode='all';last_enqueue_at=1789135732.0;last_write_at=1789135732.1;last_error_at=$null;last_error_code=$null}
    foreach($n in @('queue_size','queue_capacity','enqueued_count','written_count','fact_row_count','dropped_count','failure_count')) {$capture[$n]=0}
    $capture.queue_capacity=128;$capture.dropped_count=467;$capture.written_count=189983;$capture.fact_row_count=2422075
    return [pscustomobject]@{image=[pscustomobject]$image;image_capture=[pscustomobject]$capture}
}
function ConfigFixture {return DecodeObject '{"restart_required":false,"values":{"spot":{"image_capture":{"max_bytes":2000000,"min_interval_sec":1.0},"ip":"DO_NOT_EXPORT","url":"DO_NOT_EXPORT"}}}'}
$s=CaptureSnapshot (CaptureFixture) (ConfigFixture)
Check ($s.counts.dropped_count -eq 467 -and $s.delta_from_previous_sample -eq 0 -and -not $s.counter_decreased_since_previous_sample) 'historical 467 is not treated as new loss'
Check ($s.historical_drop_cause -ceq 'UNDETERMINED_SIZE_LIMIT_OR_QUEUE_FULL' -and -not $s.per_drop_time_or_reason_recorded_by_this_version) 'no invented per-drop cause or timestamp'
Check ($s.counts.written_count -ne $s.counts.fact_row_count) 'different process versus historical fact counts allowed'
Check ($s.transport_retention_counts_match -and $s.recent_transport_failures[0].at_kst -ceq '2026-09-11T18:35:26.2690000+09:00') 'retained transport failure event timestamp preserved'
Check (($s|ConvertTo-Json -Depth 10) -notmatch 'DO_NOT_EXPORT') 'SPOT full config and extra event fields excluded'
Check (-not $s.configured_values_are_effective_runtime_proof) 'cached max_bytes not declared runtime-effective proof'
$mut=CaptureFixture;$mut.image_capture.dropped_count=468;Check ((CaptureSnapshot $mut (ConfigFixture)).delta_from_previous_sample -eq 1) 'positive drop delta distinguished from old total'
$mut=CaptureFixture;$mut.image_capture.dropped_count=0;Check ((CaptureSnapshot $mut (ConfigFixture)).counter_decreased_since_previous_sample) 'decreased counter flagged, not an all-clear'
$mut=CaptureFixture;$mut.image.source_port_request_failure_event_drop_count=1;Check (-not (CaptureSnapshot $mut (ConfigFixture)).transport_retention_counts_match) 'inconsistent retention counts flagged'
$mut=CaptureFixture;$mut.image.source_port_recent_request_failure_events[0].PSObject.Properties.Remove('exception_class');Check (-not (CaptureSnapshot $mut (ConfigFixture)).recent_transport_failures[0].exception.present) 'optional exception class absence explicit'
foreach($field in @('dropped_count','written_count','queue_size','failure_count')) {$mut=CaptureFixture;$mut.image_capture.$field=@(1);Reject {CaptureSnapshot $mut (ConfigFixture)} ('capture array counter rejected: '+$field)}
$mut=ConfigFixture;$mut.values.spot.image_capture.max_bytes=$null;Reject {CaptureSnapshot (CaptureFixture) $mut} 'missing max bytes not defaulted'
$mut=CaptureFixture;$mut.image.source_port_recent_request_failure_events[0].event_at_utc='not-a-date';Reject {CaptureSnapshot $mut (ConfigFixture)} 'invalid transport time rejected'
$mut=CaptureFixture;$mut.image.source_port_recent_request_failure_events[0].event_at_utc='2026-99-11T09:35:26.269Z';Reject {CaptureSnapshot $mut (ConfigFixture)} 'invalid calendar timestamp rejected'
SameRuntime ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4}) ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4})
Check $true 'unchanged runtime accepted'
Reject {SameRuntime ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4}) ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=5})} 'PID reuse rejected'
foreach($name in @('historical_drops_resolved','installation_ready','installation_started','production_promotion_allowed','backup_or_restore_performed','error_queue_cleared','new_camera_requests')) {Check ($text.Contains($name+'=$false')) ('no false approval or mutation: '+$name)}
if([IO.File]::Exists($OutputRoot) -or [IO.Directory]::Exists($OutputRoot)){throw 'Existing fixture output is preserved.'}
[void][IO.Directory]::CreateDirectory($OutputRoot)
$result=[pscustomobject]@{result='V1025_ERROR_DETAIL_LOCAL_FIXTURES_PASS';powershell_version=$PSVersionTable.PSVersion.ToString();assertions=$checks.Count;source_sha256=(TextHash $text);checks=$checks.ToArray();server_main_executed=$false;network_queries_performed=$false;product_changes_made=$false}
$json=$result|ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $OutputRoot 'validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
