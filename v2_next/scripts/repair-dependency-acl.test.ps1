param([switch]$PureOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major-lt 7){throw 'PowerShell 7 required; no files changed'}
$errors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'repair-dependency-acl.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
foreach($name in @('RestrictedDacl','RuleKeys','AssertInheritedOnly','AccessSddl','OwnerGroup')){
    $function=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq$name},$true)
    . ([scriptblock]::Create($function.Extent.Text))
}
$cases=0
function Equal($a,$b){if($a-cne$b){throw "Assertion failed: $a != $b"};$script:cases++}
function Reject([scriptblock]$Code){$rejected=$false;try{&$Code}catch{$rejected=$true};if(-not$rejected){throw 'Expected rejection'};$script:cases++}
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$trusted=@($sid,'S-1-5-18','S-1-5-32-544')
$sddl="O:${sid}G:SYD:AI(A;OICIID;FA;;;${sid})(A;OICIID;FA;;;SY)(A;OICIID;FA;;;BA)(A;OICIID;0x1301bf;;;WD)(A;OICIID;FR;;;AU)"
$original=[Security.AccessControl.DirectorySecurity]::new();$original.SetSecurityDescriptorSddlForm($sddl)
AssertInheritedOnly $original;$cases++
$restricted=RestrictedDacl $sddl $trusted
Equal $restricted.AreAccessRulesProtected $true
$rules=@($restricted.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
Equal $rules.Count 4
Equal @($rules|Where-Object {$_.IdentityReference.Value-ceq'S-1-1-0'}).Count 0
Equal @($rules|Where-Object {$_.IdentityReference.Value-ceq'S-1-5-11'}).Count 1
Equal @($rules|Where-Object IsInherited).Count 0
Reject {AssertInheritedOnly $restricted}
Equal (OwnerGroup $restricted) ''
Equal (RuleKeys $restricted $trusted $false $false) (RuleKeys $original $trusted $true $true)
$directoryRoundtrip=[Security.AccessControl.DirectorySecurity]::new();$directoryRoundtrip.SetSecurityDescriptorSddlForm($sddl)
Equal (RuleKeys $directoryRoundtrip $trusted $true $true) (RuleKeys $restricted $trusted $false $false)
$fileSddl="O:${sid}G:SYD:AI(A;ID;FA;;;${sid})(A;ID;0x1301bf;;;WD)"
$fileRoundtrip=[Security.AccessControl.FileSecurity]::new();$fileRoundtrip.SetSecurityDescriptorSddlForm($fileSddl)
Equal (RuleKeys $fileRoundtrip $trusted $true $false) ("${sid}|0|2032127|0|0|True")
$denied=[Security.AccessControl.DirectorySecurity]::new();$denied.SetSecurityDescriptorSddlForm("O:${sid}G:SYD:AI(D;OICIID;FW;;;WD)(A;OICIID;FA;;;${sid})")
Equal @((RestrictedDacl $denied.GetSecurityDescriptorSddlForm('All') $trusted).GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|Where-Object AccessControlType -eq Deny).Count 1
$commands=@($ast.FindAll({param($n)$n-is[Management.Automation.Language.CommandAst]-and$n.GetCommandName()-eq'Set-Acl'},$true))
Equal $commands.Count 1
Equal (@($commands[0].CommandElements|Where-Object {$_-is[Management.Automation.Language.CommandParameterAst]}|ForEach-Object ParameterName)-contains'LiteralPath') $true
Equal @($ast.FindAll({param($n)$n-is[Management.Automation.Language.CommandAst]-and$n.GetCommandName()-eq'Remove-Item'},$true)).Count 0

# Owned isolated fixture only; no managed candidates or registry writes.
if(-not$PureOnly){
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('sfl-acl-test-'+[Guid]::NewGuid().ToString('N'))
$child=Join-Path $fixture 'child';$file=Join-Path $child 'sample.txt'
$before=$null
try{
    [void][IO.Directory]::CreateDirectory($child)
    [IO.File]::WriteAllText($file,'fixture')
    $before=Get-Acl -LiteralPath $fixture
    $parentAcl=RestrictedDacl $sddl @($trusted+'S-1-1-0')
    Set-Acl -LiteralPath $fixture -AclObject $parentAcl
    $childBefore=Get-Acl -LiteralPath $child;$fileBefore=Get-Acl -LiteralPath $file
    $change=RestrictedDacl (Get-Acl -LiteralPath $fixture).Sddl $trusted
    Set-Acl -LiteralPath $fixture -AclObject $change
    $childAfter=Get-Acl -LiteralPath $child;$fileAfter=Get-Acl -LiteralPath $file
    Equal (RuleKeys $childAfter $trusted $false $false) (RuleKeys $childBefore $trusted $true $false)
    Equal (RuleKeys $fileAfter $trusted $false $false) (RuleKeys $fileBefore $trusted $true $false)
    Equal (OwnerGroup $childBefore) (OwnerGroup $childAfter)
    Equal (OwnerGroup $fileBefore) (OwnerGroup $fileAfter)
    Equal @($childAfter.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|Where-Object {$_.IdentityReference.Value-ceq'S-1-1-0'}).Count 0
    AssertInheritedOnly $childAfter;$cases++
    Equal ([IO.File]::ReadAllText($file)) 'fixture'
}finally{
    if(Test-Path -LiteralPath $fixture){
        if($null-ne$before){$restore=[Security.AccessControl.DirectorySecurity]::new();$restore.SetSecurityDescriptorSddlForm($before.Sddl,[Security.AccessControl.AccessControlSections]::Access);Set-Acl -LiteralPath $fixture -AclObject $restore}
        if(Test-Path -LiteralPath $file){Remove-Item -LiteralPath $file -Force}
        if(Test-Path -LiteralPath $child){Remove-Item -LiteralPath $child -Force}
        Remove-Item -LiteralPath $fixture -Force
    }
}
}
Write-Host "[PASS] $cases ACL tests; PureOnly=$PureOnly; no managed candidates or registry changed."
