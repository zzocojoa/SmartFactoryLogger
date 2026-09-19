[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Build under native x64 Windows PowerShell 5.1.'}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=[IO.Path]::GetFullPath($OutputRoot)
if([IO.File]::Exists($output)-or[IO.Directory]::Exists($output)){throw 'Output exists; preserve it and choose a new run.'}
$legacy=Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup.ps1'
if((Get-FileHash -LiteralPath $legacy -Algorithm SHA256).Hash -cne '7943B476C75BF5FC1B8F1CB9D83C6018E787F4ACCEA17D42BF0C6C670FF42C53'){throw 'Reviewed source pin differs.'}
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($legacy,[ref]$tokens,[ref]$errors)
if($errors.Count-ne0){throw 'Reviewed utility source parse failure.'}
$names=@('Plain','HashStream','FileFact','MutableFileFact','ReadJson','Property','Bool','Counter','PrivateAcl','AssertPrivateAcl','WriteJsonNew','InitializeTokenInspector')
$pieces=[Collections.Generic.List[string]]::new()
$pieces.Add('# Generated read-only product check. New SFLOps report files only.')
foreach($name in $names){
    $functions=@($ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$true))
    if($functions.Count-ne1){throw ('Utility not unique: '+$name)}
    $pieces.Add($functions[0].Extent.Text)
}
$body=Join-Path $PSScriptRoot 'installed-read-v1026.body.ps1'
$pieces.Add([IO.File]::ReadAllText($body))
[void][IO.Directory]::CreateDirectory($output)
$helper=Join-Path $output 'read-installed-v1026.ps1'
[IO.File]::WriteAllText($helper,([string]::Join("`r`n`r`n",$pieces.ToArray())),[Text.UTF8Encoding]::new($false))
$null=[Management.Automation.Language.Parser]::ParseFile($helper,[ref]$tokens,[ref]$errors)
if($errors.Count-ne0){throw ($errors|Out-String)}
$helperHash=(Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash
$launcher=@'
& {
    $ErrorActionPreference = 'Stop'
    $path = 'C:\Users\user\Desktop\SmartFactory\read-installed-v1026.ps1'
    $expected = '__HASH__'
    $stream = [IO.File]::Open($path, 'Open', 'Read', 'Read')
    $sha = [Security.Cryptography.SHA256]::Create()
    $reader = $null
    try {
        $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
        if ($actual -cne $expected) { throw 'Helper SHA256 mismatch. Do not execute.' }
        $stream.Position = 0
        $reader = [IO.StreamReader]::new($stream, [Text.UTF8Encoding]::new($false, $true))
        & ([scriptblock]::Create($reader.ReadToEnd()))
    }
    finally {
        if ($null -ne $reader) { $reader.Dispose() }
        $sha.Dispose()
        $stream.Dispose()
    }
}
'@
$launcher=$launcher.Replace('__HASH__',$helperHash)
[IO.File]::WriteAllText((Join-Path $output 'RUN_ON_SERVER.txt'),$launcher,[Text.UTF8Encoding]::new($false))
$release=Join-Path $repo 'artifacts\v1026-release-prep-d7a1b20-20260911\installer-candidate-review-only'
& $native -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'test-installed-read-v1026.ps1') -Helper $helper -OutputRoot (Join-Path $output 'local-tests') -ReleaseRoot $release -ExtractedAppRoot (Join-Path $repo '.tmp\v1026x1\app') -UninstallerPath (Join-Path $repo '.tmp\v1026x1\nsis\$R0\Uninstall smart-factory.exe') -Launcher (Join-Path $output 'RUN_ON_SERVER.txt')
if($LASTEXITCODE-ne0){throw 'Local tests failed; artifact is not ready for server use.'}
if((Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash-cne$helperHash){throw 'Helper changed during tests.'}
$validation=Get-Content -LiteralPath (Join-Path $output 'local-tests\validation-result.json') -Raw|ConvertFrom-Json
if($validation.result-cne'V1026_INSTALLED_READ_LOCAL_TEST_PASS'-or$validation.helper_sha256-cne$helperHash){throw 'Validation binding failure.'}
[IO.File]::WriteAllText($helper+'.sha256.txt',$helperHash+"`n",[Text.Encoding]::ASCII)
[IO.File]::Copy((Join-Path $PSScriptRoot 'INSTALLED_READ_V1026_GUIDE.md'),(Join-Path $output 'GUIDE.md'),$false)
$result=[ordered]@{result='V1026_INSTALLED_READ_READY_NOT_SERVER_EXECUTED';helper_path=$helper;helper_sha256=$helperHash;helper_length=(Get-Item -LiteralPath $helper).Length;source_body_sha256=(Get-FileHash -LiteralPath $body -Algorithm SHA256).Hash;test_source_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'test-installed-read-v1026.ps1') -Algorithm SHA256).Hash;launcher_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'RUN_ON_SERVER.txt') -Algorithm SHA256).Hash;reviewed_utility_source_sha256='7943B476C75BF5FC1B8F1CB9D83C6018E787F4ACCEA17D42BF0C6C670FF42C53';utilities=$names;validation_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'local-tests\validation-result.json') -Algorithm SHA256).Hash;server_executed=$false;installer_started=$false;configuration_modified=$false}
[IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 5
