[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Use native x64 PS5.1.'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=[IO.Path]::GetFullPath($OutputRoot)
if(-not $output.StartsWith($repo+'\artifacts\',[StringComparison]::OrdinalIgnoreCase) -or [IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'New artifacts child required; never overwrite a delivery.'}
$source=Join-Path $PSScriptRoot 'repair-root-inbox-acl.ps1'
$tests=Join-Path $PSScriptRoot 'test-root-inbox-acl.ps1'
$text=[IO.File]::ReadAllText($source)
if($text -match '[^\x00-\x7F]'){throw 'Helper must remain ASCII-compatible UTF-8.'}
[void][IO.Directory]::CreateDirectory($output)
$helper=$output+'\repair-sflops-root-inbox-r1.ps1'
[IO.File]::Copy($source,$helper,$false)
$hash=(Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash
$length=(Get-Item -LiteralPath $helper).Length
$launch=@'
& {
    $ErrorActionPreference = 'Stop'
    $path = 'C:\Users\user\Desktop\SmartFactory\repair-sflops-root-inbox-r1.ps1'
    $expected = '__HASH__'
    $length = __LENGTH__
    $stream = [IO.File]::Open($path, 'Open', 'Read', 'Read')
    $sha = [Security.Cryptography.SHA256]::Create()
    $reader = $null
    try {
        $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
        if ($stream.Length -ne $length -or $actual -cne $expected) {
            throw 'Helper length/SHA256 mismatch. Do not execute.'
        }
        $stream.Position = 0
        $reader = [IO.StreamReader]::new($stream, [Text.UTF8Encoding]::new($false, $true))
        & ([scriptblock]::Create($reader.ReadToEnd())) -Execute
    }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        $sha.Dispose()
        $stream.Dispose()
    }
}
'@
$launch=$launch.Replace('__HASH__',$hash).Replace('__LENGTH__',[string]$length)
$launchPath=$output+'\RUN_ON_SERVER.txt'
[IO.File]::WriteAllText($launchPath,$launch,[Text.UTF8Encoding]::new($false))
$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
& $native -NoLogo -NoProfile -ExecutionPolicy Bypass -File $tests -Helper $helper -OutputRoot ($output+'\local-tests') -Launcher $launchPath
if($LASTEXITCODE -ne 0){throw 'Tests failed; preserve this directory and do not distribute it.'}
if((Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash -cne $hash){throw 'Helper changed during tests.'}
$validationPath=$output+'\local-tests\validation.json'
$validation=Get-Content -LiteralPath $validationPath -Raw|ConvertFrom-Json
if($validation.result -cne 'ROOT_INBOX_ACL_LOCAL_TEST_PASS' -or $validation.helper_sha256 -cne $hash){throw 'Validation binding mismatch.'}
[IO.File]::WriteAllText(($helper+'.sha256.txt'),($hash+"`n"),[Text.Encoding]::ASCII)
[IO.File]::Copy((Join-Path $PSScriptRoot 'ROOT_INBOX_ACL_GUIDE.md'),($output+'\GUIDE.md'),$false)
$result=[ordered]@{result='ROOT_INBOX_ACL_DELIVERY_READY_NOT_SERVER_EXECUTED';helper_path=$helper;helper_length=$length;helper_sha256=$hash;assertions=$validation.assertions;launcher_sha256=(Get-FileHash -LiteralPath $launchPath -Algorithm SHA256).Hash;tests_sha256=(Get-FileHash -LiteralPath $tests -Algorithm SHA256).Hash;validation_sha256=(Get-FileHash -LiteralPath $validationPath -Algorithm SHA256).Hash;server_executed=$false;product_modified=$false;database_migration=$false}
[IO.File]::WriteAllText(($output+'\build-result.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 5
