Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# Load only pure validation/copy functions; never execute the real migration entrypoint.
$tokens=$null;$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'migrate-desktop-test.ps1'),[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Migration script parse failed'}
foreach($name in @('AssertPlain','StreamHash','AclSignature','AssertFlatInventory','CopyVerifiedFile','AssertChildPath','DestinationRelative','AssertTreeInventory','VerifyArchiveEntry','AssertArchiveMappings','ReferencesCollection','AssertCollectionMappings')){
    $definition=$ast.FindAll({param($node) $node-is[Management.Automation.Language.FunctionDefinitionAst]},$false)|Where-Object Name -ceq $name
    if(@($definition).Count-ne 1){throw "Missing function: $name"}
    . ([scriptblock]::Create($definition.Extent.Text))
}
function Require($Condition,[string]$Message){if(-not$Condition){throw $Message}}
function ExpectFailure([scriptblock]$Action,[string]$Message){
    $failed=$false
    try{& $Action}catch{$failed=$true}
    Require $failed $Message
}
Require ((DestinationRelative 'spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727\nested\a.txt' 'desktop-release')-ceq'kit-077b6b1\nested\a.txt') 'Alias differs from the reviewed field-kit mapping'
Require ((DestinationRelative 'spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727-other\a.txt' 'desktop-release')-ceq'spot_connecttimeout_field_kit_077b6b1c_rebuilt_20260727-other\a.txt') 'Alias must not match a prefix lookalike'
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('sfl-migration-unit-'+[Guid]::NewGuid().ToString('N'))
$source=Join-Path $fixture 'source';$destination=Join-Path $fixture 'destination'
$sourceFile=Join-Path $source 'sample.bin';$copyFile=Join-Path $destination 'sample.bin'
$badFile=Join-Path $destination 'bad.bin';$extraFile=Join-Path $source 'extra.bin'
$zipFile=Join-Path $fixture 'retained.zip';$linked=Join-Path $fixture 'linked'
$nested=Join-Path $source 'nested';$nestedFile=Join-Path $nested 'proof.txt'
$longName=('x'*(259-$destination.Length-1-4))+'.bin'
$longSource=Join-Path $source $longName;$longCopy=Join-Path $destination $longName
$pin=$null;$sourcePin=$null;$zipPin=$null
try{
    [void](New-Item -ItemType Directory -Path $source)
    [void](New-Item -ItemType Directory -Path $destination)
    [IO.File]::WriteAllBytes($sourceFile,[byte[]](0,1,2,128,255))
    $oldTime=[datetime]::SpecifyKind([datetime]'2024-01-02T03:04:05',[DateTimeKind]::Utc)
    [IO.File]::SetCreationTimeUtc($sourceFile,$oldTime)
    [IO.File]::SetLastWriteTimeUtc($sourceFile,$oldTime)
    $acl=Get-Acl -LiteralPath $source
    $acl.SetAccessRuleProtection($true,$true)
    Set-Acl -LiteralPath $destination -AclObject $acl
    $record=[pscustomobject]@{name='sample.bin';source=$sourceFile;destination=$copyFile;bytes=5;sha256=(Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash}
    $sourcePin=[IO.File]::Open($sourceFile,'Open','Read','Read')
    $pin=CopyVerifiedFile $record
    Require ($pin-is[IO.FileStream]) 'Copy function must return exactly one pinned stream'
    Require ((StreamHash $pin)-ceq$record.sha256) 'Copy hash differs'
    Require ((AclSignature (Get-Acl -LiteralPath $sourceFile))-ceq(AclSignature (Get-Acl -LiteralPath $copyFile))) 'Copy broadens access'
    Require ([IO.File]::GetCreationTimeUtc($copyFile)-eq$oldTime) 'Creation timestamp differs'
    Require ([IO.File]::GetLastWriteTimeUtc($copyFile)-eq$oldTime) 'Write timestamp differs'
    AssertFlatInventory $source @($record) 'source'
    AssertFlatInventory $destination @($record) 'destination'
    $dirs=@([pscustomobject]@{source=$source;destination=$destination})
    AssertCollectionMappings @($record) $dirs $source $destination
    $keeper=[pscustomobject]@{source=$sourceFile;destination=$copyFile;action='COPY';bytes=5;sha256=$record.sha256;retained_archive=$null;retained_file=$null}
    $fileDuplicate=[pscustomobject]@{source=(Join-Path $source 'other\sample.bin');destination=$null;action='FILE_DUPLICATE';bytes=5;sha256=$record.sha256;retained_archive=$null;retained_file=[pscustomobject]@{source=$sourceFile;path=$copyFile;bytes=5;sha256=$record.sha256}}
    AssertArchiveMappings @($keeper,$fileDuplicate) $source $destination
    $fileDuplicate.retained_file.sha256='0'*64
    ExpectFailure {AssertArchiveMappings @($keeper,$fileDuplicate) $source $destination} 'Duplicate digest mismatch must fail'
    $fileDuplicate.retained_file.sha256=$record.sha256
    $fileDuplicate.retained_file.source=$fileDuplicate.source
    ExpectFailure {AssertArchiveMappings @($keeper,$fileDuplicate) $source $destination} 'Duplicate chains must fail'
    $fileDuplicate.retained_file.source=$sourceFile
    $fileDuplicate.retained_file.path=Join-Path $fixture 'escaped.bin'
    ExpectFailure {AssertArchiveMappings @($keeper,$fileDuplicate) $source $destination} 'Out-of-bound keeper must fail'
    $badMapping=[pscustomobject]@{name='sample.bin';source=$sourceFile;destination=(Join-Path $fixture 'escaped.bin');bytes=5}
    ExpectFailure {AssertCollectionMappings @($badMapping) $dirs $source $destination} 'Destination escape must fail before writes'
    AssertTreeInventory $source @($record) $dirs 'source'
    AssertTreeInventory $destination @($record) $dirs 'destination'
    [void](New-Item -ItemType Directory -Path $nested)
    [IO.File]::WriteAllBytes($nestedFile,[byte[]](3))
    $nestedRecord=[pscustomobject]@{name='nested\proof.txt';source=$nestedFile;destination=(Join-Path $destination 'nested\proof.txt');bytes=1}
    $nestedDirs=@($dirs)+[pscustomobject]@{source=$nested;destination=(Join-Path $destination 'nested')}
    AssertCollectionMappings @($record,$nestedRecord) $nestedDirs $source $destination
    AssertTreeInventory $source @($record,$nestedRecord) $nestedDirs 'source'
    Remove-Item -LiteralPath $nestedFile
    Remove-Item -LiteralPath $nested
    ExpectFailure {AssertChildPath $fixture $source} 'Parent directory must be rejected'
    ExpectFailure {AssertChildPath ($source+'-other') $source} 'Prefix lookalike must be rejected'
    ExpectFailure {AssertTreeInventory $source @($record,$record) $dirs 'source'} 'Duplicate mapping must fail'
    Require (ReferencesCollection ('"'+$source+'\sample.bin"') $source) 'Real registration must be detected'
    Require (-not(ReferencesCollection ($source+'Logger\sample.bin') $source)) 'Prefix lookalike is not a registration'
    [void](New-Item -ItemType Junction -Path $linked -Target $source)
    ExpectFailure {AssertPlain (Join-Path $linked 'sample.bin')} 'Junction traversal must fail'
    $zip=[IO.Compression.ZipFile]::Open($zipFile,[IO.Compression.ZipArchiveMode]::Create)
    try{
        $entry=$zip.CreateEntry('proof/sample.bin');$out=$entry.Open()
        try{$content=[byte[]](0,1,2,128,255);$out.Write($content,0,$content.Length)}finally{$out.Dispose()}
    }finally{$zip.Dispose()}
    $zipPin=[IO.File]::Open($zipFile,'Open','Read','Read')
    $duplicate=[pscustomobject]@{bytes=5;sha256=$record.sha256;retained_archive=[pscustomobject]@{entry='proof/sample.bin'}}
    VerifyArchiveEntry $duplicate $zipPin
    $duplicate.sha256='0'*64
    ExpectFailure {VerifyArchiveEntry $duplicate $zipPin} 'Changed archive content must fail'
    $duplicate.sha256=$record.sha256;$duplicate.retained_archive.entry='missing.bin'
    ExpectFailure {VerifyArchiveEntry $duplicate $zipPin} 'Missing archive member must fail'
    ExpectFailure {CopyVerifiedFile $record} 'Existing evidence must not be overwritten'
    $bad=[pscustomobject]@{name='bad.bin';source=$sourceFile;destination=$badFile;bytes=5;sha256=('0'*64)}
    ExpectFailure {CopyVerifiedFile $bad} 'Hash mismatch must fail'
    Require ([IO.File]::Exists($sourceFile)-and[IO.File]::Exists($badFile)) 'Failure must preserve source and partial copy'
    [IO.File]::WriteAllBytes($extraFile,[byte[]](4))
    ExpectFailure {AssertFlatInventory $source @($record) 'source'} 'Unexpected source file must fail'
    ExpectFailure {AssertTreeInventory $source @($record) $dirs 'source'} 'New tree file must fail'
    $escape=[pscustomobject]@{name='sample.bin';source=$badFile;destination=$copyFile;bytes=5;sha256=$record.sha256}
    ExpectFailure {AssertFlatInventory $destination @($escape) 'source'} 'Out-of-bound source mapping must fail'
    [IO.File]::WriteAllBytes($longSource,[byte[]](9,8,7))
    $longRecord=[pscustomobject]@{source=$longSource;destination=$longCopy;bytes=3;sha256=(Get-FileHash -LiteralPath $longSource).Hash}
    $longPin=CopyVerifiedFile $longRecord
    try{Require ($longCopy.Length-eq 259-and(StreamHash $longPin)-ceq$longRecord.sha256) 'Local 259-character path copy failed'}finally{$longPin.Dispose()}
    '[PASS] Copy, ACL, timestamps, no overwrite, mismatch preservation, inventories, archive content, links and registration boundaries.'
}finally{
    if($null-ne$pin){$pin.Dispose()}
    if($null-ne$sourcePin){$sourcePin.Dispose()}
    if($null-ne$zipPin){$zipPin.Dispose()}
    if(Test-Path -LiteralPath $linked){[IO.Directory]::Delete($linked)}
    if(Test-Path -LiteralPath $zipFile){Remove-Item -LiteralPath $zipFile -Force}
    if(Test-Path -LiteralPath $nestedFile){Remove-Item -LiteralPath $nestedFile -Force}
    if(Test-Path -LiteralPath $nested){Remove-Item -LiteralPath $nested}
    # Exact synthetic leaves only. Never recursively delete the fixture or any external path.
    foreach($leaf in @($sourceFile,$copyFile,$badFile,$extraFile,$longSource,$longCopy)){
        if([IO.Path]::GetDirectoryName($leaf)-cnotin@($source,$destination)){throw 'Test cleanup escaped fixture'}
        if(Test-Path -LiteralPath $leaf){Remove-Item -LiteralPath $leaf -Force}
    }
    foreach($dir in @($source,$destination,$fixture)){
        if(Test-Path -LiteralPath $dir){
            if(@(Get-ChildItem -LiteralPath $dir -Force).Count){throw "Unexpected test files remain: $dir"}
            Remove-Item -LiteralPath $dir
        }
    }
}
