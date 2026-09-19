[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native PS5.1 x64 required.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$Ok,[string]$Name) if(-not $Ok){throw $Name};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name}
function CopyObject {param([object]$Value) return ConvertFrom-Json -InputObject ($Value|ConvertTo-Json -Depth 20)}
$gatePath=Join-Path $PSScriptRoot 'release-pair-resume-gate.ps1'
$t=$null;$e=$null;$gateAst=[Management.Automation.Language.Parser]::ParseFile($gatePath,[ref]$t,[ref]$e)
Check (@($e).Count -eq 0) 'Gate native parser'
foreach($fn in $gateAst.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
$targets=@('C:\synthetic\inventory','C:\synthetic');$hash='A'*64
$backup=[pscustomobject]@{schema_version='sflops-exact-two-acl-repair-v1';targets=@(
    [pscustomobject]@{path=$targets[1];sddl='old-root'},[pscustomobject]@{path=$targets[0];sddl='old-inventory'})}
$events=@(
    [pscustomobject]@{event='PLAN';backup_sha256=$hash},
    [pscustomobject]@{event='ACL_CHANGE_INTENT';path=$targets[0];before_sddl='old-inventory'},
    [pscustomobject]@{event='ACL_CHANGE_VERIFIED';path=$targets[0];after_sddl='new-inventory'},
    [pscustomobject]@{event='ACL_CHANGE_INTENT';path=$targets[1];before_sddl='old-root'},
    [pscustomobject]@{event='ACL_CHANGE_VERIFIED';path=$targets[1];after_sddl='new-root'},
    [pscustomobject]@{event='COMPLETE';backup_sha256=$hash;result='SFLOPS_EXACT_TWO_FOLDER_ACL_REPAIR_PASS';acl_write_returned_success=2;
        original_files_deleted=0;cleanup_retried=$false;recursive_acl_reset_performed=$false;app_restart_performed=$false})
$expected=Assert-ResumeAclRecords $events $backup $targets $hash
Check ($expected.Count -eq 2 -and $expected[$targets[0]] -ceq 'new-inventory' -and $expected[$targets[1]] -ceq 'new-root') 'Complete six-event receipt maps exact ACLs'
foreach($mode in @('partial','wrong-plan-hash','wrong-final-hash','wrong-result','one-write','prior-deletion','prior-cleanup','prior-reset','prior-restart','target-order','before-mismatch','empty-after','event-order')){
    $bad=CopyObject $events
    switch($mode){
        partial {$bad=@($bad[0..4])}
        wrong-plan-hash {$bad[0].backup_sha256='B'*64}
        wrong-final-hash {$bad[5].backup_sha256='B'*64}
        wrong-result {$bad[5].result='HOLD'}
        one-write {$bad[5].acl_write_returned_success=1}
        prior-deletion {$bad[5].original_files_deleted=1}
        prior-cleanup {$bad[5].cleanup_retried=$true}
        prior-reset {$bad[5].recursive_acl_reset_performed=$true}
        prior-restart {$bad[5].app_restart_performed=$true}
        target-order {$bad[1].path=$targets[1]}
        before-mismatch {$bad[1].before_sddl='changed'}
        empty-after {$bad[4].after_sddl=' '}
        event-order {$bad[2].event='ACL_CHANGE_INTENT'}
    }
    Reject {Assert-ResumeAclRecords $bad $backup $targets $hash} ('Receipt rejects '+$mode)
}
$bad=CopyObject $backup;$bad.targets=@($bad.targets[0],$bad.targets[0])
Reject {Assert-ResumeAclRecords $events $bad $targets $hash} 'Backup duplicate/missing target rejected'
$bad=CopyObject $backup;$bad.schema_version='unknown'
Reject {Assert-ResumeAclRecords $events $bad $targets $hash} 'Backup unknown schema rejected'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath=Join-Path $workspace 'artifacts\server-cleanup-release-pair-resume-r1\RUN_RELEASE_PAIR_CLEANUP_RESUME.txt'
$launcher=[IO.File]::ReadAllText($launcherPath)
$t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($launcher,[ref]$t,[ref]$e)
Check (@($e).Count -eq 0) 'Generated outer native parser'
$children=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.StringConstantExpressionAst] -and $n.Value.StartsWith('Set-StrictMode -Version Latest')},$true))
Check ($children.Count -eq 1) 'One literal child payload'
$child=$children[0].Value
$t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($child,[ref]$t,[ref]$e)
Check (@($e).Count -eq 0) 'Generated child native parser'
Check ($launcher.Contains('-NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $encoded')) 'Fresh NoProfile child only'
Check ($child.IndexOf('Invoke-ReleasePairResumeGate $streams $launchGuards') -lt $child.IndexOf('$helperRoot=')) 'ACL evidence gate before new staging and deletion launch'
Check ($child.Contains("-File (Join-Path `$helperRoot 'cleanup-v1019-release-pair.ps1') -Execute") -and $child.Contains('Open-CleanupDirectoryGuard $helperRoot $launchGuards')) 'Fixed existing cleanup protected launch'
Check ($child.Contains('507678162C3521D2F7909137A92308C2C1F48EACA380865CE97B5C7D8C387C57') -and $child.Contains('90EE9F49517AF299AB7A0DBA38053C3B80806DF6E7C662BA765FA754260D9CAD')) 'External ACL evidence pins embedded'
$gate=[IO.File]::ReadAllText($gatePath)
Check ($gate -notmatch 'SetAccessControl|Remove-Item|MarkFile|DeleteEmptyDirectory|WriteAll|Start-Process|Stop-Process|Invoke-WebRequest|Invoke-RestMethod') 'New gate has no writes/deletes/ACL mutation/process/API calls'
# Launch ONLY a benign no-op string padded to the exact real command length.
# The actual child/server helper is parsed, never executed on the developer host.
$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$probe="[Console]::WriteLine('RESUME_LENGTH_PROBE_ONLY');exit 0`n#"
Check ($probe.Length -lt $child.Length) 'Probe padding length valid'
$probe=$probe.PadRight($child.Length,' ')
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
Check ($encoded.Length+250 -le 32000) 'Conservative native command length budget'
$answer=@(& $native -NoLogo -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $encoded)
Check ($LASTEXITCODE -eq 0 -and $answer.Count -eq 1 -and $answer[0] -ceq 'RESUME_LENGTH_PROBE_ONLY') 'Equivalent length native command launches without truncation'
[pscustomobject]@{result='RELEASE_PAIR_RESUME_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();
    actual_launcher_executed=$false;server_execution_performed=$false;encoded_command_chars=$encoded.Length}|ConvertTo-Json -Depth 5
