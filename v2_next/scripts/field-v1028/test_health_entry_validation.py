"""Native PS5.1 bootstrap/archive/owned-job checks without ETW or app control."""
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
    names = ('invoke-field-run.template.ps1', 'invoke-trace-validation.ps1', 'invoke-health-diagnostic.ps1')
    prefix = '''Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
foreach($path in @(SOURCES)){
 $t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$t,[ref]$e)
 if($e.Count){throw ($e|Out-String)}
 foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
}
function Check([bool]$Value,[string]$Reason){if(-not $Value){throw $Reason}}
'''.replace('SOURCES', ','.join(quote(source/name) for name in names))
    env = os.environ.copy()
    env['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    results = []

    def run(name, body, arch='System32', expected=0):
        script = root/(name+'.ps1')
        script.write_text(prefix+body, encoding='utf-8-sig')
        command = [f'C:/Windows/{arch}/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-NonInteractive',
                   '-ExecutionPolicy', 'Bypass', '-File', str(script)]
        process = subprocess.run(command, env=env, capture_output=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        (root/(name+'.stdout.log')).write_bytes(process.stdout)
        (root/(name+'.stderr.log')).write_bytes(process.stderr)
        (root/(name+'.terminal.json')).write_text(json.dumps(dict(command=command, exit_code=process.returncode)))
        assert process.returncode == expected and not process.stderr, (name, process.returncode, process.stdout, process.stderr)
        value = json.loads(process.stdout)
        results.append(dict(name=name, actual_exit=process.returncode, result=value))
        return value

    run('package-contract', r'''
$files=[ordered]@{}
foreach($name in @('health_diagnostic_runner.exe','invoke-health-diagnostic.ps1','candidate-payload.json','helper-source.zip','helper-build.json','trace/manifest.json','trace/invoke-field-run.template.ps1','trace/invoke-trace-validation.ps1','trace/invoke-health-trace.ps1','trace/SFLThreadScheduling.wprp')){$files[$name]=@{bytes=10;sha256=('a'*64)}}
$files['candidate-payload.json'].sha256='658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69'
$document=[pscustomobject]@{schema='sfl-health-diagnostic-package-v1';candidate_commit='acaf77d95101a050f4d3ecd76125d3502036f5a7';signature_policy='UNSIGNED_INTERNAL';files=[pscustomobject]$files;release_gate='HOLD';promotion_allowed=$false}
Assert-HealthEntryPackage $document
$next=$document|ConvertTo-Json -Depth 5|ConvertFrom-Json
$next.candidate_commit='0732c8e810be3c46096b397812f53a9767354229'
$next.files.'candidate-payload.json'.sha256='4e3e95be87d8ea51a509ba62c8eb29236eefe402f5f353bb78c9a342d7825a97'
Assert-HealthEntryPackage $next
foreach($pair in @(@($document,$next),@($next,$document))){
 $mixed=$pair[0]|ConvertTo-Json -Depth 5|ConvertFrom-Json
 $mixed.files.'candidate-payload.json'.sha256=$pair[1].files.'candidate-payload.json'.sha256
 $rejected=$false;try{Assert-HealthEntryPackage $mixed}catch{$rejected=$true};Check $rejected 'cross-candidate payload accepted'
}
foreach($commit in @($next.candidate_commit.ToUpperInvariant(),('f'*40))){
 $mixed=$next|ConvertTo-Json -Depth 5|ConvertFrom-Json;$mixed.candidate_commit=$commit
 $rejected=$false;try{Assert-HealthEntryPackage $mixed}catch{$rejected=$true};Check $rejected 'nonexact candidate accepted'
}
$bad=@(@('schema','old'),@('candidate_commit','4cc7393e1bafbf90a329726aed9470fe0daacb21'),@('signature_policy','SIGNED'),@('release_gate','PASS'),@('promotion_allowed',0))
foreach($row in $bad){$changed=$document|ConvertTo-Json -Depth 5|ConvertFrom-Json;$changed.($row[0])=$row[1];$rejected=$false;try{Assert-HealthEntryPackage $changed}catch{$rejected=$true};Check $rejected ('package:'+ $row[0])}
$changed=$document|ConvertTo-Json -Depth 5|ConvertFrom-Json;$changed.files.'candidate-payload.json'.sha256='b'*64
$rejected=$false;try{Assert-HealthEntryPackage $changed}catch{$rejected=$true};Check $rejected 'wrong payload pin'
$changed=$document|ConvertTo-Json -Depth 5|ConvertFrom-Json;$changed.files.'health_diagnostic_runner.exe'.bytes=-1
$rejected=$false;try{Assert-HealthEntryPackage $changed}catch{$rejected=$true};Check $rejected 'negative bytes'
$changed=$document|ConvertTo-Json -Depth 5|ConvertFrom-Json;$changed.files|Add-Member extra @{bytes=1;sha256=('a'*64)}
$rejected=$false;try{Assert-HealthEntryPackage $changed}catch{$rejected=$true};Check $rejected 'extra package member'
@{status='PASS';accepted=2;rejected=12}|ConvertTo-Json
''')
    run('request-budgets', r'''
$short=Get-HealthEntryBudget @{schema='sfl-health-diagnostic-request-v1';duration_seconds=6}
$long=Get-HealthEntryBudget @{schema='sfl-health-outlier-request-v1';duration_seconds=900}
$cpu=Get-HealthEntryBudget @{schema='sfl-health-cpu-outlier-request-v1';duration_seconds=900}
Check ($cpu.seconds -eq 1500 -and $cpu.scope -ceq 'CPU_OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE') 'cpu request budget'
Check ($short.seconds -eq 600 -and $long.seconds -eq 1500 -and $long.scope -ceq 'OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE') 'request budgets'
foreach($case in @(@('sfl-health-diagnostic-request-v1',900),@('sfl-health-outlier-request-v1',6),@('sfl-health-outlier-request-v1',901),@('sfl-health-outlier-request-v1',$true),@('sfl-health-cpu-outlier-request-v1',6),@('sfl-health-cpu-outlier-request-v1',901),@('sfl-health-cpu-outlier-request-v1',$true),@('other',900))){
 $rejected=$false;try{[void](Get-HealthEntryBudget @{schema=$case[0];duration_seconds=$case[1]})}catch{$rejected=$true};Check $rejected 'mixed request accepted'
}
@{status='PASS';short_seconds=$short.seconds;long_seconds=$long.seconds;cpu_seconds=$cpu.seconds;rejected=8}|ConvertTo-Json
''')
    archive = root/'archive'
    archive.mkdir()
    run('archive-and-path', r'''
$folder=FOLDER
$source=$folder+'\source.json';[IO.File]::WriteAllText($source,'{"fixture":"unchanged"}')
$stream=[IO.File]::Open($source,'Open','Read','Read')
try{
 $pin=Get-HealthEntryHash $stream;Copy-HealthEntryStream $stream ($folder+'\copy.json')
 $blocked=$false;try{[IO.File]::WriteAllText($source,'changed')}catch{$blocked=$true};Check $blocked 'source not locked'
 $blocked=$false;try{Copy-HealthEntryStream $stream ($folder+'\copy.json')}catch{$blocked=$true};Check $blocked 'overwrote archive'
 $facts=Get-HealthEntryFiles $folder;Check ($facts.Count -eq 2 -and $facts['copy.json'].sha256 -ceq $pin) 'archive facts'
}finally{$stream.Dispose()}
foreach($bad in @('relative.json','\\server\share\file.json',($source+':ads'),('C:\'+('a'*235)),("C:\bad"+[char]10+'name'))){
 $blocked=$false;try{[void](Get-HealthEntryPath $bad)}catch{$blocked=$true};Check $blocked 'unsafe path accepted'
}
@{status='PASS';same_bytes=$true;overwrite_rejected=$true;locked_source=$true;path_rejections=5}|ConvertTo-Json
'''.replace('FOLDER', quote(archive)))
    for scenario in ('normal', 'callback-failure'):
        directory = root/scenario
        directory.mkdir()
        value = run('owned-'+scenario, r'''
$entryState=@{ticks=0;record=@{callback_seen=$false}}
$callback={param($owned) $entryState.ticks++;$entryState.record.callback_seen=$true;Check ($owned.Pid -gt 0) 'missing owned child';FAILURE}
$native='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$result=Invoke-HealthEntryChild $native @('-NoProfile','-NonInteractive','-Command','[Threading.Thread]::Sleep(750); exit 0') DIRECTORY $callback
Check ($entryState.ticks -gt 0 -and $entryState.record.callback_seen) 'callback state shadowed'
Check ($result.job_after_cleanup[1] -eq 0 -and $result.created_suspended -and $result.job_assigned_before_resume) 'owned-job cleanup'
$result|ConvertTo-Json -Depth 10
'''.replace('DIRECTORY', quote(directory)).replace('FAILURE',
            "throw 'injected-callback-failure'" if scenario == 'callback-failure' else ''))
        assert value['status'] == ('PASS' if scenario == 'normal' else 'FAIL')
        assert value['termination_requested'] == (scenario != 'normal')
        assert value['actual_exit_code'] == (0 if scenario == 'normal' else 1)
        if scenario != 'normal':
            assert value['errors'] == ['injected-callback-failure']
    deadline_folder = root/'deadline'
    deadline_folder.mkdir()
    value = run('owned-deadline', r'''
$result=Invoke-HealthEntryChild 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' @('-NoProfile','-NonInteractive','-Command','[Threading.Thread]::Sleep(5000)') DIRECTORY {} 1
Check ($result.status -ceq 'FAIL' -and $result.termination_requested -and $result.job_after_cleanup[1] -eq 0 -and $result.errors -contains 'health-outer-deadline') 'bounded owned deadline'
$result|ConvertTo-Json -Depth 10
'''.replace('DIRECTORY', quote(deadline_folder)))
    for arch in ('System32', 'SysWOW64'):
        body = '& '+quote(source/'invoke-health-diagnostic.ps1')+" -PackageRoot 'unused' -ExpectedManifestSha256 '"+'a'*64
        body += "' -RequestPath 'unused' -ExpectedRequestSha256 '"+'b'*64+"' -OperatorSid 'S-1-5-21-1-2-3-1001'\nexit $LASTEXITCODE\n"
        value = run('prerequisite-'+arch, body, arch, expected=1)
        reason = 'administrator-required' if arch == 'System32' else 'native-powershell-5.1-x64-required'
        assert value['status'] == 'FAIL' and value['errors'] == [reason]
    result = dict(status='PASS', cases=results, actual_etw_started=False, application_controlled=False,
        sources={name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names},
        release_gate='HOLD', promotion_allowed=False)
    (root/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
