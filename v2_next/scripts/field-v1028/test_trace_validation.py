"""PS5.1 controller fault tests; no ETW session or production app is started."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psutil


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output.resolve()
    root.mkdir()
    source = Path(__file__).with_name('invoke-trace-validation.ps1').resolve()
    helper = source.with_name('invoke-field-run.template.ps1')
    native = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    env = os.environ.copy()
    env['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    env['SFL_TRACE_UNEXPECTED_ENV'] = 'test only'
    prefix = """Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
foreach($source in @(SOURCES)){
 $t=$null;$e=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$t,[ref]$e)
 if($e.Count){throw ($e|Out-String)}
 foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
}
function Check([bool]$v,[string]$why){if(-not $v){throw $why}}
""".replace('SOURCES', ','.join(map(quote, (helper, source))))
    receipts = []

    def run(name, body):
        script = root / (name + '.ps1')
        script.write_text(prefix + body, encoding='utf-8-sig')
        result = subprocess.run(
            [native, '-NoProfile', '-NonInteractive', '-File', str(script)],
            capture_output=True, env=env, timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (root / (name + '.stdout.log')).write_bytes(result.stdout)
        (root / (name + '.stderr.log')).write_bytes(result.stderr)
        record = dict(name=name, exit_code=result.returncode)
        save(root / (name + '.json'), record)
        receipts.append(record)
        assert result.returncode == 0 and not result.stderr, (
            record, result.stdout.decode('utf-8', 'replace'),
            result.stderr.decode('utf-8', 'replace'),
        )
        return json.loads(result.stdout)

    cases = run('lifecycle', r"""
$records=@()
foreach($case in @('normal','parent-exit','deadline','parent-dead','foreign','unknown','start-fail','start-throw','ready-throw','intent-throw','stop-throw','query-throw','cancel-throw','stop-fail')){
 $s=@{case=$case;state='ABSENT';calls=[Collections.Generic.List[string]]::new();intent=$false;parent_calls=0;queries=0}
 if($case -eq 'foreign'){$s.state='ACTIVE'}
 if($case -eq 'unknown'){$s.state='UNKNOWN'}
 $lease=@{instance='SFLTrace_'+('a'*32);guard_seconds=8}
 $command={param($op,$file)
   $s.calls.Add($op)
   if($op -eq 'start'){$s.state='ACTIVE';if($s.case -eq 'start-throw'){throw 'injected-start'};if($s.case -eq 'start-fail'){return @{status='FAIL';actual_exit_code=1;stdout=''}}}
   if($op -eq 'stop'){
     if($s.case -in @('stop-throw','cancel-throw')){throw 'injected-stop'}
     if($s.case -eq 'stop-fail'){return @{status='FAIL';actual_exit_code=1;stdout=''}}
     $s.state='ABSENT'
   }
   if($op -eq 'cancel'){if($s.case -eq 'cancel-throw'){throw 'injected-cancel'};$s.state='ABSENT'}
   if($op -eq 'status'){$s.queries++;if($s.case -eq 'query-throw' -and $s.queries -eq 3){throw 'injected-query'}}
   $out=switch($s.state){'ABSENT' {'WPR is not recording'} 'ACTIVE' {'WPR recording is in progress...'} default {'unrecognized'}}
   return @{status='PASS';actual_exit_code=0;stdout=$out}
 }
 $r=Invoke-TraceLifecycle $lease $command {
   $s.parent_calls++
   return ($s.case -ne 'parent-dead' -and -not ($s.case -eq 'parent-exit' -and $s.parent_calls -gt 1))
 } {$s.case -notin @('parent-exit','deadline')} {
   if($s.case -eq 'ready-throw'){throw 'injected-ready'}
 } {8} {throw 'unexpected-pause'} {
   if($s.case -eq 'intent-throw'){throw 'injected-intent'};$s.intent=$true
 }
 if($case -in @('foreign','unknown','parent-dead','intent-throw')){
   Check (($s.calls -join ',') -ceq 'status' -and -not $r.start_attempted) ('no foreign mutation '+$case)
 }else{
   Check ($s.intent -and $s.calls.Contains('stop')) ('durable intent/cleanup '+$case)
   Check ($r.cleanup_confirmed -eq ($case -ne 'cancel-throw')) ('cleanup verdict '+$case)
 }
 if($case -in @('normal','parent-exit','deadline')){Check ($r.status -ceq 'CONTROL_FLOW_COMPLETE') ('success '+$case)}
 else{Check ($r.status -ceq 'FAIL') ('failure retained '+$case)}
 if($case -eq 'normal'){Check ($r.reason -ceq 'controller-requested-stop') 'normal reason'}
 if($case -eq 'parent-exit'){Check ($r.reason -ceq 'controller-exited') 'death reason'}
 if($case -eq 'deadline'){Check ($r.reason -ceq 'guard-deadline') 'deadline reason'}
 Check ($r.release_gate -ceq 'HOLD' -and -not $r.promotion_allowed) 'no promotion'
 $records+=@{case=$case;calls=@($s.calls);result=$r}
}
$records|ConvertTo-Json -Depth 20
""")
    assert len(cases) == 14
    run('identity-and-ownership', r"""
Initialize-TraceHandles
$created=[Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc()
$p=[SflTraceParent]::new([uint32]$PID,$created)
try{Check ($p.Alive()) 'exact live parent handle'}finally{$p.Dispose()}
Check ([SflTraceParent]::GenerationAlive([uint32]$PID,$created)) 'exact generation alive'
Check (-not [SflTraceParent]::GenerationAlive([uint32]$PID,($created+1))) 'reused identity not same generation'
$failed=$false;try{$bad=[SflTraceParent]::new([uint32]$PID,($created+1));$bad.Dispose()}catch{$failed=$true}
Check $failed 'mismatched held handle rejected'
$lease=@{instance='SFLTrace_'+('a'*32)}
$intent=[pscustomobject]@{schema='sfl-trace-start-intent-v1';instance=$lease.instance;lease_sha256=('b'*64);manifest_sha256=('c'*64);observed_before_start='ABSENT';guard_pid=$PID;guard_created_filetime=$created.ToString()}
Assert-TraceRecovery $intent $lease ('b'*64) ('c'*64) {param($p,$c) $false}
foreach($fault in @('alive','unknown','lease','manifest','instance','preexisting')){
 $i=$intent|ConvertTo-Json|ConvertFrom-Json
 if($fault -eq 'lease'){$i.lease_sha256='x'}
 if($fault -eq 'manifest'){$i.manifest_sha256='x'}
 if($fault -eq 'instance'){$i.instance='other'}
 if($fault -eq 'preexisting'){$i.observed_before_start='ACTIVE'}
 $failed=$false
 try{Assert-TraceRecovery $i $lease ('b'*64) ('c'*64) {param($p,$c) if($fault -eq 'unknown'){throw 'identity query failed'};return ($fault -eq 'alive')}}catch{$failed=$true}
 Check $failed ('recovery rejected '+$fault)
}
foreach($out in @('','unrecognized',"WPR is not recording`nWPR recording is in progress...")){
 Check ((Read-TraceState @{status='PASS';actual_exit_code=0;stdout=$out}) -ceq 'UNKNOWN') 'ambiguous state rejected'
}
Check ((Read-TraceState @{status='FAIL';actual_exit_code=0;stdout='WPR is not recording'}) -ceq 'UNKNOWN') 'failed command not absence'
@{status='PASS';in_job=[SflTraceParent]::CurrentInJob()}|ConvertTo-Json
""")
    fixture = root / 'fixture.py'
    fixture.write_text('''import json, os, subprocess, sys, time
from pathlib import Path
mode, marker = sys.argv[1], Path(sys.argv[2])
if mode in ('linger', 'hang'):
    child = subprocess.Popen([sys.executable, '-S', __file__, 'child', str(marker), '.2' if mode == 'linger' else '60'], creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 3
    while not marker.exists() and time.monotonic() < deadline: time.sleep(.01)
    if mode == 'hang': time.sleep(60)
elif mode == 'child':
    marker.write_text(json.dumps({'pid': os.getpid()}))
    time.sleep(float(sys.argv[3]))
elif mode == 'args':
    print(json.dumps({'args': sys.argv[3:], 'unexpected': os.environ.get('SFL_TRACE_UNEXPECTED_ENV')}))
elif mode == 'exit7': sys.exit(7)
''', encoding='utf-8')
    environment_root = root / 'environment'
    for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
        (environment_root / key).mkdir(parents=True)
    arguments_body = 'Initialize-RunNative\n$rows=@()\n'
    arguments_body += '$package=' + quote(root / 'package with spaces') + '\n'
    arguments_body += '$directory=' + quote(root) + '\n'
    arguments_body += "$instance='SFLTrace_" + os.urandom(16).hex() + "'\n"
    arguments_body += r'''
foreach($op in @('status','start','stop','cancel')){
 $argv=@(Get-TraceArguments $op $package $directory $instance 'trace.etl')
 $expected=switch($op){
  'status' {@('-status','-instancename',$instance)}
  'start' {@('-start',($package+'\SFLThreadScheduling.wprp!SFLThreadScheduling.light'),'-instancename',$instance)}
  'stop' {@('-stop',($directory+'\trace.etl'),'-skipPdbGen','-instancename',$instance)}
  'cancel' {@('-cancel','-instancename',$instance)}
 }
 Check (($argv|ConvertTo-Json -Compress) -ceq ($expected|ConvertTo-Json -Compress)) ('argv boundaries '+$op)
 $actualArgs=@('-S',FIXTURE,'args',MARKER)+$argv
 $r=Invoke-TraceNative EXECUTABLE $actualArgs ($directory+'\argv-'+$op) ENVIRONMENT 10
 Check ($r.status -ceq 'PASS' -and $r.actual_exit_code -eq 0 -and $r.job_after_cleanup[1] -eq 0) ('argv native child '+$op)
 $received=$r.stdout|ConvertFrom-Json
 Check (($received.args|ConvertTo-Json -Compress) -ceq ($expected|ConvertTo-Json -Compress)) ('received argv '+$op)
 $rows+=@{operation=$op;arguments=$received.args}
}
$rejected=0
foreach($fault in @('operation','instance','output','existing')){
 try{
  if($fault -eq 'operation'){Get-TraceArguments 'unscoped' $package $directory $instance ''}
  if($fault -eq 'instance'){Get-TraceArguments 'status' $package $directory 'other' ''}
  if($fault -eq 'output'){Get-TraceArguments 'stop' $package $directory $instance '../outside.etl'}
  if($fault -eq 'existing'){
   [IO.File]::WriteAllText(($directory+'\trace.etl'),'fixture only')
   Get-TraceArguments 'stop' $package $directory $instance 'trace.etl'
  }
 }catch{$rejected++}
}
Check ($rejected -eq 4) 'unsafe command rejection'
@{rows=$rows;rejections=$rejected}|ConvertTo-Json -Depth 10
'''.replace('FIXTURE', quote(fixture)).replace('MARKER', quote(root / 'unused.json'))
    arguments_body = arguments_body.replace('EXECUTABLE', quote(sys._base_executable))
    arguments_body = arguments_body.replace('ENVIRONMENT', quote(environment_root))
    argument_results = run('wpr-argument-boundaries', arguments_body)
    assert len(argument_results['rows']) == 4 and argument_results['rejections'] == 4
    exit_body = '$native=' + quote(native) + '\n$directory=' + quote(root) + '\n'
    exit_body += r'''
$rows=@()
foreach($delay in @(0,250)){
 foreach($code in @(0,1,23)){
  $line='-NoProfile -NonInteractive -Command "Start-Sleep -Milliseconds '+$delay+';[Console]::WriteLine(''stdout-final'');[Console]::Error.WriteLine(''stderr-final'');[Environment]::Exit('+$code+')"'
  $name=$delay.ToString()+'-'+$code
  $p=Start-TraceProcess $native $line ($directory+'\exit-'+$name+'.stdout.log') ($directory+'\exit-'+$name+'.stderr.log')
  try{
   Check ($p.WaitForExit(10000)) 'fixture bounded exit'
   Check ($null -ne $p.ExitCode -and $p.ExitCode -eq $code) 'actual retained exit code'
   $logs=Read-TraceProcessLogs $p ($directory+'\exit-'+$name+'.stdout.log') ($directory+'\exit-'+$name+'.stderr.log')
   Check ($logs.writers_closed -and $logs.stdout.Trim() -ceq 'stdout-final' -and $logs.stderr.Trim() -ceq 'stderr-final') 'redirected final output complete'
   $rows+=@{delay_ms=$delay;expected=$code;actual=$p.ExitCode;sharing_retries=$logs.sharing_retries}
  }finally{$p.Dispose()}
 }
}
$rows|ConvertTo-Json
'''
    exit_results = run('redirected-process-exit-codes', exit_body)
    assert len(exit_results) == 6
    log_body = '$native=' + quote(native) + '\n$directory=' + quote(root) + '\n'
    log_body += r'''
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Threading;
public sealed class SflDelayedLogWriter {
 public ManualResetEvent Ready=new ManualResetEvent(false);
 public Thread Worker;
 public Exception Error;
 public SflDelayedLogWriter(string path,int delay) {
  Worker=new Thread(()=>{
   try {using(var f=new FileStream(path,FileMode.Create,FileAccess.Write,FileShare.ReadWrite)){
    var b=Encoding.UTF8.GetBytes("prefix-"); f.Write(b,0,b.Length);f.Flush();Ready.Set();Thread.Sleep(delay);
    b=Encoding.UTF8.GetBytes("final");f.Write(b,0,b.Length);f.Flush();
   }}catch(Exception e){Error=e;Ready.Set();}
  });Worker.IsBackground=true;Worker.Start();
 }
}
'@
$p=Start-TraceProcess $native '-NoProfile -NonInteractive -Command "exit 0"' ($directory+'\log-fixture.stdout.log') ($directory+'\log-fixture.stderr.log')
$rows=@()
try{
 Check ($p.WaitForExit(10000)) 'fixture terminal'
 foreach($role in @('stdout','stderr')){
  $out=$directory+'\delayed-'+$role+'.out';$err=$directory+'\delayed-'+$role+'.err'
  [IO.File]::WriteAllText($out,'stable');[IO.File]::WriteAllText($err,'stable')
  $writer=[SflDelayedLogWriter]::new($(if($role -eq 'stdout'){$out}else{$err}),350)
  try{
   Check ($writer.Ready.WaitOne(3000) -and $null -eq $writer.Error) 'writer ready'
   $originalRejected=$false
   try{[void][IO.File]::ReadAllText($(if($role -eq 'stdout'){$out}else{$err}))}catch [IO.IOException]{$originalRejected=($_.Exception.HResult -band 0xffff) -eq 32}
   Check $originalRejected 'original reader sharing violation reproduced'
   $logs=Read-TraceProcessLogs $p $out $err 2000
   Check ($logs.writers_closed -and $logs.sharing_retries -gt 0 -and $logs.$role -ceq 'prefix-final') 'wait for complete writer output'
   $rows+=@{case='delayed-'+$role;retries=$logs.sharing_retries;original_reader_rejected=$originalRejected}
  }finally{Check ($writer.Worker.Join(3000)) 'writer joined';$writer.Ready.Dispose()}
 }
 $out=$directory+'\timeout.out';$err=$directory+'\timeout.err';[IO.File]::WriteAllText($err,'')
 $writer=[SflDelayedLogWriter]::new($out,600)
 try{
  Check ($writer.Ready.WaitOne(3000)) 'timeout writer ready'
  $clock=[Diagnostics.Stopwatch]::StartNew();$rejected=$false
  try{Read-TraceProcessLogs $p $out $err 100}catch{$rejected=$_.Exception.Message -ceq 'controller-logs-not-closed-do-not-rerun'}
  Check ($rejected -and $clock.ElapsedMilliseconds -lt 1500) 'bounded log timeout'
  $rows+=@{case='writer-timeout';elapsed_ms=$clock.ElapsedMilliseconds}
 }finally{Check ($writer.Worker.Join(3000)) 'timeout writer joined';$writer.Ready.Dispose()}
 foreach($role in @('stdout','stderr')){
  $out=$directory+'\oversize-'+$role+'.out';$err=$directory+'\oversize-'+$role+'.err'
  [IO.File]::WriteAllText($out,'');[IO.File]::WriteAllText($err,'')
  [IO.File]::WriteAllBytes($(if($role -eq 'stdout'){$out}else{$err}),[byte[]]::new(65537))
  $rejected=$false
  try{Read-TraceProcessLogs $p $out $err}catch{$rejected=$_.Exception.Message -ceq 'controller-log-budget'}
  Check $rejected 'oversize logs rejected';$rows+=@{case='oversize-'+$role}
 }
 $clock=[Diagnostics.Stopwatch]::StartNew();$rejected=$false
 try{Read-TraceProcessLogs $p ($directory+'\missing.out') $err}catch [IO.FileNotFoundException]{$rejected=$true}
 Check ($rejected -and $clock.ElapsedMilliseconds -lt 1000) 'missing logs fail without retry'
 $rows+=@{case='missing-log'}
}finally{$p.Dispose()}
$p=Start-TraceProcess $native '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 2"' ($directory+'\live.out') ($directory+'\live.err')
try{
 $rejected=$false
 try{Read-TraceProcessLogs $p ($directory+'\live.out') ($directory+'\live.err')}catch{$rejected=$_.Exception.Message -ceq 'trace-log-process-still-running'}
 Check $rejected 'live process log read rejected';$rows+=@{case='live-process'}
 Check ($p.WaitForExit(10000)) 'live fixture terminal'
}finally{$p.Dispose()}
$rows|ConvertTo-Json -Depth 6
'''
    log_results = run('redirected-log-finalization', log_body)
    assert len(log_results) == 7
    readonly_body = 'Initialize-RunNative\n'
    readonly_body += "$instance='SFLTrace_" + os.urandom(16).hex() + "'\n"
    readonly_body += '$argv=@(Get-TraceArguments status ' + quote(source.parent)
    readonly_body += ' ' + quote(root) + " $instance '')\n"
    readonly_body += r"$r=Invoke-TraceNative 'C:\Windows\System32\wpr.exe' $argv "
    readonly_body += quote(root / 'readonly-native-status') + ' ' + quote(environment_root) + ' 20\n'
    readonly_body += "Check ((Read-TraceState $r) -ceq 'ABSENT') 'real WPR status accepts separate arguments'\n$r|ConvertTo-Json -Depth 12\n"
    readonly = run('readonly-wpr-status', readonly_body)
    assert readonly['actual_exit_code'] == 0 and readonly['job_after_cleanup'][1] == 0
    assert not readonly['termination_requested']
    unrelated = subprocess.Popen(
        [sys._base_executable, '-S', '-c', 'import time;time.sleep(120)'],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        for name in ('args', 'exit7', 'linger', 'hang', 'missing'):
            marker = root / (name + '-child.json')
            arguments = ['-S', str(fixture), name, str(marker)]
            if name == 'args':
                arguments += ['한글 spaces', 'literal"quote', 'trailing\\', '']
            exe = root / 'missing.exe' if name == 'missing' else sys._base_executable
            body = 'Initialize-RunNative\n$r=Invoke-TraceNative ' + quote(exe)
            body += ' @(' + ','.join(map(quote, arguments)) + ') '
            body += quote(root / ('native-' + name)) + ' ' + quote(environment_root)
            body += (' 1' if name == 'hang' else ' 10') + '\n$r|ConvertTo-Json -Depth 20\n'
            result = run('native-' + name, body)
            assert unrelated.poll() is None
            if name in ('args', 'linger'):
                assert result['status'] == 'PASS' and result['actual_exit_code'] == 0
                assert result['job_after_cleanup'][1] == 0 and not result['termination_requested']
            else:
                assert result['status'] == 'FAIL'
            if name == 'args':
                assert json.loads(result['stdout']) == dict(args=arguments[4:], unexpected=None)
            if name == 'exit7':
                assert result['actual_exit_code'] == 7
            if name == 'hang':
                assert result['termination_requested'] and result['job_after_cleanup'][1] == 0
            if marker.exists():
                assert not psutil.pid_exists(json.loads(marker.read_bytes())['pid'])
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=10)
    facts = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
             for p in (source, helper, Path(__file__))}
    save(root / 'summary.json', dict(
        status='PASS', scope='SIMULATED_LIFECYCLE_AND_NATIVE_OWNED_COMMANDS_ONLY',
        simulated_lifecycle_cases=14, actual_etw_executed=False,
        command_argument_operations=4, unsafe_command_rejections=4,
        retained_exit_code_cases=6, redirected_log_finalization_cases=7, real_wpr_readonly_status_exit=0,
        receipts=receipts, sources=facts, release_gate='HOLD', promotion_allowed=False,
    ))
    print(json.dumps(dict(status='PASS', lifecycle_cases=14, process_suites=len(receipts), actual_etw_executed=False)))


if __name__ == '__main__':
    main()
