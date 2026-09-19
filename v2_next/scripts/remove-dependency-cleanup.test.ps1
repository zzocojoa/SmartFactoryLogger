Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$errors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'remove-dependency-cleanup.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
foreach($name in @('ChildPath','StreamHash','NsMatches','AssertMetadata','JournalOffset','JournalTransition','CheckTree','InlineEvidence','AssertTrustedAcl','NoStreams')){
    $function=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq$name},$true)
    if($null-eq$function){throw 'Missing pure helper'}
    . ([scriptblock]::Create($function.Extent.Text))
}
$cases=0
function Equal($a,$b){if($a-cne$b){throw "Assertion failed: $a != $b"};$script:cases++}
function Reject([scriptblock]$Code){$rejected=$false;try{&$Code}catch{$rejected=$true};if(-not$rejected){throw 'Expected rejection'};$script:cases++}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.tmp\synthetic-only'))
Equal (InlineEvidence @(@{reason='launcher'},@{evidence=@{bytes=3}})).bytes 3
Reject {InlineEvidence @(@{reason='launcher'})}
Reject {InlineEvidence @(@{evidence=@{bytes=3}},@{evidence=@{bytes=3}})}
$acl=[Security.AccessControl.FileSecurity]::new()
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl.SetOwner($sid)
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','Allow'))
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'ReadAndExecute','Allow'))
AssertTrustedAcl $acl;$cases++
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','Allow'))
Reject {AssertTrustedAcl $acl}
Equal (ChildPath $root 'a/b') ($root+'\a\b')
foreach($relative in @('','../a','/a','a/../b','a/./b','a//b','a/','a\b','C:/a','a:stream',"a`0b")){Reject {ChildPath $root $relative}}
Equal (NsMatches ([long]621355968000000001) '100') $true
Equal (NsMatches ([long]621355968000000001) '101') $false
Equal (NsMatches ([long]639250478619133774) '1789451061913377400') $true
$m=@{attributes=32;sddl='D:test';creation_ticks='639250478619133774';write_ticks='639250478619133774'}
AssertMetadata $m $m;$cases++
foreach($key in $m.Keys){$other=$m.Clone();$other[$key]='DIFFERENT';Reject {AssertMetadata $m $other}}
$id='fixture-guid';$json='{"이름":"증거","file_states":"fixture-guid:PPP","directory_states":"fixture-guid:PP"}'
$offset=JournalOffset $json 'file_states' $id 3
$dirOffset=JournalOffset $json 'directory_states' $id 2
$stream=[IO.MemoryStream]::new([Text.Encoding]::UTF8.GetBytes($json),$true)
try{
    JournalTransition $stream $offset 0 3 'P' 'R'
    $state=[Text.Encoding]::UTF8.GetString($stream.ToArray())|ConvertFrom-Json
    Equal $state.file_states 'fixture-guid:RPP'
    Reject {JournalTransition $stream $offset 0 3 'P' 'R'}
    Reject {JournalTransition $stream $offset 1 3 'P' 'D'}
    Reject {JournalTransition $stream $offset -1 3 'P' 'R'}
    Reject {JournalTransition $stream $offset 3 3 'P' 'R'}
    Reject {JournalTransition $stream 10000 0 3 'P' 'R'}
    JournalTransition $stream $offset 0 3 'R' 'D'
    JournalTransition $stream $dirOffset 1 2 'P' 'R'
    $state=[Text.Encoding]::UTF8.GetString($stream.ToArray())|ConvertFrom-Json
    Equal $state.file_states 'fixture-guid:DPP';Equal $state.directory_states 'fixture-guid:PR';Equal $state.'이름' '증거'
    Reject {JournalOffset '{"file_states":"fixture-guid:DDD"}' 'file_states' $id 3}
    Reject {JournalOffset ($json+$json) 'file_states' $id 3}
}finally{$stream.Dispose()}
$stream=[IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes('abc'))
try{Equal (StreamHash $stream) 'BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD'}finally{$stream.Dispose()}
$removeCommands=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.CommandAst]-and$n.GetCommandName()-eq'Remove-Item'},$true))
Equal $removeCommands.Count 2
foreach($command in $removeCommands){
    $params=@($command.CommandElements|Where-Object {$_-is[Management.Automation.Language.CommandParameterAst]}|ForEach-Object ParameterName)
    Equal ($params-contains'LiteralPath') $true;Equal ($params-contains'Recurse') $false
}
$whereCommands=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.CommandAst]-and$n.GetCommandName()-eq'Where-Object'},$true))
foreach($command in $whereCommands){
    foreach($param in @($command.CommandElements|Where-Object {$_-is[Management.Automation.Language.CommandParameterAst]})){
        Equal ($param.ParameterName-cin@('ceq','cne','eq','ne')) $true
    }
}
$fixture=[IO.Path]::GetTempFileName()
try{
    [IO.File]::WriteAllText($fixture,$json,[Text.UTF8Encoding]::new($false))
    $held=[IO.File]::Open($fixture,'Open','ReadWrite','None')
    try{
        JournalTransition $held $offset 0 3 'P' 'R'
        Reject {$other=[IO.File]::Open($fixture,'Open','Read','Read');$other.Dispose()}
        NoStreams $fixture;$cases++
        Equal ([string]::IsNullOrEmpty((Get-Acl -LiteralPath $fixture).Sddl)) $false
    }finally{$held.Dispose()}
    Equal (([IO.File]::ReadAllText($fixture)|ConvertFrom-Json).file_states) 'fixture-guid:RPP'
}finally{Remove-Item -LiteralPath $fixture -Force}
Write-Host "[PASS] $cases dependency cleanup pure/AST tests; no real files or registry changed."
