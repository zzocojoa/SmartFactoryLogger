"""Native PS5.1 request-binding tests; no administrator token or ETW start."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output.resolve()
    root.mkdir()
    assert not ctypes.windll.shell32.IsUserAnAdmin(), 'unelevated test required'
    source = Path(__file__).parent
    names = ('invoke-field-run.template.ps1', 'invoke-trace-validation.ps1', 'invoke-request-trace-validation.ps1')
    prefix = """Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
foreach($source in @(SOURCES)){
 $tokens=$null;$errors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
 if($errors.Count){throw ($errors|Out-String)}
 foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
}
function Check([bool]$condition,[string]$reason){if(-not $condition){throw $reason}}
""".replace('SOURCES', ','.join(quote(source/name) for name in names))
    environment = os.environ.copy()
    environment['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    results = []

    def run(name, body, folder='System32', expected_exit=0):
        script = root/(name+'.ps1')
        script.write_text(prefix+body, encoding='utf-8-sig')
        result = subprocess.run([f'C:/Windows/{folder}/WindowsPowerShell/v1.0/powershell.exe',
                                 '-NoProfile', '-NonInteractive', '-File', str(script)],
                                env=environment, capture_output=True, timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (root/(name+'.stdout.log')).write_bytes(result.stdout)
        (root/(name+'.stderr.log')).write_bytes(result.stderr)
        assert result.returncode == expected_exit and not result.stderr, (name, result.returncode, result.stdout, result.stderr)
        value = json.loads(result.stdout)
        results.append(dict(name=name, exit_code=result.returncode, result=value))
        return value

    binding = run('input-binding', r"""
$fixture='C:\fixture'
$hash='a'*64
$armed=[pscustomobject]@{schema='sfl-request-trace-armed-v1';run_id=('b'*32);output_directory=$fixture;identity=@{pid=1234;process_created_filetime=134364938856872760};elevated=$false;wait_seconds=600;armed_at_utc=[DateTimeOffset]::UtcNow.AddSeconds(-1).ToString('o');source_files=[pscustomobject]@{'field_trace_request_fixture.py'=$hash;'field_http_sampling.py'=$hash;'field_native_timing.py'=$hash};release_gate='HOLD';promotion_allowed=$false}
$request=[pscustomobject]@{schema='sfl-request-trace-request-v1';run_id=$armed.run_id;fixture_directory=$fixture;armed_sha256=$hash;fixture_pid=1234;fixture_created_filetime='134364938856872760';fixture_sources=$armed.source_files;expires_utc=[DateTimeOffset]::UtcNow.AddSeconds(500).ToString('o');release_gate='HOLD';promotion_allowed=$false}
Assert-RequestTraceInput $request $armed $fixture $hash
$cases=@(
 @('schema','bad'),@('run_id',('c'*32)),@('fixture_directory','C:\other'),@('armed_sha256',('0'*64)),
 @('fixture_pid',1),@('fixture_pid',$true),@('fixture_created_filetime','1'),@('promotion_allowed',$true),
 @('expires_utc',[DateTimeOffset]::UtcNow.AddSeconds(-10).ToString('o')),
 @('expires_utc',[DateTimeOffset]::UtcNow.AddSeconds(1000).ToString('o')))
foreach($case in $cases){
 $changed=$request|ConvertTo-Json -Depth 10|ConvertFrom-Json;$changed.($case[0])=$case[1]
 $rejected=$false;try{Assert-RequestTraceInput $changed $armed $fixture $hash}catch{$rejected=$true}
 Check $rejected ('accepted invalid '+$case[0])
}
$changed=$request|ConvertTo-Json -Depth 10|ConvertFrom-Json
$changed.fixture_sources.'field_native_timing.py'='0'*64
$rejected=$false;try{Assert-RequestTraceInput $changed $armed $fixture $hash}catch{$rejected=$true};Check $rejected 'source pin'
@{status='PASS';accepted=1;rejected=11}|ConvertTo-Json
""")
    assert binding['rejected'] == 11
    data_path = root/'publication'
    data_path.mkdir()
    run('publication-completion', r"""
$fixture=FIXTURE
Write-RequestTraceBinding $fixture @{schema='binding-test';run_id='one'}
$original=Get-RunFact ($fixture+'\trace-binding.json')
Check (-not [IO.File]::Exists($fixture+'\trace-binding.json.writing')) 'temporary remained'
$rejected=$false;try{Write-RequestTraceBinding $fixture @{schema='binding-test';run_id='two'}}catch{$rejected=$true}
Check $rejected 'existing binding replaced'
Check ((Get-RunFact ($fixture+'\trace-binding.json')).sha256 -ceq $original.sha256) 'original binding changed'
Write-TraceJson ($fixture+'\workload.json') @{schema='fixture-test'}
$request=@{run_id='one';fixture_pid=1234;fixture_created_filetime='134364938856872760'}
$complete=[pscustomobject]@{schema='sfl-request-trace-fixture-complete-v1';run_id='one';status='WORKLOAD_COMPLETE_REQUIRES_TRACE_CORRELATION';identity=@{pid=1234;process_created_filetime=134364938856872760};workload=(Get-RunFact ($fixture+'\workload.json'));release_gate='HOLD';promotion_allowed=$false}
$result=Assert-RequestTraceCompletion $complete $request $fixture
Check ($result.bytes -gt 0) 'workload pin'
$complete.workload.sha256='0'*64
$rejected=$false;try{$null=Assert-RequestTraceCompletion $complete $request $fixture}catch{$rejected=$true};Check $rejected 'changed workload accepted'
@{status='PASS';original_binding_preserved=$true;workload_mismatch_rejected=$true}|ConvertTo-Json
""".replace('FIXTURE', quote(data_path)))
    json_path = root/'closed.json'
    run('closed-json-race', r"""
$path=JSONPATH
Add-Type -TypeDefinition @'
using System;using System.IO;using System.Text;using System.Threading;
public static class FixtureWriter {
 public static Thread Start(string path,int delay) {
  var stream=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None);
  var thread=new Thread(()=>{try{Thread.Sleep(delay);byte[] raw=Encoding.UTF8.GetBytes("{\"status\":\"final\"}");stream.Write(raw,0,raw.Length);stream.Flush(true);}finally{stream.Dispose();}});
  thread.Start();return thread;
 }
}
'@
$writer=[FixtureWriter]::Start($path,150)
$clock=[Diagnostics.Stopwatch]::StartNew()
$result=Read-RequestTraceClosedJson $path
Check ($writer.Join(1000) -and $result.status -ceq 'final' -and $clock.ElapsedMilliseconds -ge 100) 'read live writer'
$bad=$path+'.bad';[IO.File]::WriteAllText($bad,'{"broken"')
$rejected=$false;try{$null=Read-RequestTraceClosedJson $bad}catch{$rejected=$true};Check $rejected 'malformed json accepted'
$missing=$false;try{$null=Read-RequestTraceClosedJson ($path+'.missing')}catch{$missing=$true};Check $missing 'missing json accepted'
@{status='PASS';writer_closed=$true;malformed_rejected=$true;missing_rejected=$true}|ConvertTo-Json
""".replace('JSONPATH', quote(json_path)))
    for architecture in ('System32', 'SysWOW64'):
        body = '& ' + quote(source/'invoke-request-trace-validation.ps1') + " -PackageRoot 'unused' -ExpectedManifestSha256 '" + 'a'*64 + "' -JoinRequestPath 'unused' -ExpectedJoinRequestSha256 '" + 'b'*64 + "'\nexit $LASTEXITCODE\n"
        value = run('prerequisite-'+architecture, body, architecture, expected_exit=1)
        expected = 'administrator PowerShell required' if architecture == 'System32' else 'native PS5.1 x64 required'
        assert value['errors'] == [expected] and value['status'] == 'FAIL' and not value['promotion_allowed']
    summary = dict(status='PASS', cases=results, actual_etw_executed=False,
                   sources={name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names},
                   field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False)
    (root/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
