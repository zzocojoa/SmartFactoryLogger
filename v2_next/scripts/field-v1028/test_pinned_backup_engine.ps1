param(
    [Parameter(Mandatory=$true)][string]$EnginePath,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'native-ps51-required'}
$source=Join-Path $PSScriptRoot 'install-field-candidate.ps1'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
# Import function definitions only; never execute the production install controller.
foreach($definition in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
    . ([scriptblock]::Create($definition.Extent.Text))
}
$root=Plain $OutputRoot
if(Test-Path -LiteralPath $root){throw 'fresh-fixture-required'}
$null=[IO.Directory]::CreateDirectory($root)
$script:held=[Collections.Generic.List[IDisposable]]::new()
$checks=[Collections.Generic.List[string]]::new()
function Pass([bool]$Value,[string]$Name){if(-not $Value){throw ('TEST:'+ $Name)};$checks.Add($Name)}
function RejectPin([string]$Path,[string]$Name){
    $errorText=$null
    try{ImportBackupEngine $Path}catch{$errorText=$_.Exception.Message}
    Pass ($null -ne $errorText -and $errorText.Contains('locked-file-fact')) $Name
}
try {
    $inputStream=LockFile $EnginePath 'fb12e3acb370d86999156600efb3cd23083d890dfec1216cf4e06e9c1cce2a26' 24576
    $raw=New-Object byte[] 24576;$inputStream.Position=0
    $offset=0
    while($offset -lt $raw.Length){$read=$inputStream.Read($raw,$offset,$raw.Length-$offset);Require ($read -gt 0) 'fixture-input-truncated';$offset+=$read}
    $dll=Join-Path $root 'internet-zone.dll';[IO.File]::WriteAllBytes($dll,$raw)
    $zone="[ZoneTransfer]`r`nZoneId=3`r`n"
    Set-Content -LiteralPath $dll -Stream 'Zone.Identifier' -Value $zone -NoNewline -Encoding ASCII
    $before=Fact $dll;$streamsBefore=ConfigStreamFacts $dll
    $pathLoadError=$null
    try{Add-Type -LiteralPath $dll}catch{$pathLoadError=$_.Exception.ToString()}
    Pass ($null -ne $pathLoadError -and $pathLoadError.Contains('0x80131515')) 'original-path-loader-reproduces-0x80131515'

    $tampered=[byte[]]$raw.Clone();$tampered[100]=$tampered[100] -bxor 1
    $bad=Join-Path $root 'changed.dll';[IO.File]::WriteAllBytes($bad,$tampered)
    RejectPin $bad 'changed-engine-rejected-before-load'
    $short=Join-Path $root 'short.dll';[IO.File]::WriteAllBytes($short,$raw[0..99])
    RejectPin $short 'wrong-length-engine-rejected-before-load'

    ImportBackupEngine $dll
    Pass ($null -ne ('SflColdCopyStreamsV2.Engine' -as [type])) 'pinned-byte-loader-resolves-engine'
    $writeDenied=$false
    try{[IO.File]::WriteAllBytes($dll,$raw)}catch{$writeDenied=$true}
    Pass $writeDenied 'engine-held-against-replacement'
    Pass (((Fact $dll)|ConvertTo-Json -Compress) -ceq ($before|ConvertTo-Json -Compress)) 'dll-default-bytes-preserved'
    Pass (((ConfigStreamFacts $dll)|ConvertTo-Json -Compress) -ceq ($streamsBefore|ConvertTo-Json -Compress)) 'zone-stream-preserved'

    $data=Join-Path $root 'data';$null=[IO.Directory]::CreateDirectory($data)
    $sample=Join-Path $data 'sample.csv';[IO.File]::WriteAllText($sample,'closed-fixture')
    Set-Content -LiteralPath $sample -Stream 'fixture' -Value 'preserved-stream' -NoNewline
    $engine=[SflColdCopyStreamsV2.Engine]::new([string[]]@($data),[Action]{},[Action[string,long,long,long]]{param($a,$b,$c,$d)})
    $copy=Join-Path $root 'copy';$manifest=Join-Path $root 'files.tsv'
    $backup=$engine.Backup($copy,$manifest)
    $verified=$engine.Verify($manifest,$backup.ManifestSha256,$copy,$null,$false)
    Pass ($verified.Files -eq 1 -and $verified.NamedStreams -eq 1 -and $verified.Bytes -eq $backup.Bytes) 'loaded-engine-verifies-default-and-named-streams'
    Pass ((Get-Content -LiteralPath (Join-Path $copy 'r0\sample.csv') -Stream 'fixture' -Raw) -ceq 'preserved-stream') 'copied-named-stream-content-preserved'
    $result=[ordered]@{status='PASS';checks=$checks.Count;names=$checks.ToArray();source_sha256=(Fact $source).sha256;engine_sha256=$before.sha256;path_loader_error=$pathLoadError;server_accessed=$false;production_installation_performed=$false;security_settings_changed=$false;source_streams_removed=$false}
    [IO.File]::WriteAllText((Join-Path $root 'review.json'),($result|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    $result|ConvertTo-Json -Depth 5
} finally {foreach($handle in $script:held){$handle.Dispose()}}
