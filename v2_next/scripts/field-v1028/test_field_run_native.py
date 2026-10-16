"""Native PS5.1 job/handle/ACL tests; starts and kills only this test's own children."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


def quote(value):
    return "'"+str(value).replace("'", "''")+"'"


def save(path, value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.output.resolve();root.mkdir()
    source=Path(__file__).with_name('invoke-field-run.template.ps1').resolve()
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    native='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    env=os.environ.copy();env['PSModulePath']='C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    env['SFL_SHOULD_NOT_BE_INHERITED']='test marker only, not a secret'
    prefix="""Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(SOURCE,[ref]$t,[ref]$e)
if($e.Count){throw 'parse failure'}
foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
function Check([bool]$v,[string]$why){if(-not $v){throw $why}}
""".replace('SOURCE',quote(source))
    receipts=[]

    def run(name,body):
        script=root/(name+'.ps1');script.write_text(prefix+body,encoding='utf-8-sig')
        command=[native,'-NoProfile','-NonInteractive','-File',str(script)]
        result=subprocess.run(command,capture_output=True,env=env,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        (root/(name+'.stdout.log')).write_bytes(result.stdout)
        (root/(name+'.stderr.log')).write_bytes(result.stderr)
        record=dict(name=name,command=command,exit_code=result.returncode,stderr_bytes=len(result.stderr))
        save(root/(name+'.json'),record);receipts.append(record)
        assert result.returncode==0 and not result.stderr,(record,result.stdout.decode('utf-8','replace'),result.stderr.decode('utf-8','replace'))
        return result.stdout.decode('utf-8')

    run('acl',"""
Check ($PSVersionTable.PSEdition -ceq 'Desktop' -and [Environment]::Is64BitProcess) 'native PS5.1 x64'
$acl=New-RunAcl 'S-1-5-21-2762931165-1280404403-2847611662-1001'
Check ($acl.AreAccessRulesProtected -and $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'owner and inheritance'
$rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
Check ($rules.Count -eq 3) 'rule count'
$reader=@($rules|Where-Object{$_.IdentityReference.Value -ceq 'S-1-5-21-2762931165-1280404403-2847611662-1001'})
Check ($reader.Count -eq 1 -and $reader[0].FileSystemRights -eq ([Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize)) 'operator read only'
'ACL_DESCRIPTOR_ONLY_PASS'
""")
    fixture=root/'fixture.py'
    fixture.write_text('''import json, os, subprocess, sys, time
from pathlib import Path
mode, marker = sys.argv[1], Path(sys.argv[2])
if mode in ('hang','orphan','settling','deadline-drain'):
    child=subprocess.Popen([sys.executable,'-S',__file__,'short-child' if mode=='settling' else 'child',str(marker)],creationflags=subprocess.CREATE_NO_WINDOW)
    end=time.monotonic()+5
    while not marker.exists() and time.monotonic()<end:time.sleep(.01)
    if mode in ('orphan','settling','deadline-drain'):raise SystemExit(0)
    time.sleep(90)
elif mode in ('child','short-child'):
    marker.write_text(json.dumps({'pid':os.getpid()}))
    time.sleep(.3 if mode=='short-child' else 90)
elif mode=='args':
    print(json.dumps({'args':sys.argv[3:],'stdin':sys.stdin.buffer.read().hex(),
        'unexpected_environment':os.environ.get('SFL_SHOULD_NOT_BE_INHERITED')}))
elif mode=='exit7':raise SystemExit(7)
''',encoding='utf-8')
    names=('args','exit7','hang','orphan','settling','deadline-drain')
    unrelated=subprocess.Popen([sys._base_executable,'-S','-c','import time;time.sleep(90)'],creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for name in names:
            directory=root/name;directory.mkdir()
            marker=root/(name+'-child.json')
            arguments=['-S',str(fixture),name,str(marker)]
            if name=='args':arguments+=['spaces and 한글','literal"quote','trailing\\','']
            body='$r=Invoke-RunNative '+quote(sys._base_executable)+' @('+','.join(quote(x) for x in arguments)+') '+quote(directory)+' '+('1' if name in ('hang','deadline-drain') else '15')+'\n'
            body+="$r|ConvertTo-Json -Depth 8\nCheck ($r.created_suspended -and $r.job_assigned_before_resume -and $r.job_after_cleanup[1] -eq 0) 'owned suspended job'\n"
            if name in ('args','settling'):body+="Check ($r.status -ceq 'PASS' -and $r.actual_exit_code -eq 0 -and -not $r.termination_requested -and $r.job_drain.idle_confirmed) 'normal child and owned drain'\n"
            elif name=='exit7':body+="Check ($r.status -ceq 'FAIL' -and $r.actual_exit_code -eq 7 -and -not $r.termination_requested) 'actual exit7'\n"
            else:body+="Check ($r.status -ceq 'FAIL' -and $r.termination_requested) 'owned fault termination'\n"
            if name=='deadline-drain':body+="Check ($r.errors -contains 'outer-deadline' -and -not $r.job_drain.idle_confirmed) 'drain cannot extend overall deadline'\n"
            observation=json.loads(run(name,body))['job_observation_before_cleanup']
            assert observation['schema']=='sfl-owned-job-observation-v1',observation
            assert observation['sequence_not_atomic'] is True and observation['stopwatch_frequency']>0,observation
            assert observation['ended_ticks']>=observation['started_ticks'],observation
            root_observation=observation['root']
            assert root_observation['owned'] is True and root_observation['created_filetime']>0,observation
            assert Path(root_observation['executable']).resolve()==Path(sys._base_executable).resolve(),observation
            assert root_observation['signaled'] is (name!='hang'),observation
            assert root_observation['error'] is None,observation
            assert unrelated.pid not in [p['pid'] for p in observation['members']],observation
            if name in ('hang','orphan','deadline-drain'):
                child_pid=json.loads(marker.read_bytes())['pid']
                owned_child=[p for p in observation['members'] if p['pid']==child_pid]
                assert len(owned_child)==1 and owned_child[0]['owned'] is True and owned_child[0]['signaled'] is False,observation
                assert owned_child[0]['created_filetime']>0 and owned_child[0]['exit_code'] is None,observation
            if name=='args':
                value=json.loads((directory/'stdout.log').read_bytes())
                assert value==dict(args=arguments[4:],stdin='',unexpected_environment=None),value
            if marker.exists():assert not psutil.pid_exists(json.loads(marker.read_bytes())['pid'])
            assert unrelated.poll() is None
        # A failed diagnostic must not skip termination of the owned tree or
        # touch a process outside that tree. Inject failure at the call site.
        directory=root/'diagnostic-failure';directory.mkdir();marker=root/'diagnostic-failure-child.json'
        arguments=['-S',str(fixture),'hang',str(marker)]
        body="""
$definition=(Get-Command Invoke-RunNative).Definition.Replace('$child.ObserveJob()',"`$(throw 'synthetic-observation-failure')")
Set-Item Function:Invoke-RunNative ([scriptblock]::Create($definition))
"""
        body+='$r=Invoke-RunNative '+quote(sys._base_executable)+' @('+','.join(quote(x) for x in arguments)+') '+quote(directory)+' 1\n'
        body+="$r|ConvertTo-Json -Depth 8\nCheck ($r.status -ceq 'FAIL' -and $r.termination_requested -and $r.job_after_cleanup[1] -eq 0 -and $r.job_observation_error -ceq 'synthetic-observation-failure') 'diagnostic failure still cleans owned tree'\n"
        run('diagnostic-failure',body)
        assert marker.exists() and not psutil.pid_exists(json.loads(marker.read_bytes())['pid'])
        assert unrelated.poll() is None

        # Repeated quick exits retain the first accounting sample while requiring
        # positive, bounded whole-job idle confirmation before a PASS.
        directory=root/'quick-exits';directory.mkdir()
        body='$parent='+quote(directory)+'\n$records=@()\n'
        body+='for($i=0;$i -lt 30;$i++){\n$d=Join-Path $parent ([string]$i);[void][IO.Directory]::CreateDirectory($d)\n'
        body+='$r=Invoke-RunNative '+quote(sys.executable)+" @('-S','-c','pass') $d 15\n"
        body+="Check ($r.actual_exit_code -eq 0 -and $r.job_after_cleanup[1] -eq 0) 'quick root exited and job cleaned'\n"
        body+="Check ($r.status -ceq 'PASS' -and $r.job_drain.idle_confirmed -and -not $r.termination_requested -and $r.job_drain.observations[-1].accounting[1] -eq 0) 'bounded idle confirmation required'\n"
        body+="$records+=$r\n}\n$records|ConvertTo-Json -Depth 8\n"
        records=json.loads(run('quick-exits',body))
        assert len(records)==30
        for record in records:
            observation=record['job_observation_before_cleanup']
            assert observation['root']['signaled'] is True and observation['root']['exit_code']==0,observation
            assert observation['root']['error'] is None,observation
            assert all(p['signaled'] is None for p in observation['members'] if p['owned'] is not True),observation
        assert unrelated.poll() is None
        directory=root/'death';directory.mkdir();marker=root/'death-child.json'
        args=['-S',str(fixture),'hang',str(marker)]
        script=root/'death.ps1'
        script.write_text(prefix+'Invoke-RunNative '+quote(sys._base_executable)+' @('+','.join(quote(x) for x in args)+') '+quote(directory)+' 30 | ConvertTo-Json -Depth 8',encoding='utf-8-sig')
        with (root/'death.stdout.log').open('xb') as out,(root/'death.stderr.log').open('xb') as err:
            parent=subprocess.Popen([native,'-NoProfile','-NonInteractive','-File',str(script)],stdout=out,stderr=err,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+15
                while not marker.exists() and parent.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                assert marker.exists(),'native child not started'
                descendants=[p.pid for p in psutil.Process(parent.pid).children(recursive=True)]
                assert json.loads(marker.read_bytes())['pid'] in descendants
                parent.terminate();parent.wait(timeout=10)
                deadline=time.monotonic()+10
                while any(psutil.pid_exists(pid) for pid in descendants) and time.monotonic()<deadline:time.sleep(.05)
                assert not any(psutil.pid_exists(pid) for pid in descendants),descendants
                assert unrelated.poll() is None
                record=dict(name='supervisor-death',parent_exit=parent.returncode,descendants=descendants,all_gone=True,unrelated_alive=True)
                save(root/'death.json',record);receipts.append(record)
            finally:
                if parent.poll() is None:parent.terminate();parent.wait(timeout=10)
        directory=root/'no-exe';directory.mkdir()
        run('missing-executable',"$r=Invoke-RunNative "+quote(root/'missing.exe')+" @() "+quote(directory)+" 3\n$r|ConvertTo-Json -Depth 8\nCheck ($r.status -ceq 'FAIL' -and -not $r.job_assigned_before_resume) 'missing executable fails'\n")
        for mode in ('valid','changed','extra','traversal','not-frozen'):
            directory=root/('output-'+mode);session=directory/'session';session.mkdir(parents=True)
            value=dict(schema='sfl-field-run-result-v1',request_sha256='a'*64,
                       frozen=mode!='not-frozen',status='PASS',release_gate='HOLD',promotion_allowed=False,
                       classification='SYNTHETIC_OUTPUT_VERIFIER_FIXTURE')
            save(session/'result.json',value)
            (session/'payload.txt').write_bytes(b'preserve me')
            facts={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in session.iterdir()}
            if mode=='traversal':facts['../escape.txt']=facts['payload.txt']
            save(session/'manifest.json',dict(schema='sfl-field-run-files-v1',files=facts,release_gate='HOLD',promotion_allowed=False))
            if mode=='changed':(session/'payload.txt').write_bytes(b'changed bytes')
            if mode=='extra':(session/'extra.txt').write_bytes(b'not declared')
            call='Test-RunOutput '+quote(directory)+' '+quote('a'*64)+' $true'
            if mode=='valid':body='$r='+call+"\nCheck ($r.status -ceq 'PASS' -and $r.file_count -eq 2) 'valid output manifest'\n$r|ConvertTo-Json -Depth 8\n"
            else:
                reason={'changed':'result-member-fact','extra':'result-extra-file','traversal':'result-member-path','not-frozen':'runner-result-binding'}[mode]
                body='try { $null='+call+";throw 'invalid output accepted' } catch { Check ($_.Exception.Message -ceq "+quote(reason)+") 'expected output rejection'; $_.Exception.Message }\n"
            run('output-'+mode,body)
    finally:
        unrelated.terminate();unrelated.wait(timeout=10)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_sha
    summary=dict(status='PASS',cases=len(receipts),native_powershell='5.1 x64',source_sha256=source_sha,
                 production_acl_applied=False,production_acl_descriptor_verified=True,server_executed=False)
    save(root/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':main()
