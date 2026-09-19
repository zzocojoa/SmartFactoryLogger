param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'read-minimal-backup-preflight-v1025.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw ($errors | Out-String) }
$checks = [Collections.Generic.List[string]]::new()
function Check { param([bool]$OK,[string]$Name) if (-not $OK) { throw ('TEST FAILED: ' + $Name) }; $checks.Add($Name) }
function Reject { param([scriptblock]$Code,[string]$Name) $failed=$false;try{& $Code|Out-Null}catch{$failed=$true};Check $failed $Name }
$functions = @($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]}, $true))
foreach ($function in $functions) { . ([scriptblock]::Create($function.Extent.Text)) }
$text = [IO.File]::ReadAllText($source)
Check ($functions.Count -eq 14) 'parse and import functions only'
Check ($text -notmatch 'CreateDirectory|WriteAllText|WriteAllBytes|Set-Content|Out-File|Copy-Item|Move-Item|Remove-Item|Start-Process|Stop-Process|taskkill|Invoke-Expression|Import-Module') 'server helper has no filesystem/process mutation'
Check ($text.Contains('$request.Method = ''GET''') -and $text.Contains('$request.Proxy = $null') -and
    $text.Contains('$request.AllowAutoRedirect = $false')) 'loopback request is GET without proxy or redirect'
Check ($text.Contains("'http://127.0.0.1:8000/health'")) 'only fixed health endpoint exists'
foreach ($forbidden in @('/api/spot/live_image.jpg','/api/config','/stats','http://outside.invalid')) {
    Check (-not $text.Contains($forbidden)) ('forbidden endpoint absent: ' + $forbidden)
}
foreach ($flag in @('backup_created = $false','restore_rehearsal_performed = $false','application_stop_performed = $false',
    'application_restart_performed = $false','installation_started = $false','product_changes_made = $false',
    'production_promotion_allowed = $false')) {
    Check ($text.Contains($flag)) ('no premature action: ' + $flag)
}
Check ($text.Contains('$opsRoot = ''C:\ProgramData\SFLOps''')) 'new SFLOps policy root pinned'
Check (-not $text.Contains('C:\ProgramData\SFL26B-')) 'legacy backup root not reused'
Check ($text.Contains('Minimal backup cannot recover accumulated CSV/image/fact data')) 'excluded business-data risk explicit'
Check ($text.Contains('$roamingRoot = ''C:\Users\user\AppData\Roaming''') -and
    $text.Contains('Need ((FullLocalPath $env:APPDATA) -ieq $roamingRoot)')) 'APPDATA compared with roaming root, not product subfolder'
Check (-not $text.Contains('Need ((FullLocalPath $env:APPDATA) -ieq $appDataRoot)')) 'regression: APPDATA is not product subfolder'

Check ((FullLocalPath 'C:/scope/child') -ceq 'C:\scope\child') 'local path normalization'
foreach ($bad in @('C:\','relative','\\server\share','C:\scope\..\escape','C:\scope\x:ads','C:\scope\CON','C:\scope\x*')) {
    Reject { FullLocalPath $bad } ('unsafe path rejected: ' + $bad)
}
Check (IsWithin 'C:\scope\child' 'c:\SCOPE') 'case-insensitive child'
Check (-not (IsWithin 'C:\scope2\child' 'C:\scope')) 'prefix sibling rejected'
Reject { DecodeJsonObject '[]' } 'array JSON root rejected'
Reject { DecodeJsonObject 'null' } 'null JSON root rejected'
Check ((Required (DecodeJsonObject '{"value":"ok"}') 'value') -ceq 'ok') 'required scalar field'
Reject { Required (DecodeJsonObject '{"value":["ok"]}') 'value' } 'array field rejected'

if ([IO.File]::Exists($OutputRoot) -or [IO.Directory]::Exists($OutputRoot)) { throw 'Existing test output is preserved.' }
$fixture = [IO.Path]::GetFullPath($OutputRoot)
[void][IO.Directory]::CreateDirectory($fixture)
$roamingRoot = Join-Path $fixture 'Roaming'
$appDataRoot = Join-Path $roamingRoot 'AppData'
$electronRoot = Join-Path $roamingRoot 'Electron'
$installRoot = Join-Path $fixture 'Install'
$opsRoot = Join-Path $fixture 'SFLOps'
foreach ($directory in @($appDataRoot,$electronRoot,(Join-Path $appDataRoot 'layouts'))) {
    [void][IO.Directory]::CreateDirectory($directory)
}
[IO.File]::WriteAllText((Join-Path $appDataRoot 'config.ini'), 'fixture config', [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $appDataRoot 'operator_metadata.json'), '{}', [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $appDataRoot 'layouts\a.json'), '{}', [Text.UTF8Encoding]::new($false))
[void][IO.Directory]::CreateDirectory((Join-Path $electronRoot 'Local Storage\leveldb'))
[IO.File]::WriteAllText((Join-Path $electronRoot 'Local State'), '{}', [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $electronRoot 'Local Storage\leveldb\000001.log'), 'fixture', [Text.UTF8Encoding]::new($false))
$file = GetFixedFileMetadata 'operator_metadata' (Join-Path $appDataRoot 'operator_metadata.json') $true
Check ($file.exists -and $file.bytes -eq 2) 'fixed state file metadata'
$missing = GetFixedFileMetadata 'optional' (Join-Path $appDataRoot 'missing.json') $false
Check (-not $missing.exists -and $null -eq $missing.bytes) 'missing optional state explicit'
Reject { GetFixedFileMetadata 'outside' (Join-Path $fixture 'outside.json') $false } 'state path boundary'
$layouts = GetTreeSummary 'layouts' (Join-Path $appDataRoot 'layouts') $true
$electron = GetTreeSummary 'electron_profile' $electronRoot $true
Check ($layouts.files -eq 1 -and $layouts.bytes -eq 2 -and $layouts.enumeration_complete) 'layout tree summary'
Check ($electron.files -eq 2 -and $electron.directories -eq 2 -and $electron.enumeration_complete) 'electron tree summary'
Reject { GetTreeSummary 'bad' (Join-Path $fixture 'outside') $false } 'unapproved tree root rejected'
Reject { GetTreeSummary 'electron_profile' $electronRoot $true 0 60 } 'entry budget validated'
$sha = [Security.Cryptography.SHA256]::Create()
try { $expectedHash = [BitConverter]::ToString($sha.ComputeHash(
    [Text.UTF8Encoding]::new($false).GetBytes('fixture config'))).Replace('-', '') }
finally { $sha.Dispose() }
Check ((GetPinnedConfigHash (Join-Path $appDataRoot 'config.ini') $expectedHash).matches_pin) 'bounded config hash'
Reject { GetPinnedConfigHash (Join-Path $appDataRoot 'config.ini') ('0' * 64) } 'wrong config hash rejected'
AssertSameRuntime ([pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=4}) `
    ([pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=4})
Check $true 'same runtime accepted'
Reject { AssertSameRuntime ([pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=4}) `
    ([pscustomobject]@{main_pid=1;main_start_utc_ticks=2;backend_pid=3;backend_start_utc_ticks=5}) } 'runtime replacement rejected'

$result = [pscustomobject]@{
    result = 'V1025_MINIMAL_BACKUP_PREFLIGHT_LOCAL_TEST_PASS'
    assertions = $checks.Count
    powershell_version = $PSVersionTable.PSVersion.ToString()
    server_main_executed = $false
    network_queries_performed = $false
    product_changes_made = $false
    checks = $checks.ToArray()
}
$json = $result | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $fixture 'validation-result.json'), $json, [Text.UTF8Encoding]::new($false))
$json
