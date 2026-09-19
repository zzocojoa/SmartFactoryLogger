param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$ReleaseRoot,
    [Parameter(Mandatory=$true)][string]$ExtractedAppRoot,
    [Parameter(Mandatory=$true)][string]$ExtractedNsisRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$source=Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count-ne0){throw($errors|Out-String)}
$checks=[Collections.Generic.List[string]]::new()
function Check{param([bool]$OK,[string]$Name)if(-not$OK){throw('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject{param([scriptblock]$Code,[string]$Name)$failed=$false;try{&$Code|Out-Null}catch{$failed=$true};Check $failed $Name}
$functions=@($ast.FindAll({param($node)$node-is[Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($function in $functions){.([scriptblock]::Create($function.Extent.Text))}
$text=[IO.File]::ReadAllText($source)

Check($functions.Count-eq27)'parse/import functions only; server main not executed'
Check($text.Contains("param([switch]`$Execute)")-and$text.Contains("if (-not `$Execute)"))'explicit execution switch'
Check($text.Contains('Type INSTALL V1.0.26'))'separate operator install token'
Check($text.Contains("`$stageRoot = 'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503'"))'exact completed stage pinned'
Check($text.Contains("`$backupWorkRoot = 'C:\ProgramData\SFLOps\backups\v1025-min-20260916-090230-5ea532c9'"))'exact completed backup pinned'
Check($text.Contains('88FE4660AC294E1484FC9C2C4AA9400E77BC5EB6506FAD28A0E76ECD59F89FD0'))'backup result hash pinned'
Check($text.Contains('85B0B7D46AD4519E7149A3F0F8FAF7DA6F009BE362C169B11C9B529FD147B628'))'backup manifest hash pinned'
Check($text.Contains('F4B2FA04536CCC8B3CF095E2D643E7CB6BE0766CF3BB98D5F7FAF301C5AA5C86'))'stage receipt hash pinned'
Check($text.Contains('1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F'))'installer hash pinned'
Check($text.Contains("automatic_rollback_performed=`$false")-and$text.Contains("fifteen_minute_observation_started=`$false"))'no rollback or Canary claim'
Check($text-notmatch'(?im)^\s*(Stop-Process|taskkill|Remove-Item|Move-Item|Clear-Content|Invoke-Expression)\b')'no force stop cleanup or dynamic execution command'
Check($text.Contains("ShellExecute(`$copy")-and$text.Contains("installer-elevated"))'shell launch plus observed standard-token gate'
Check($text.Contains('Minimal backup excludes accumulated CSV/image/fact logs'))'backup limitation repeated at execution'
Check($text.Contains("LocalJson 'stats'")-and$text.Contains("'app-error-queue'"))'30-second postflight gates app error queue'

if([IO.File]::Exists($OutputRoot)-or[IO.Directory]::Exists($OutputRoot)){throw'Existing fixture output is preserved.'}
$fixture=[IO.Path]::GetFullPath($OutputRoot);[void][IO.Directory]::CreateDirectory($fixture)
$script:pins=[Collections.Generic.List[IDisposable]]::new()

$release=[IO.Path]::GetFullPath($ReleaseRoot)
$installerPath=Join-Path $release 'smart-factory-logger-v2 Setup 1.0.26.exe'
$installerFact=FileFact $installerPath '1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F' 164003067
Check($installerFact.length-eq164003067)'real candidate installer pin'
$identityFact=FileFact (Join-Path $release 'release_identity.json') '7EB46147F55DAD515E507196A7E1FBACD7D1B075E870DB159F82580DA64E3493'
Check($identityFact.length-gt0)'real release identity pin'
$manifestPath=Join-Path $release 'extracted-payload-manifest.json'
$manifestFact=FileFact $manifestPath 'D527AA7F8284AF6917FE1166F070871C07BCA379F03BD32740BDEF70CD48814F'
$manifest=ReadJson $manifestPath
Check(@(Property $manifest 'files').Count-eq1645-and[long](Property $manifest 'file_count')-eq1645)'real payload manifest contract'

$app=[IO.Path]::GetFullPath($ExtractedAppRoot)
$manifestMap=@{}
foreach($entry in @(Property $manifest 'files')){$manifestMap[[string]$entry.path]=$entry}
$actual=@(Get-ChildItem -LiteralPath $app -File -Recurse -Force)
Check($actual.Count-eq1645)'real extracted payload membership count'
$realRows=[Collections.Generic.List[string]]::new();[long]$realBytes=0
foreach($file in $actual){
    $relative=$file.FullName.Substring($app.TrimEnd('\').Length+1).Replace('\','/')
    if(-not$manifestMap.ContainsKey($relative)){throw('TEST FAILED: unexpected real payload '+$relative)}
    $stream=[IO.File]::Open($file.FullName,'Open','Read','Read')
    try{$hash=HashStream $stream;$length=[long]$stream.Length}finally{$stream.Dispose()}
    $entry=$manifestMap[$relative]
    if($length-ne[long]$entry.length-or$hash-cne[string]$entry.sha256){throw('TEST FAILED: real payload hash '+$relative)}
    $realRows.Add("$relative`0$length`0$hash`n");$realBytes+=$length
}
$sorted=$realRows.ToArray();[Array]::Sort($sorted,[StringComparer]::Ordinal)
$sha=[Security.Cryptography.SHA256]::Create()
try{$realTree=[BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($sorted)))).Replace('-','')}finally{$sha.Dispose()}
Check($realBytes-eq560922854-and$realTree-ceq'0C18CE2E9F810A8636DA007BE00F02ADD5AEB7869E693E4827774B0E3C53F908')'real extracted payload tree identity'

$uninstallerPath=Join-Path ([IO.Path]::GetFullPath($ExtractedNsisRoot)) 'Uninstall smart-factory.exe'
$uninstallerFact=FileFact $uninstallerPath '610F5540AA0C6C24EF7DBEFFC1B5EE749D1B9C8CDCFC2B6EF643F8EA6F0DE837' 234261
Check($uninstallerFact.length-eq234261)'real generated uninstaller pin'

$treeRoot=Join-Path $fixture 'installed';[void][IO.Directory]::CreateDirectory($treeRoot)
[void][IO.Directory]::CreateDirectory((Join-Path $treeRoot 'resources'))
[IO.File]::WriteAllText((Join-Path $treeRoot 'smart-factory.exe'),'app')
[IO.File]::WriteAllText((Join-Path $treeRoot 'resources\app.asar'),'asar')
[IO.File]::WriteAllText((Join-Path $treeRoot 'Uninstall smart-factory.exe'),'uninstaller')
function SmallEntry{param([string]$Root,[string]$Name)$path=Join-Path $Root $Name.Replace('/','\');$s=[IO.File]::Open($path,'Open','Read','Read');try{$h=HashStream $s;$l=$s.Length}finally{$s.Dispose()};return [pscustomobject]@{path=$Name;length=[long]$l;sha256=$h}}
$smallFiles=@(SmallEntry $treeRoot 'smart-factory.exe';SmallEntry $treeRoot 'resources/app.asar')
$payloadRows=@($smallFiles|ForEach-Object{"$($_.path)`0$($_.length)`0$($_.sha256)`n"});[Array]::Sort($payloadRows,[StringComparer]::Ordinal)
$sha=[Security.Cryptography.SHA256]::Create();try{$smallPayloadTree=[BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($payloadRows)))).Replace('-','')}finally{$sha.Dispose()}
$smallManifest=[pscustomobject]@{tree_sha256=$smallPayloadTree;files=$smallFiles}
$un=SmallEntry $treeRoot 'Uninstall smart-factory.exe'
$allRows=@($payloadRows)+@("$($un.path)`0$($un.length)`0$($un.sha256)`n");[Array]::Sort($allRows,[StringComparer]::Ordinal)
$sha=[Security.Cryptography.SHA256]::Create();try{$smallTree=[BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($allRows)))).Replace('-','')}finally{$sha.Dispose()}
$script:expectedPayloadFiles=2;$script:expectedPayloadTree=$smallPayloadTree;$script:uninstallerName=$un.path;$script:uninstallerLength=$un.length;$script:uninstallerHash=$un.sha256
$script:expectedInstalledFiles=3;$script:expectedInstalledBytes=[long](($smallFiles|Measure-Object length -Sum).Sum)+$un.length;$script:expectedInstalledTree=$smallTree
$tree=GetInstalledTree $treeRoot $smallManifest
Check($tree.file_count-eq3-and$tree.tree_sha256-ceq$smallTree)'synthetic installed tree pass'
[IO.File]::AppendAllText((Join-Path $treeRoot 'resources\app.asar'),'tamper')
Reject{GetInstalledTree $treeRoot $smallManifest}'installed payload tamper rejected'

$acl=PrivateAcl
$aclRules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
Check($acl.AreAccessRulesProtected-and$aclRules.Count-eq2-and@($aclRules|Where-Object{$_.IdentityReference.Value-cin@('S-1-5-32-544','S-1-5-18')}).Count-eq2)'private ACL object contract'
$private=Join-Path $fixture 'private';[void][IO.Directory]::CreateDirectory($private)
$script:runRoot=$private
$receiptHash=WriteJsonNew (Join-Path $private 'fixture.json') ([ordered]@{result='PASS';value=1})
AssertSidecar (Join-Path $private 'fixture.json.sha256.txt') $receiptHash
Check($receiptHash-cmatch'^[A-F0-9]{64}$')'new receipt and sidecar'

InitializeTokenInspector
Check(('SflInstallToken'-as[type])-ne$null)'token inspector compiles under Windows PowerShell 5.1'

foreach($pin in $pins){$pin.Dispose()}
$helperSha=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$result=[pscustomobject]@{result='V1026_INSTALL_HELPER_LOCAL_TEST_PASS';assertions=$checks.Count;powershell_version=$PSVersionTable.PSVersion.ToString();helper_sha256=$helperSha;installer_sha256=$installerFact.sha256;payload_tree_sha256=$realTree;uninstaller_sha256=$uninstallerFact.sha256;server_main_executed=$false;installer_started=$false;network_queries_performed=$false;product_changes_made=$false;checks=$checks.ToArray()}
$json=$result|ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $fixture 'validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
