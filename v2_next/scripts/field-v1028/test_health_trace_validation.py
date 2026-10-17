"""Native PowerShell contract/cleanup tests; no administrator token or ETW start."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess


def quote(value):
    return "'"+str(value).replace("'", "''")+"'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output.resolve()
    root.mkdir()
    assert not ctypes.windll.shell32.IsUserAnAdmin()
    source = Path(__file__).parent
    names = ('invoke-field-run.template.ps1', 'invoke-trace-validation.ps1', 'invoke-health-trace.ps1')
    prefix = '''Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
foreach($path in @(SOURCES)){
 $t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$t,[ref]$e)
 if($e.Count){throw ($e|Out-String)}
 foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
}
function Check([bool]$value,[string]$reason){if(-not $value){throw $reason}}
'''.replace('SOURCES', ','.join(quote(source/n) for n in names))
    env = os.environ.copy()
    env['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    results = []

    def run(name, body, folder='System32', expected=0):
        script = root/(name+'.ps1')
        script.write_text(prefix+body, encoding='utf-8-sig')
        command = [f'C:/Windows/{folder}/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(script)]
        p = subprocess.run(command, env=env, capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        (root/(name+'.stdout.log')).write_bytes(p.stdout)
        (root/(name+'.stderr.log')).write_bytes(p.stderr)
        assert p.returncode == expected and not p.stderr, (name, p.returncode, p.stdout, p.stderr)
        value = json.loads(p.stdout)
        results.append(dict(name=name, actual_exit=p.returncode, result=value))
        return value

    run('contracts', r'''
$c=[pscustomobject]@{schema='sfl-health-trace-contract-v1';scope='LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC';run_id=('a'*32);channel_path='C:\fixture\trace-channel';package_sha256=('b'*64);backend_pid=100;backend_created_filetime=[long]134365056356121274;main_pid=101;duration_seconds=6;guard_seconds=30;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceContract $c $c.channel_path $c.package_sha256
$bad=@(@('schema','old'),@('scope','FIELD_QA'),@('run_id','bad'),@('channel_path','C:\other'),@('package_sha256',('0'*64)),@('backend_pid',$true),@('main_pid',100),@('duration_seconds',8),@('guard_seconds',8),@('backend_created_filetime','134365056356121274'),@('promotion_allowed',0),@('release_gate','PASS'))
foreach($row in $bad){$changed=$c|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1];$rejected=$false;try{Assert-HealthTraceContract $changed $c.channel_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('contract:'+ $row[0])}
$lease=[pscustomobject]@{schema='sfl-health-trace-lease-v1';scope=$c.scope;run_id=$c.run_id;instance=('SFLTrace_'+('d'*32));run_path='C:\fixture\T111111111111';parent_pid=500;parent_created_filetime='134365056356121274';guard_seconds=30;capture_seconds=6;stop_timeout_seconds=60;contract_sha256=('e'*64);package_sha256=$c.package_sha256;profile_sha256='603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486';release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256
$badLease=@(@('schema','sfl-local-trace-lease-v1'),@('guard_seconds',8),@('capture_seconds',30),@('stop_timeout_seconds',61),@('parent_pid',$true),@('parent_created_filetime','1'),@('contract_sha256','bad'),@('profile_sha256',('0'*64)),@('promotion_allowed',$true))
foreach($row in $badLease){$changed=$lease|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1];$rejected=$false;try{Assert-HealthTraceLease $changed $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('lease:'+ $row[0])}
$rejected=$false;try{Assert-TraceLease $lease $lease.run_path}catch{$rejected=$true};Check $rejected 'legacy scope accepted health lease'
@{status='PASS';accepted=2;rejected=($bad.Count+$badLease.Count+1)}|ConvertTo-Json
''')
    run('ready-binding', r'''
$c=[pscustomobject]@{run_id=('a'*32);scope='LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC'}
$h='b'*64;$files=[ordered]@{}
foreach($name in @('native-initial.json','runtime-initial.json','control-initial.json','configuration-initial.json')){$files[$name]=@{bytes=20;sha256=$h}}
$ready=[pscustomobject]@{schema='sfl-health-trace-collector-ready-v1';scope=$c.scope;run_id=$c.run_id;contract_sha256=$h;worker=@{pid=200;created_filetime=[long]134365056356121274};payload_reference_sha256=$h;configuration_reference_sha256=$h;initial_files=[pscustomobject]$files;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceReady $ready $c $h
$ready.worker.created_filetime='134365056356121274'
$rejected=$false;try{Assert-HealthTraceReady $ready $c $h}catch{$rejected=$true};Check $rejected 'worker generation type'
$ready.worker.created_filetime=[long]134365056356121274;$ready.initial_files.'native-initial.json'.sha256='bad'
$rejected=$false;try{Assert-HealthTraceReady $ready $c $h}catch{$rejected=$true};Check $rejected 'initial file hash'
@{status='PASS';accepted=1;rejected=2}|ConvertTo-Json
''')
    run('outlier-contracts', r'''
$c=[pscustomobject]@{schema='sfl-health-outlier-contract-v1';scope='LOCAL_HEALTH_OUTLIER_TRACE_DIAGNOSTIC';run_id=('a'*32);channel_path='C:\fixture\trace-channel';package_sha256=('b'*64);backend_pid=100;backend_created_filetime=[long]134365056356121274;main_pid=101;duration_seconds=900;guard_seconds=960;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceContract $c $c.channel_path $c.package_sha256
$lease=[pscustomobject]@{schema='sfl-health-outlier-lease-v1';scope=$c.scope;run_id=$c.run_id;instance=('SFLTrace_'+('d'*32));run_path='C:\fixture\T111111111111';parent_pid=500;parent_created_filetime='134365056356121274';guard_seconds=960;capture_seconds=900;stop_timeout_seconds=60;contract_sha256=('e'*64);package_sha256=$c.package_sha256;profile_sha256='603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486';release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256
$bad=@(@('schema','sfl-health-trace-contract-v1'),@('scope','LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC'),@('duration_seconds',6),@('duration_seconds',901),@('guard_seconds',30),@('guard_seconds',961))
foreach($row in $bad){$changed=$c|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1];$rejected=$false;try{Assert-HealthTraceContract $changed $c.channel_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('outlier:'+ $row[0])}
$lease.guard_seconds=30
$rejected=$false;try{Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected 'mixed lease guard'
$s=@{active=$false;elapsed=0}
$command={param($op,$file) if($op -ceq 'start'){$s.active=$true};if($op -ceq 'stop'){$s.active=$false};@{status='PASS';actual_exit_code=0;stdout=$(if($s.active){'WPR recording is in progress...'}else{'WPR is not recording'});stderr=''}}
$result=Invoke-TraceLifecycle @{instance=('SFLTrace_'+('f'*32));guard_seconds=960} $command {$true} {$false} {} {$s.elapsed} {$s.elapsed+=30} {}
Check ($result.reason -ceq 'guard-deadline' -and $s.elapsed -eq 960 -and $result.cleanup_confirmed -and -not $s.active) 'outlier independent deadline'
@{status='PASS';accepted=2;rejected=7;deadline=$s.elapsed;cleanup=$result.cleanup_confirmed;actual_etw_started=$false}|ConvertTo-Json
''')
    run('cpu-outlier-contracts', r'''
$c=[pscustomobject]@{schema='sfl-health-cpu-outlier-contract-v1';scope='LOCAL_HEALTH_CPU_OUTLIER_TRACE_DIAGNOSTIC';run_id=('a'*32);channel_path='C:\fixture\trace-channel';package_sha256=('b'*64);backend_pid=100;backend_created_filetime=[long]134365056356121274;main_pid=101;duration_seconds=900;guard_seconds=960;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceContract $c $c.channel_path $c.package_sha256
$lease=[pscustomobject]@{schema='sfl-health-cpu-outlier-lease-v1';scope=$c.scope;run_id=$c.run_id;instance=('SFLTrace_'+('d'*32));run_path='C:\fixture\T111111111111';parent_pid=500;parent_created_filetime='134365056356121274';guard_seconds=960;capture_seconds=900;stop_timeout_seconds=60;contract_sha256=('e'*64);package_sha256=$c.package_sha256;profile_sha256='3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee';release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256
$bad=@(@('schema','sfl-health-outlier-contract-v1'),@('scope','LOCAL_HEALTH_OUTLIER_TRACE_DIAGNOSTIC'),@('duration_seconds',6),@('guard_seconds',961))
foreach($row in $bad){$changed=$c|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1];$rejected=$false;try{Assert-HealthTraceContract $changed $c.channel_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('cpu-contract:'+ $row[0])}
foreach($hash in @('603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486',('0'*64))){
 $changed=$lease|ConvertTo-Json|ConvertFrom-Json;$changed.profile_sha256=$hash
 $rejected=$false;try{Assert-HealthTraceLease $changed $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected 'cpu profile mismatch accepted'
}
$changed=$lease|ConvertTo-Json|ConvertFrom-Json;$changed.schema='sfl-health-outlier-lease-v1';$changed.scope='LOCAL_HEALTH_OUTLIER_TRACE_DIAGNOSTIC'
$rejected=$false;try{Assert-HealthTraceLease $changed $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected 'cpu profile accepted in scheduling contract'
@{status='PASS';accepted=2;rejected=7;actual_etw_started=$false}|ConvertTo-Json
''')
    run('cpu-concurrent-contracts', r'''
$c=[pscustomobject]@{schema='sfl-health-cpu-concurrent-contract-v1';scope='LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC';run_id=('a'*32);channel_path='C:\fixture\trace-channel';package_sha256=('b'*64);backend_pid=100;backend_created_filetime=[long]134365056356121274;main_pid=101;duration_seconds=900;guard_seconds=960;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceContract $c $c.channel_path $c.package_sha256
$lease=[pscustomobject]@{schema='sfl-health-cpu-concurrent-lease-v1';scope=$c.scope;run_id=$c.run_id;instance=('SFLTrace_'+('d'*32));run_path='C:\fixture\T111111111111';parent_pid=500;parent_created_filetime='134365056356121274';guard_seconds=960;capture_seconds=900;stop_timeout_seconds=60;contract_sha256=('e'*64);package_sha256=$c.package_sha256;profile_sha256='3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee';release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256
foreach($row in @(@('schema','sfl-health-cpu-outlier-contract-v1'),@('scope','LOCAL_HEALTH_CPU_OUTLIER_TRACE_DIAGNOSTIC'),@('duration_seconds',901),@('guard_seconds',961))){
 $changed=$c|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1]
 $rejected=$false;try{Assert-HealthTraceContract $changed $c.channel_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('concurrent-contract:'+ $row[0])
}
foreach($row in @(@('schema','sfl-health-cpu-outlier-lease-v1'),@('scope','LOCAL_HEALTH_CPU_OUTLIER_TRACE_DIAGNOSTIC'),@('profile_sha256','603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486'),@('guard_seconds',961))){
 $changed=$lease|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1]
 $rejected=$false;try{Assert-HealthTraceLease $changed $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('concurrent-lease:'+ $row[0])
}
@{status='PASS';accepted=2;rejected=8;actual_etw_started=$false}|ConvertTo-Json
''')
    run('ready-concurrent-contracts', r'''
$c=[pscustomobject]@{schema='sfl-health-ready-concurrent-contract-v1';scope='LOCAL_HEALTH_READY_CONCURRENT_TRACE_DIAGNOSTIC';run_id=('a'*32);channel_path='C:\fixture\trace-channel';package_sha256=('b'*64);backend_pid=100;backend_created_filetime=[long]134365056356121274;main_pid=101;duration_seconds=900;guard_seconds=960;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceContract $c $c.channel_path $c.package_sha256
$lease=[pscustomobject]@{schema='sfl-health-ready-concurrent-lease-v1';scope=$c.scope;run_id=$c.run_id;instance=('SFLTrace_'+('d'*32));run_path='C:\fixture\T111111111111';parent_pid=500;parent_created_filetime='134365056356121274';guard_seconds=960;capture_seconds=900;stop_timeout_seconds=60;contract_sha256=('e'*64);package_sha256=$c.package_sha256;profile_sha256='03220768bee3245513b2ec4d9eeac2affd7ddffcd2c786f6a658146bdd8e2478';release_gate='HOLD';promotion_allowed=$false}
Assert-HealthTraceLease $lease $lease.run_path $c.package_sha256
foreach($row in @(@('schema','sfl-health-cpu-concurrent-contract-v1'),@('scope','LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC'),@('duration_seconds',901),@('guard_seconds',961))){
 $changed=$c|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1]
 $rejected=$false;try{Assert-HealthTraceContract $changed $c.channel_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('ready-contract:'+ $row[0])
}
foreach($row in @(@('schema','sfl-health-cpu-concurrent-lease-v1'),@('scope','LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC'),@('profile_sha256','3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee'),@('guard_seconds',961))){
 $changed=$lease|ConvertTo-Json|ConvertFrom-Json;$changed.($row[0])=$row[1]
 $rejected=$false;try{Assert-HealthTraceLease $changed $lease.run_path $c.package_sha256}catch{$rejected=$true};Check $rejected ('ready-lease:'+ $row[0])
}
@{status='PASS';accepted=2;rejected=8;actual_etw_started=$false}|ConvertTo-Json
''')
    run('independent-native-bootstrap', r'''
Initialize-TraceHandles
foreach($encoded in @('', 'bad-command', ('a'*24001))){
 $rejected=$false;try{[void][SflTraceParent]::StartIndependent($encoded,[Environment]::SystemDirectory)}catch{$rejected=$_.Exception.InnerException -is [ArgumentException]};Check $rejected 'invalid native command accepted'
}
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes('exit 7'))
$child=$null;$blocked=$false;$actual=$null;$blockedReason=$null
try{
 try{$child=[SflTraceParent]::StartIndependent($encoded,[Environment]::SystemDirectory)}catch{
  $errorNative=$_.Exception.InnerException
  if($errorNative -is [ComponentModel.Win32Exception] -and $errorNative.NativeErrorCode -eq 5){$blocked=$true;$blockedReason='access-denied'}
  elseif($errorNative -is [InvalidOperationException] -and $errorNative.Message -ceq 'independent-child-still-in-job'){$blocked=$true;$blockedReason='ancestor-job-retained-child-cleaned-before-resume'}else{throw}
 }
 if($child){Check ($child.WaitForExit(10000)) 'independent short child did not exit';$actual=$child.ExitCode;Check ($actual -eq 7) 'independent exit code'}
}finally{if($child){$child.Dispose()}}
@{status='PASS';invalid_inputs_rejected=3;ancestor_job_blocked=$blocked;blocked_reason=$blockedReason;child_exit=$actual;actual_etw_started=$false}|ConvertTo-Json
''')
    channel = root/'messages'
    channel.mkdir()
    run('messages', r'''
$channel=CHANNEL
Write-HealthTraceMessage $channel 'capture-go.json' @{value=1}
$fact=Get-RunFact ($channel+'\capture-go.json')
$rejected=$false;try{Write-HealthTraceMessage $channel 'capture-go.json' @{value=2}}catch{$rejected=$true};Check $rejected 'overwrote go'
Check ((Get-RunFact ($channel+'\capture-go.json')).sha256 -ceq $fact.sha256) 'original modified'
Write-HealthTraceMessage $channel 'capture-failed.json' @{status='FAIL'}
Check ((Read-HealthTraceJson ($channel+'\capture-failed.json')).status -ceq 'FAIL') 'failure message'
$rejected=$false;try{Write-HealthTraceMessage $channel '..\escape.json' @{value=1}}catch{$rejected=$true};Check $rejected 'name traversal'
@{status='PASS';existing_bytes_preserved=$true;failure_published=$true}|ConvertTo-Json
'''.replace('CHANNEL', quote(channel)))
    run('thirty-second-lifecycle', r'''
$cases=@()
foreach($scenario in @('normal','parent-exited','deadline')){
 $fixtureState=@{active=$false;elapsed=0;ready=$false;intent=$false;ops=[Collections.Generic.List[string]]::new()}
 $command={param($op,$file) $fixtureState.ops.Add($op);if($op -ceq 'start'){$fixtureState.active=$true};if($op -ceq 'stop'){$fixtureState.active=$false};$text=if($fixtureState.active){'WPR recording is in progress...'}else{'WPR is not recording'};@{status='PASS';actual_exit_code=0;stdout=$text;stderr=''}}
 $lease=@{instance=('SFLTrace_'+('f'*32));guard_seconds=30}
 $result=Invoke-TraceLifecycle $lease $command {return ($scenario -cne 'parent-exited' -or -not $fixtureState.ready)} {return ($scenario -ceq 'normal')} {$fixtureState.ready=$true} {$fixtureState.elapsed} {$fixtureState.elapsed+=10} {$fixtureState.intent=$true}
 $expected=if($scenario -ceq 'normal'){'controller-requested-stop'}elseif($scenario -ceq 'parent-exited'){'controller-exited'}else{'guard-deadline'}
 Check ($result.status -ceq 'CONTROL_FLOW_COMPLETE' -and $result.cleanup_confirmed -and $result.reason -ceq $expected -and -not $fixtureState.active) 'cleanup scenario'
 Check ($fixtureState.ops[-2] -ceq 'stop' -and $fixtureState.ops[-1] -ceq 'status') 'cleanup order'
 if($scenario -ceq 'deadline'){Check ($fixtureState.elapsed -eq 30) 'wrong deadline'}
 $cases+=@{scenario=$scenario;reason=$result.reason;elapsed=$fixtureState.elapsed;cleanup=$result.cleanup_confirmed}
}
@{status='PASS';cases=$cases;actual_etw_started=$false}|ConvertTo-Json -Depth 6
''')
    for arch in ('System32', 'SysWOW64'):
        body = '& '+quote(source/'invoke-health-trace.ps1')+" -PackageRoot 'unused' -ExpectedManifestSha256 '"+'a'*64+"'\nexit $LASTEXITCODE\n"
        value = run('prerequisite-'+arch, body, arch, expected=1)
        expected = 'administrator PowerShell required' if arch == 'System32' else 'native PS5.1 x64 required'
        assert value['status'] == 'FAIL' and value['errors'] == [expected]
    result = dict(status='PASS', cases=results, actual_etw_started=False,
                  sources={n: hashlib.sha256((source/n).read_bytes()).hexdigest() for n in names},
                  release_gate='HOLD', promotion_allowed=False)
    (root/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
