Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$expectedCommit = 'd7a1b20f96711fb07fc7add0867e79ee36506fce'
$installRoot = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
$configPath = 'C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
$runRoot = 'C:\ProgramData\SFLOps\runs\v1026-install-20260916-092927-baafcd33'
$expectedConfigHash =
    '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'
$expectedUninstallerHash =
    '610F5540AA0C6C24EF7DBEFFC1B5EE749D1B9C8CDCFC2B6EF643F8EA6F0DE837'
$expectedUninstallerLength = [int64]234261

$streams = [Collections.Generic.List[IDisposable]]::new()
$savedPath = $env:PATH
$savedModulePath = $env:PSModulePath

function Need {
    param([bool]$Ok, [string]$Code)

    if (-not $Ok) {
        throw ('V1026_POST_HOLD_READ:' + $Code)
    }
}

function Property {
    param([object]$Object, [string]$Name)

    Need ($null -ne $Object) ('missing-object-' + $Name)
    $item = $Object.PSObject.Properties[$Name]
    Need ($null -ne $item) ('missing-field-' + $Name)
    return $item.Value
}

function Assert-PlainExisting {
    param([string]$Path)

    $full = [IO.Path]::GetFullPath($Path)
    Need (
        [IO.File]::Exists($full) -or
        [IO.Directory]::Exists($full)
    ) ('missing-path-' + [IO.Path]::GetFileName($full))

    $node = [IO.FileInfo]::new($full)

    while ($null -ne $node) {
        Need (
            ($node.Attributes -band
                [IO.FileAttributes]::ReparsePoint) -eq 0
        ) 'reparse-path'

        if ($node -is [IO.FileInfo]) {
            $node = $node.Directory
        }
        else {
            $node = $node.Parent
        }
    }

    return $full
}

function Get-FileFact {
    param(
        [string]$Path,
        [string]$ExpectedHash = '',
        [int64]$ExpectedLength = -1,
        [switch]$Mutable
    )

    $full = Assert-PlainExisting $Path
    Need ([IO.File]::Exists($full)) 'expected-file'

    $share = if ($Mutable) {
        [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    }
    else {
        [IO.FileShare]::Read
    }

    $stream = [IO.File]::Open(
        $full,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $share
    )
    $streams.Add($stream)

    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $hash = [BitConverter]::ToString(
            $sha.ComputeHash($stream)
        ).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }

    if ($ExpectedLength -ge 0) {
        Need ($stream.Length -eq $ExpectedLength) 'file-length'
    }

    if (-not [string]::IsNullOrEmpty($ExpectedHash)) {
        Need ($hash -ceq $ExpectedHash) 'file-hash'
    }

    return [pscustomobject][ordered]@{
        path = $full
        length = [int64]$stream.Length
        sha256 = $hash
    }
}

function Read-JsonFile {
    param([string]$Path)

    $full = Assert-PlainExisting $Path
    $bytes = [IO.File]::ReadAllBytes($full)
    $text = [Text.UTF8Encoding]::new(
        $false,
        $true
    ).GetString($bytes)

    if (
        $text.Length -gt 0 -and
        [int][char]$text[0] -eq 0xFEFF
    ) {
        $text = $text.Substring(1)
    }

    return ConvertFrom-Json -InputObject $text
}

function Get-LocalJson {
    param([string]$Endpoint)

    Need (
        $Endpoint -cin @(
            'health',
            'api/spot/config',
            'stats'
        )
    ) 'endpoint'

    $request = [Net.HttpWebRequest]::Create(
        'http://127.0.0.1:8000/' + $Endpoint
    )
    $request.Method = 'GET'
    $request.Proxy = $null
    $request.AllowAutoRedirect = $false
    $request.Timeout = 10000
    $request.ReadWriteTimeout = 10000

    $response = $null
    $reader = $null

    try {
        $response = $request.GetResponse()
        Need ([int]$response.StatusCode -eq 200) 'local-http-status'

        $reader = [IO.StreamReader]::new(
            $response.GetResponseStream(),
            [Text.UTF8Encoding]::new($false, $true),
            $true
        )

        return ConvertFrom-Json -InputObject $reader.ReadToEnd()
    }
    finally {
        if ($null -ne $reader) {
            $reader.Dispose()
        }

        if ($null -ne $response) {
            $response.Dispose()
        }
    }
}

function Initialize-TokenReader {
    if ('SflPostHoldToken' -as [type]) {
        return
    }

    Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;

public static class SflPostHoldToken {
    const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
    const uint TOKEN_QUERY = 0x0008;
    const int TokenUser = 1;
    const int TokenSessionId = 12;
    const int TokenElevation = 20;

    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int pid);

    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);

    [DllImport("advapi32.dll", SetLastError=true)]
    static extern bool OpenProcessToken(
        IntPtr process,
        uint access,
        out IntPtr token
    );

    [DllImport("advapi32.dll", SetLastError=true)]
    static extern bool GetTokenInformation(
        IntPtr token,
        int kind,
        IntPtr buffer,
        int length,
        out int returned
    );

    static IntPtr OpenToken(int pid, out IntPtr process) {
        process = OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION,
            false,
            pid
        );

        if (process == IntPtr.Zero) {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        IntPtr token;
        if (!OpenProcessToken(process, TOKEN_QUERY, out token)) {
            CloseHandle(process);
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        return token;
    }

    static int IntValue(int pid, int kind) {
        IntPtr process = IntPtr.Zero;
        IntPtr token = IntPtr.Zero;
        IntPtr buffer = IntPtr.Zero;

        try {
            token = OpenToken(pid, out process);
            buffer = Marshal.AllocHGlobal(4);
            int returned;

            if (!GetTokenInformation(
                token,
                kind,
                buffer,
                4,
                out returned
            )) {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            return Marshal.ReadInt32(buffer);
        }
        finally {
            if (buffer != IntPtr.Zero) Marshal.FreeHGlobal(buffer);
            if (token != IntPtr.Zero) CloseHandle(token);
            if (process != IntPtr.Zero) CloseHandle(process);
        }
    }

    public static bool IsElevated(int pid) {
        return IntValue(pid, TokenElevation) != 0;
    }

    public static int SessionId(int pid) {
        return IntValue(pid, TokenSessionId);
    }

    public static string UserSid(int pid) {
        IntPtr process = IntPtr.Zero;
        IntPtr token = IntPtr.Zero;
        IntPtr buffer = IntPtr.Zero;

        try {
            token = OpenToken(pid, out process);
            int needed = 0;
            GetTokenInformation(
                token,
                TokenUser,
                IntPtr.Zero,
                0,
                out needed
            );

            if (needed <= 0 && Marshal.GetLastWin32Error() != 122) {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            buffer = Marshal.AllocHGlobal(needed);
            int returned;

            if (!GetTokenInformation(
                token,
                TokenUser,
                buffer,
                needed,
                out returned
            )) {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            return new SecurityIdentifier(
                Marshal.ReadIntPtr(buffer)
            ).Value;
        }
        finally {
            if (buffer != IntPtr.Zero) Marshal.FreeHGlobal(buffer);
            if (token != IntPtr.Zero) CloseHandle(token);
            if (process != IntPtr.Zero) CloseHandle(process);
        }
    }
}
'@
}

function Get-ProcessFact {
    param([Diagnostics.Process]$Process)

    $path = $null
    try {
        $path = $Process.Path
    }
    catch {
        $path = $null
    }

    return [pscustomobject][ordered]@{
        pid = [int]$Process.Id
        name = $Process.ProcessName
        path = $path
        started_at = $Process.StartTime.ToString('o')
        session_id = [SflPostHoldToken]::SessionId($Process.Id)
        user_sid = [SflPostHoldToken]::UserSid($Process.Id)
        elevated = [SflPostHoldToken]::IsElevated($Process.Id)
    }
}

try {
    $native = [IO.Path]::Combine(
        [Environment]::SystemDirectory,
        'WindowsPowerShell\v1.0\powershell.exe'
    )

    $current = (
        [Diagnostics.Process]::GetCurrentProcess()
    ).MainModule.FileName

    $principal = [Security.Principal.WindowsPrincipal]::new(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )

    Need (
        [Environment]::Is64BitProcess -and
        $PSVersionTable.PSEdition -ceq 'Desktop' -and
        $PSVersionTable.PSVersion.Major -eq 5 -and
        $PSVersionTable.PSVersion.Minor -eq 1 -and
        $current -ieq $native -and
        $principal.IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator
        )
    ) 'native-admin-ps51'

    $env:PATH = (
        [Environment]::SystemDirectory + ';' +
        [IO.Path]::GetDirectoryName($native)
    )
    $env:PSModulePath =
        [IO.Path]::GetDirectoryName($native) + '\Modules'

    Write-Host (
        '[READ ONLY] Inspecting the installer-elevated HOLD and current ' +
        'runtime. No retry, restart, rollback or observation.'
    ) -ForegroundColor Cyan

    Initialize-TokenReader

    $intentPath = $runRoot + '\intent.json'
    $holdPath = $runRoot + '\hold.json'
    $intentFact = Get-FileFact $intentPath
    $holdFact = Get-FileFact $holdPath
    $intent = Read-JsonFile $intentPath
    $hold = Read-JsonFile $holdPath

    Need (
        (Property $intent 'schema_version') -ceq
            'v1026-install-intent-v1' -and
        (Property $intent 'product_version') -ceq '1.0.26' -and
        (Property $intent 'product_commit') -ceq $expectedCommit -and
        [bool](Property $intent 'operator_token_accepted') -and
        -not [bool](Property $intent 'automatic_rollback_authorized') -and
        -not [bool](Property $intent 'canary_observation_authorized')
    ) 'intent-semantic'

    Need (
        (Property $hold 'schema_version') -ceq
            'v1026-install-hold-v1' -and
        (Property $hold 'result') -ceq 'HOLD' -and
        (Property $hold 'phase') -ceq 'interactive-installer' -and
        (Property $hold 'reason') -ceq 'installer-elevated' -and
        -not [bool](Property $hold 'automatic_rollback_performed') -and
        [bool](Property $hold 'partial_files_preserved')
    ) 'hold-semantic'

    $configFact = Get-FileFact `
        $configPath `
        $expectedConfigHash `
        2670 `
        -Mutable

    $uninstallerPath = $installRoot + '\Uninstall smart-factory.exe'
    $uninstallerFact = $null
    if ([IO.File]::Exists($uninstallerPath)) {
        $uninstallerFact = Get-FileFact `
            $uninstallerPath `
            $expectedUninstallerHash `
            $expectedUninstallerLength
    }

    $apps = @(
        Get-Process `
            -Name 'smart-factory' `
            -ErrorAction SilentlyContinue
    )
    $backends = @(
        Get-Process `
            -Name 'SmartFactoryBackend' `
            -ErrorAction SilentlyContinue
    )
    $listeners = @(
        Get-NetTCPConnection `
            -LocalPort 8000 `
            -State Listen `
            -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )

    $appFacts = @($apps | ForEach-Object { Get-ProcessFact $_ })
    $backendFacts = @(
        $backends | ForEach-Object { Get-ProcessFact $_ }
    )

    $setupFacts = @(
        Get-CimInstance Win32_Process |
            Where-Object {
                $null -ne $_.ExecutablePath -and
                $_.ExecutablePath -like (
                    'C:\Users\user\AppData\Local\SFLInstall\' +
                    'v1026-*\smart-factory-logger-v2 Setup 1.0.26.exe'
                )
            } |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    pid = [int]$_.ProcessId
                    path = $_.ExecutablePath
                    command_line_present =
                        -not [string]::IsNullOrWhiteSpace($_.CommandLine)
                }
            }
    )

    $health = $null
    $spot = $null
    $stats = $null
    $healthExact = $false

    if (
        $apps.Count -gt 0 -and
        $backends.Count -eq 1 -and
        $listeners.Count -eq 1 -and
        $listeners[0] -eq $backends[0].Id
    ) {
        $health = Get-LocalJson 'health'
        $spot = Get-LocalJson 'api/spot/config'
        $stats = Get-LocalJson 'stats'

        $healthExact = (
            (Property $health 'app_version') -ceq '1.0.26' -and
            (Property (
                Property $health 'spot_temperature'
            ) 'build_git_commit') -ceq $expectedCommit
        )
    }

    $allProductProcesses = @($appFacts + $backendFacts)
    $anyElevated = @(
        $allProductProcesses |
            Where-Object { $_.elevated }
    ).Count -gt 0

    $result = if (-not $healthExact) {
        'V1026_POST_HOLD_RUNTIME_NOT_BOUND'
    }
    elseif ($anyElevated) {
        'V1026_POST_HOLD_RUNTIME_ELEVATED_REVIEW_REQUIRED'
    }
    elseif ($setupFacts.Count -gt 0) {
        'V1026_POST_HOLD_INSTALLER_STILL_RUNNING'
    }
    else {
        'V1026_POST_HOLD_RUNTIME_IDENTITY_PRESENT_NON_ELEVATED'
    }

    [pscustomobject][ordered]@{
        schema_version = 'v1026-post-installer-elevated-hold-read-v1'
        result = $result
        checked_at = [DateTimeOffset]::Now.ToString('o')
        original_hold = [pscustomobject][ordered]@{
            run_root = $runRoot
            intent = $intentFact
            hold = $holdFact
            phase = Property $hold 'phase'
            reason = Property $hold 'reason'
            launch_root = Property $hold 'launch_root'
        }
        config = $configFact
        uninstaller = $uninstallerFact
        app_processes = $appFacts
        backend_processes = $backendFacts
        port_8000_owners = $listeners
        installer_processes = $setupFacts
        health_exact_v1026 = $healthExact
        health = $health
        spot_image = $(
            if ($null -eq $spot) {
                $null
            }
            else {
                Property $spot 'image'
            }
        )
        stats_errors = $(
            if ($null -eq $stats) {
                $null
            }
            else {
                Property $stats 'errors'
            }
        )
        any_product_process_elevated = $anyElevated
        installed_tree_fully_verified = $false
        image_liveness_sample_performed = $false
        source_file_writes_performed = $false
        product_changes_made = $false
        application_restart_performed = $false
        installation_retry_performed = $false
        automatic_rollback_performed = $false
        canary_observation_started = $false
        next_action =
            'RETURN_OUTPUT_FOR_POST_HOLD_RECONCILIATION'
        limitation = (
            'Point-in-time read only. This does not convert the original ' +
            'HOLD into PASS and does not yet verify the complete installed tree.'
        )
    } | ConvertTo-Json -Depth 10

    Write-Host (
        '[DONE] Return the complete output. Do not retry installation or ' +
        'restart/rollback the app.'
    ) -ForegroundColor Green
}
catch {
    Write-Host (
        '[HOLD] Read-only reconciliation stopped. Preserve current state ' +
        'and complete output; do not retry, restart or roll back.'
    ) -ForegroundColor Yellow

    throw
}
finally {
    foreach ($stream in $streams) {
        $stream.Dispose()
    }

    $env:PATH = $savedPath
    $env:PSModulePath = $savedModulePath
}
