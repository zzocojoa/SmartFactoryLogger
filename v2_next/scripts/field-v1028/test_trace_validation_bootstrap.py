"""Exercise x86/x64 launch and pin rejection without starting ETW."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess

from trace_validation_bootstrap import build_trace_command


def fact(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    root = parser.parse_args().output.resolve()
    root.mkdir()
    # Real-suite checks must stop at the administrator prerequisite.
    assert not ctypes.windll.shell32.IsUserAnAdmin(), 'run these checks unelevated'
    source = Path(__file__).with_name('invoke-trace-validation-suite.ps1')
    env = os.environ.copy()
    env['PSModulePath'] = 'C:/Windows/System32/WindowsPowerShell/v1.0/Modules'
    records = []

    def invoke(name, folder, script):
        command = root / (name + '.ps1')
        command.write_text(script, encoding='utf-8-sig')
        exe = f'C:/Windows/{folder}/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run(
            [exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(command)],
            env=env, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        (root / (name + '.stdout.log')).write_bytes(result.stdout)
        (root / (name + '.stderr.log')).write_bytes(result.stderr)
        records.append(dict(name=name, exit_code=result.returncode, stderr_bytes=len(result.stderr)))
        return result

    for folder in ('System32', 'SysWOW64'):
        package = root / (folder + " fixture with ' quote")
        package.mkdir()
        fixture = package / 'invoke-trace-validation-suite.ps1'
        fixture.write_text(r'''param([string]$PackageRoot,[string]$ExpectedManifestSha256)
$ErrorActionPreference='Stop'
$expected=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $expected){throw 'wrong native runtime'}
if($ExpectedManifestSha256 -cne ('a'*64) -or $PackageRoot -ine $PSScriptRoot){throw 'arguments changed'}
$blocked=$false
try{$s=[IO.File]::Open($PSCommandPath,'Open','Write','ReadWrite');$s.Dispose()}catch [IO.IOException]{$blocked=$true}
if(-not $blocked){throw 'suite bytes not held read-only during child execution'}
Write-Host 'NATIVE_AND_PINNED_FIXTURE_PASS'
exit 0
''', encoding='utf-8-sig')
        command = build_trace_command(package, 'a' * 64, fact(fixture)['sha256'])
        result = invoke(folder + '-fixture', folder, command)
        assert result.returncode == 0 and not result.stderr, (records[-1], result.stdout, result.stderr)
        assert b'NATIVE_AND_PINNED_FIXTURE_PASS' in result.stdout and b'LAUNCH_EXIT=0' in result.stdout
        expected_route = 'System32' if folder == 'System32' else 'Sysnative'
        assert f'\\{expected_route}\\WindowsPowerShell'.encode() in result.stdout
        tampered = build_trace_command(package, 'a' * 64, '0' * 64)
        result = invoke(folder + '-tampered', folder, "$ErrorActionPreference='Stop'\n" + tampered)
        assert result.returncode == 1 and b'TRACE_SUITE_SHA256_MISMATCH' in result.stderr
        assert b'NATIVE_AND_PINNED_FIXTURE_PASS' not in result.stdout and b'LAUNCH_EXIT=' not in result.stdout

        # Actual suite bytes, not a mocked prerequisite expression.
        command = build_trace_command(source.parent, 'a' * 64, fact(source)['sha256'])
        result = invoke(folder + '-real-suite-bootstrap', folder, command)
        assert result.returncode == 0 and not result.stderr, (records[-1], result.stdout, result.stderr)
        assert b'LAUNCH_EXIT=1' in result.stdout and b'administrator PowerShell required' in result.stdout
        start, end = result.stdout.index(b'{'), result.stdout.rindex(b'}') + 1
        parsed = json.loads(result.stdout[start:end])
        assert parsed['runtime']['is_64_bit_process'] and not parsed['scenarios']
        assert parsed['status'] == 'FAIL' and parsed['release_gate'] == 'HOLD' and not parsed['promotion_allowed']

        direct = "& '" + str(source).replace("'", "''") + "' -PackageRoot 'unused' -ExpectedManifestSha256 '" + 'a' * 64 + "'\nexit $LASTEXITCODE\n"
        result = invoke(folder + '-real-suite-direct', folder, direct)
        assert result.returncode == 1 and not result.stderr, (records[-1], result.stdout, result.stderr)
        parsed = json.loads(result.stdout)
        expected_error = 'administrator PowerShell required' if folder == 'System32' else 'native PS5.1 x64 required'
        assert parsed['errors'] == [expected_error] and not parsed['scenarios']
        assert parsed['runtime']['is_64_bit_process'] == (folder == 'System32')

    rejected = 0
    for package, manifest, suite in [
        ('relative', 'a' * 64, 'b' * 64),
        ('C:relative', 'a' * 64, 'b' * 64),
        ('//server/share', 'a' * 64, 'b' * 64),
        ('C:/bad\npath', 'a' * 64, 'b' * 64),
        ('C:/valid', 'A' * 64, 'b' * 64),
        ('C:/valid', 'a' * 63, 'b' * 64),
        ('C:/valid', 'a' * 64, 'b' * 63),
    ]:
        try:
            build_trace_command(package, manifest, suite)
        except ValueError:
            rejected += 1
    assert rejected == 7
    summary = dict(
        status='PASS', actual_etw_executed=False, native_invocations=len(records),
        input_rejections=rejected, receipts=records,
        sources={p.name: fact(p) for p in (source, Path(__file__), Path(__file__).with_name('trace_validation_bootstrap.py'))},
        release_gate='HOLD', promotion_allowed=False,
    )
    with (root / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
