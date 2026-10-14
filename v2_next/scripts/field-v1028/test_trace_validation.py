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
        receipts=receipts, sources=facts, release_gate='HOLD', promotion_allowed=False,
    ))
    print(json.dumps(dict(status='PASS', lifecycle_cases=14, process_suites=len(receipts), actual_etw_executed=False)))


if __name__ == '__main__':
    main()
