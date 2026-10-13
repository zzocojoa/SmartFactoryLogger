"""Native PS5.1 tests; all writes stay in a new Desktop/SmartFactory fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--package', type=Path, required=True)
args = parser.parse_args()
ROOT = args.output.resolve()
PACKAGE = args.package.resolve()
SOURCE = Path(__file__).with_name('invoke-field-package-read.ps1').resolve()
NATIVE = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
assert ROOT.parent == Path('C:/Users/user/Desktop/SmartFactory') and ROOT.name.startswith('PDCA_FREAD128_')
assert ROOT.is_dir() and not (ROOT / 'probes').exists()
(ROOT / 'probes').mkdir()
(ROOT / 'fixtures').mkdir()
env = os.environ.copy()
for key in list(env):
    if key.lower() == 'psmodulepath':
        del env[key]
env['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, obj):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)


prefix = f"""
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source={quote(SOURCE)}
$package={quote(PACKAGE)}
$fixtures={quote(ROOT / 'fixtures')}
$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$t,[ref]$e)
if($e.Count -ne 0){{throw 'source parse failed'}}
$functions=@($ast.FindAll({{param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]}},$false))
foreach($f in $functions){{. ([scriptblock]::Create($f.Extent.Text))}}
$hash='56144abd5439b15bdd8dda8c00840d1561fdb5370bc0fdb065187eb5e176fb5e'
$manifest='58012882bd9ae382c741e2b5e2fc045c8fa9a7959fe273083db8b1113c43fd6b'
function Check([bool]$ok,[string]$why){{if(-not $ok){{throw $why}}}}
"""
cases = []


def run(name, body=None, argv=None, expected_exit=0, stdout_marker=None):
    if argv is None:
        probe = ROOT / 'probes' / (name + '.ps1')
        probe.write_text(prefix + body + '\n', encoding='utf-8')
        argv = [NATIVE, '-NoProfile', '-NonInteractive', '-File', str(probe)]
    proc = subprocess.run(argv, capture_output=True, env=env, timeout=150)
    for suffix, data in [('stdout.log', proc.stdout), ('stderr.log', proc.stderr)]:
        with (ROOT / f'{name}.{suffix}').open('xb') as stream:
            stream.write(data)
    result = {'case': name, 'argv': argv, 'actual_exit_code': proc.returncode,
              'expected_exit_code': expected_exit, 'stderr_bytes': len(proc.stderr),
              'stdout': proc.stdout.decode('utf-8-sig', errors='replace')}
    save(ROOT / f'{name}.json', result)
    cases.append(result)
    assert proc.returncode == expected_exit, result
    assert not proc.stderr, result
    if stdout_marker:
        assert stdout_marker in result['stdout'], result
    return result


source_before = sha(SOURCE)
package_before = sha(PACKAGE / 'verify-field-package.ps1')
run('native-parse-and-production-acl', r"""
Check ($PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and [Environment]::Is64BitProcess) 'Native PS5.1 required'
$code=Get-FieldReadChildCode $package $hash 10449 $manifest
$null=[Management.Automation.Language.Parser]::ParseInput($code,[ref]$t,[ref]$e)
Check ($e.Count -eq 0) 'child parser'
$acl=New-FieldReadAcl 'S-1-5-21-2762931165-1280404403-2847611662-1001'
Check ($acl.AreAccessRulesProtected -and $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'production ACL owner'
$rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
Check ($rules.Count -eq 3) 'three production ACL rules'
$reader=@($rules | Where-Object {$_.IdentityReference.Value -ceq 'S-1-5-21-2762931165-1280404403-2847611662-1001'})
$readOnlyMask=[Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize
Check ($reader.Count -eq 1 -and $reader[0].FileSystemRights -eq $readOnlyMask) 'operator read only'
'NATIVE_PARSE_AND_PRODUCTION_ACL_PASS'
""")
run('exact-child', r"""
$r=Invoke-FieldReadChild (Get-FieldReadChildCode $package $hash 10449 $manifest)
Check ($r.actual_exit_code -eq 0 -and -not $r.timed_out -and $r.stderr.Length -eq 0) 'exact child failed'
$parsed=$r.stdout|ConvertFrom-Json
Check ($parsed.result -ceq 'FIELD_PACKAGE_BYTES_AND_IDENTITIES_VERIFIED' -and $parsed.files_verified -eq 26) 'actual package result'
$r|ConvertTo-Json -Depth 5
""")
for name, hash_expr, size, manifest_expr, reason in [
    ('child-hash-mismatch', "('0'*64)", 10449, '$manifest', 'child-verifier-hash'),
    ('child-length-mismatch', '$hash', 10450, '$manifest', 'child-verifier-length'),
    ('manifest-mismatch', '$hash', 10449, "('0'*64)", 'external-manifest-hash'),
]:
    run(name, f"""
$r=Invoke-FieldReadChild (Get-FieldReadChildCode $package {hash_expr} {size} {manifest_expr})
Check ($r.actual_exit_code -eq 1 -and -not $r.timed_out -and $r.stdout.Contains('{reason}')) 'mismatch was not rejected'
$r|ConvertTo-Json -Depth 5
""")
run('missing-path', r"""
$r=Invoke-FieldReadChild (Get-FieldReadChildCode ($fixtures+'\missing') $hash 10449 $manifest)
Check ($r.actual_exit_code -eq 1 -and $r.stdout.Contains('child-missing-or-reparse')) 'missing path rejection'
$r|ConvertTo-Json -Depth 5
""")
run('locked-bytes-and-quote-path', r"""
$directory=$fixtures+"\quote'folder";[void][IO.Directory]::CreateDirectory($directory)
$path=$directory+'\verify-field-package.ps1'
$text=@'
param($PackageRoot,$ExpectedManifestSha256)
$writeDenied=$false;$deleteDenied=$false
try{$w=[IO.File]::Open(($PackageRoot+'\verify-field-package.ps1'),'Open','Write','ReadWrite');$w.Dispose()}catch{$writeDenied=($_.Exception.InnerException.HResult -band 65535)-eq 32}
try{[IO.File]::Delete($PackageRoot+'\verify-field-package.ps1')}catch{$deleteDenied=($_.Exception.InnerException.HResult -band 65535)-eq 32}
if(-not $writeDenied -or -not $deleteDenied){throw 'locked bytes were writable or deletable'}
[ordered]@{write_denied=$writeDenied;delete_denied=$deleteDenied}|ConvertTo-Json -Compress
exit 0
'@
[IO.File]::WriteAllText($path,$text,[Text.UTF8Encoding]::new($false))
$f=Get-Item -LiteralPath $path;$h=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
$r=Invoke-FieldReadChild (Get-FieldReadChildCode $directory $h $f.Length $manifest)
Check ($r.actual_exit_code -eq 0 -and $r.stdout.Contains('"write_denied":true') -and $r.stdout.Contains('"delete_denied":true')) 'same-stream locking or quote escaping failed'
Check ((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ceq $h) 'fixture changed'
$r|ConvertTo-Json -Depth 5
""")
run('invalid-utf8', r"""
$directory=$fixtures+'\invalid-utf8';[void][IO.Directory]::CreateDirectory($directory)
$path=$directory+'\verify-field-package.ps1';[IO.File]::WriteAllBytes($path,[byte[]]@(255,255,255))
$h=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
$r=Invoke-FieldReadChild (Get-FieldReadChildCode $directory $h 3 $manifest)
Check ($r.actual_exit_code -eq 1 -and $r.stdout.Contains('FIELD_PACKAGE_READ_CHILD_HOLD')) 'invalid UTF8 must not execute'
$r|ConvertTo-Json -Depth 5
""")
run('junction-rejected', r"""
$link=$fixtures+'\junction';$null=New-Item -ItemType Junction -Path $link -Target $package
$rejected=$false;try{$null=Get-FieldReadPlainPath $link}catch{$rejected=$_.Exception.Message -ceq 'reparse-path'}
Check $rejected 'parent junction rejection'
$r=Invoke-FieldReadChild (Get-FieldReadChildCode $link $hash 10449 $manifest)
Check ($r.actual_exit_code -eq 1 -and $r.stdout.Contains('child-missing-or-reparse')) 'child junction rejection'
$r|ConvertTo-Json -Depth 5
""")
run('timeout-owned-child-only', r"""
$r=Invoke-FieldReadChild 'Start-Sleep -Seconds 30' 500
Check ($r.timed_out -and $r.actual_exit_code -ne 0) 'timeout result'
Check ($null -eq (Get-Process -Id $r.pid -ErrorAction SilentlyContinue)) 'owned verifier still running'
$r|ConvertTo-Json -Depth 5
""")
run('result-path-and-new-file-guards', r"""
foreach($path in @('relative','C:\bad:stream',('C:\'+('x'*240)))){
  $rejected=$false;try{$null=Get-FieldReadPlainPath $path}catch{$rejected=$true};Check $rejected 'unsafe result path accepted'
}
$file=$fixtures+'\keep.txt';$first=Write-FieldReadNew $file 'first'
$rejected=$false;try{$null=Write-FieldReadNew $file 'second'}catch{$rejected=$true}
Check ($rejected -and [IO.File]::ReadAllText($file) -ceq 'first') 'existing result overwritten'
'RESULT_PATH_AND_NEW_FILE_GUARDS_PASS'
""")
result_parent = ROOT / 'fixtures' / 'result-parent'
result_parent.mkdir()
reader_sid = 'S-1-5-21-2762931165-1280404403-2847611662-1001'
run('production-nonadmin-no-write', argv=[NATIVE, '-NoProfile', '-NonInteractive', '-File', str(SOURCE),
    '-PackageRoot', str(PACKAGE), '-ResultParent', str(result_parent), '-OperatorSid', reader_sid],
    expected_exit=1, stdout_marker='administrator-required')
assert list(result_parent.iterdir()) == []

# The development account is not elevated. Only the owner SID and admin guard are
# adapted in this isolated fixture copy; production source and package stay pinned.
sid_probe = subprocess.run([NATIVE, '-NoProfile', '-Command', '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'], capture_output=True, env=env, check=True)
dev_sid = sid_probe.stdout.decode().strip()
text = SOURCE.read_text('utf-8')
admin_guard = "Assert-FieldReadCondition ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'administrator-required'"
assert text.count(admin_guard) == 1 and text.count('S-1-5-32-544') == 3
adapted = text.replace(admin_guard, "Assert-FieldReadCondition $true 'fixture-admin-substitution'").replace('S-1-5-32-544', dev_sid)
fixture_source = ROOT / 'fixtures/controller-current-user-fixture.ps1'
fixture_source.write_text(adapted, encoding='utf-8')
save(ROOT / 'fixture-substitutions.json', {'original_sha256': source_before, 'fixture_sha256': sha(fixture_source),
     'owner_sid_substituted': dev_sid, 'admin_guard_substitutions': 1,
     'production_admin_integration_tested': False})
for name in ('controller-result', 'controller-rerun-new-result'):
    run(name, argv=[NATIVE, '-NoProfile', '-NonInteractive', '-File', str(fixture_source),
        '-PackageRoot', str(PACKAGE), '-ResultParent', str(result_parent), '-OperatorSid', reader_sid],
        stdout_marker='FIELD_PACKAGE_READ_VERIFIED')
results = sorted(result_parent.iterdir())
assert len(results) == 2 and results[0].name != results[1].name
for result in results:
    manifest = json.loads((result / 'manifest.json').read_text('utf-8'))
    assert sorted(p.name for p in result.iterdir()) == ['manifest.json', 'result.json', 'verifier.stderr.txt', 'verifier.stdout.txt']
    for name, fact in manifest['files'].items():
        assert (result / name).stat().st_size == fact['bytes'] and sha(result / name) == fact['sha256']
    receipt = json.loads((result / 'result.json').read_text('utf-8'))
    assert receipt['child_exit_code'] == 0 and receipt['result'] == 'FIELD_PACKAGE_READ_VERIFIED'
    assert not receipt['installation_performed'] and not receipt['field_qa_executed'] and receipt['release_gate'] == 'HOLD'
assert sha(SOURCE) == source_before and sha(PACKAGE / 'verify-field-package.ps1') == package_before
save(ROOT / 'test-result.json', {'tests': cases, 'test_count': len(cases),
     'source_sha256': source_before, 'package_verifier_unchanged': True,
     'actual_result_manifests_verified': 2, 'production_admin_integration_tested': False,
     'field_qa_executed': False, 'release_gate': 'HOLD'})
print(json.dumps({'tests_passed': len(cases), 'actual_result_manifests_verified': 2,
                  'production_admin_integration_tested': False}))
