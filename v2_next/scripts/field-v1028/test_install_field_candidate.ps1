param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'install-field-candidate.ps1'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
# Only function definitions are loaded. Production top-level installation cannot run.
foreach($definition in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
    . ([scriptblock]::Create($definition.Extent.Text))
}
$root=[IO.Path]::GetFullPath($OutputRoot)
if(Test-Path -LiteralPath $root){throw 'test-output-already-exists'}
$null=[IO.Directory]::CreateDirectory($root)
$checks=[Collections.Generic.List[string]]::new()
function Pass([bool]$Value,[string]$Name){if(-not $Value){throw ('TEST:'+ $Name)};$checks.Add($Name)}
function Reject([scriptblock]$Action,[string]$Expected,[string]$Name){$caught=$null;try{& $Action}catch{$caught=$_.Exception.Message};Pass ($null -ne $caught -and $caught.Contains($Expected)) $Name}

AssertCold @{processes=@();listeners=@()};Pass $true 'cold-empty'
Reject {AssertCold @{processes=@(@{pid=123});listeners=@()}} 'application-or-port-active' 'reject-running-app'
Reject {AssertCold @{processes=@();listeners=@(@{port=8000})}} 'application-or-port-active' 'reject-listener-without-app'
Reject {Plain '\\server\share\file'} 'absolute-local-path' 'reject-network-path'
Reject {Plain 'C:\fixture:stream'} 'absolute-local-path' 'reject-named-input-stream'

$utf8=[Text.UTF8Encoding]::new($true,$true)
$text="[SETTINGS]`r`nlabel = 공장`r`n[SPOT]`r`nlow_signal_alarm_enabled = false`r`nlow_signal_comparator_verified = true`r`nconfig_verified_by = Operator1`r`n[NEXT]`r`nx = true`r`n"
$inputBytes=$utf8.GetPreamble()+$utf8.GetBytes($text)
$expected=$utf8.GetPreamble()+$utf8.GetBytes($text.Replace('low_signal_comparator_verified = true','low_signal_comparator_verified = false'))
$actual=DisableComparator $inputBytes
Pass ([Convert]::ToBase64String($actual) -ceq [Convert]::ToBase64String($expected)) 'only-comparator-value-changed-bom-korean-crlf-preserved'
Pass ([Convert]::ToBase64String((DisableComparator $expected)) -ceq [Convert]::ToBase64String($expected)) 'already-disabled-idempotent'
Reject {DisableComparator $utf8.GetBytes($text.Replace('low_signal_alarm_enabled = false','low_signal_alarm_enabled = true'))} 'low-signal-alarm-must-be-false' 'reject-enabled-alarm'
Reject {DisableComparator $utf8.GetBytes($text.Replace('[NEXT]','low_signal_comparator_verified = false' + "`r`n[NEXT]"))} 'single-comparator' 'reject-duplicate-comparator'
Reject {DisableComparator $utf8.GetBytes($text.Replace('[NEXT]','[SPOT]'))} 'single-spot-section' 'reject-duplicate-spot-section'
Reject {DisableComparator ([Text.Encoding]::Unicode.GetPreamble()+[Text.Encoding]::Unicode.GetBytes($text))} 'unsupported-utf16' 'reject-utf16-without-mutation'
$cp949=[Text.Encoding]::GetEncoding(949)
Pass ([Convert]::ToBase64String((DisableComparator $cp949.GetBytes($text))) -ceq [Convert]::ToBase64String($cp949.GetBytes($text.Replace('low_signal_comparator_verified = true','low_signal_comparator_verified = false')))) 'cp949-preserved'

$file=Join-Path $root 'fact.txt';[IO.File]::WriteAllText($file,'actual bytes')
$script:held=[Collections.Generic.List[IDisposable]]::new();$f=Fact $file
$locked=LockFile $file $f.sha256 $f.bytes
Reject {[IO.File]::WriteAllText($file,'tamper')} 'being used by another process' 'held-bytes-reject-rewrite'
$locked.Dispose()
Reject {LockFile $file ('0'*64)} 'locked-file-fact' 'reject-wrong-external-hash'
foreach($h in $script:held){$h.Dispose()};$script:held.Clear()

$roots=@('C:\one','C:\two');$backupRoot='C:\Users\user\Desktop\SmartFactory\Q123456'
$b=[pscustomobject]@{status='SELECTED_COLD_COPY_DEFAULT_AND_NAMED_DATA_STREAMS_VERIFIED';run_root=$backupRoot;source_roots=$roots;file_manifest_sha256=('a'*64);source_streams_preserved=$true;source_and_copy_default_and_named_streams_rehashed=$true;source_metadata_and_default_named_stream_membership_unchanged=$true;app_backend_port_absence_observed=$true;preceding_logger_service_instance_id='logger';preceding_operating_identity=@{backend_pid=37};time=[DateTimeOffset]::UtcNow.ToString('o')}
$r=[pscustomobject]@{schema='sfl-field-preinstall-close-review-v1';backup_result_sha256=('b'*64);backup_manifest_sha256=('a'*64);normal_shutdown_observed=$true;failed_checks=@();logger_service_instance_id='logger';backend_pid=37}
CheckBackup $b $r $backupRoot ('b'*64) ('a'*64) $roots;Pass $true 'backup-and-close-review-bound'
$r.backend_pid=38;Reject {CheckBackup $b $r $backupRoot ('b'*64) ('a'*64) $roots} 'close-review-generation' 'reject-other-closed-generation';$r.backend_pid=37
$r.failed_checks=@('forced');Reject {CheckBackup $b $r $backupRoot ('b'*64) ('a'*64) $roots} 'normal-shutdown-review' 'reject-failed-close-proof';$r.failed_checks=@()
$b.time=[DateTimeOffset]::UtcNow.AddHours(-4).ToString('o');Reject {CheckBackup $b $r $backupRoot ('b'*64) ('a'*64) $roots} 'backup-freshness' 'reject-stale-backup';$b.time=[DateTimeOffset]::UtcNow.ToString('o')
$b.source_streams_preserved=$false;Reject {CheckBackup $b $r $backupRoot ('b'*64) ('a'*64) $roots} 'backup-proof' 'reject-missing-stream-proof'

$tree=Join-Path $root 'tree';$null=[IO.Directory]::CreateDirectory($tree)
[IO.File]::WriteAllText((Join-Path $tree 'app.dat'),'payload')
[IO.File]::WriteAllText((Join-Path $tree 'Uninstall smart-factory.exe'),'synthetic-uninstaller')
$specs=[pscustomobject]@{'app.dat'=(Fact (Join-Path $tree 'app.dat'))}
$facts=PayloadFacts $tree $specs;Pass ($facts.Count -eq 2) 'exact-payload-and-allowed-uninstaller'
[IO.File]::WriteAllText((Join-Path $tree 'app.dat'),'changed');Reject {PayloadFacts $tree $specs} 'installed-payload-mismatch' 'reject-installed-tamper'
[IO.File]::WriteAllText((Join-Path $tree 'app.dat'),'payload');[IO.File]::WriteAllText((Join-Path $tree 'extra.dat'),'extra');Reject {PayloadFacts $tree $specs} 'unexpected-installed-file' 'reject-extra-installed-file'

$script:installerStarted=$false;$script:installerExit=$null
$ok=Join-Path $root 'fixture-ok.exe';$bad=Join-Path $root 'fixture-error.exe';$slow=Join-Path $root 'fixture-slow.exe'
Add-Type -TypeDefinition 'public class FixtureOk { public static int Main(string[] args) { return args.Length==2 && args[0]=="/S" && args[1]=="/currentuser" ? 0 : 91; } }' -OutputAssembly $ok -OutputType ConsoleApplication
Add-Type -TypeDefinition 'public class FixtureError { public static int Main() { return 17; } }' -OutputAssembly $bad -OutputType ConsoleApplication
Add-Type -TypeDefinition 'public class FixtureSlow { public static int Main() { System.Threading.Thread.Sleep(1500); return 0; } }' -OutputAssembly $slow -OutputType ConsoleApplication
foreach($case in @('ok','bad','timeout')){
    $script:resultRoot=Join-Path $root $case;$null=[IO.Directory]::CreateDirectory($script:resultRoot)
    if($case -eq 'ok'){RunInstaller $ok;Pass ($script:installerExit.actual_exit_code -eq 0) 'actual-child-exit-zero-and-arguments'}
    elseif($case -eq 'bad'){Reject {RunInstaller $bad} 'installer-nonzero-exit' 'actual-child-nonzero-rejected';Pass ($script:installerExit.actual_exit_code -eq 17) 'nonzero-exit-receipt-preserved'}
    else{Reject {RunInstaller $slow 50} 'installer-timeout-no-force-no-retry' 'timeout-without-force-or-retry';$p=@(Get-Process -Name 'fixture-slow' -ErrorAction SilentlyContinue);Pass ($p.Count -eq 1) 'timeout-child-remains-owned-alive';Pass ($p[0].WaitForExit(10000)) 'timed-out-fixture-exits-normally';$p[0].Dispose()}
}
$result=[ordered]@{status='PASS';checks=$checks.Count;names=$checks.ToArray();source_sha256=(Fact $source).sha256;server_accessed=$false;production_installation_performed=$false;forced_termination=$false}
[IO.File]::WriteAllText((Join-Path $root 'tests-result.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 5
