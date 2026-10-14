"""Build a hash-pinned local trace command for either PowerShell architecture."""
import ntpath
import re


def build_trace_command(package_root, manifest_sha256, suite_sha256):
    package = ntpath.normpath(str(package_root))
    if not re.match(r'^[A-Za-z]:\\', package) or any(ord(c) < 32 for c in package):
        raise ValueError('absolute local package path required')
    if any(not re.fullmatch(r'[0-9a-f]{64}', value)
           for value in (manifest_sha256, suite_sha256)):
        raise ValueError('lowercase SHA256 pins required')

    def quote(value):
        return "'" + value.replace("'", "''") + "'"

    suite = ntpath.join(package, 'invoke-trace-validation-suite.ps1')
    return (
        "& { if(-not [Environment]::Is64BitOperatingSystem){throw '64-bit Windows required'}; "
        "$traceSystem=if([Environment]::Is64BitProcess){'System32'}else{'Sysnative'}; "
        "$traceExe=[IO.Path]::Combine([Environment]::GetFolderPath('Windows'),$traceSystem,'WindowsPowerShell\\v1.0\\powershell.exe'); "
        "Write-Host ('TRACE_BOOTSTRAP_IS64='+[Environment]::Is64BitProcess); "
        "Write-Host ('TRACE_BOOTSTRAP_EXE='+$traceExe); "
        "$traceSuite=" + quote(suite) + "; "
        "$traceLock=[IO.File]::Open($traceSuite,'Open','Read','Read'); try { "
        "$traceHasher=[Security.Cryptography.SHA256]::Create(); try { "
        "$traceHash=[BitConverter]::ToString($traceHasher.ComputeHash($traceLock)).Replace('-','').ToLowerInvariant() "
        "} finally { $traceHasher.Dispose() }; "
        "if($traceHash -cne '" + suite_sha256 + "'){throw 'TRACE_SUITE_SHA256_MISMATCH'}; "
        "& $traceExe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $traceSuite "
        "-PackageRoot " + quote(package) + " -ExpectedManifestSha256 '" + manifest_sha256 + "'; "
        "Write-Host ('LAUNCH_EXIT='+$LASTEXITCODE) } finally { $traceLock.Dispose() } }"
    )
