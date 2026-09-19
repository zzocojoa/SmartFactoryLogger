[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$auditScript=Join-Path $PSScriptRoot 'read-server-paths.ps1'
$parseErrors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($auditScript,[ref]$tokens,[ref]$parseErrors)
$checks=[Collections.Generic.List[string]]::new()
function Assert-Test { param([bool]$OK,[string]$Label) if(-not $OK){throw $Label};$checks.Add($Label) }
Assert-Test (@($parseErrors).Count -eq 0) 'Native PS5.1 parse'
foreach($fn in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$commands=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.CommandAst]},$true) |
    ForEach-Object { $_.GetCommandName() } | Where-Object { $null -ne $_ })
$allowed=@('Set-StrictMode','Get-AuditPlainPathState','Get-AuditDirectoryWindow','Get-AuditProtectionClass',
    'Write-Host','Get-Process','Where-Object','Sort-Object','ConvertTo-Json')
Assert-Test (@($commands|Where-Object {$_ -notin $allowed}).Count -eq 0) 'Only metadata/report command allowlist'
$members=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.InvokeMemberExpressionAst]},$true) |
    ForEach-Object {$_.Member.Extent.Text})
Assert-Test (@($members|Where-Object {$_ -match '^(Delete|Move|Copy|CreateDirectory|Open|ReadAllBytes|ReadAllText|WriteAll.*|Start|Kill|GetResponse)$'}).Count -eq 0) 'No content read, data writes, network or process control members'
Assert-Test ((Get-AuditPlainPathState '\\server\share\x') -ceq 'UNSUPPORTED_PATH') 'UNC not traversed'
Assert-Test ((Get-AuditPlainPathState 'C:\temp\x:stream') -ceq 'UNSUPPORTED_PATH') 'ADS path rejected'
Assert-Test ((Get-AuditPlainPathState 'C:\temp\..\Windows') -ceq 'NONCANONICAL_PATH') 'Dotdot not normalized into a new target'
Assert-Test ((Get-AuditPlainPathState 'C:\temp\*.txt') -ceq 'UNSUPPORTED_PATH') 'Glob path rejected'
Assert-Test ((Get-AuditPlainPathState $PSScriptRoot) -ceq 'PLAIN') 'Ordinary local directory metadata'
$absent=Join-Path $PSScriptRoot ('absent-'+[guid]::NewGuid().ToString('N'))
Assert-Test ((Get-AuditPlainPathState $absent) -ceq 'ABSENT') 'Missing path distinct from unreadable'
$absentWindow=Get-AuditDirectoryWindow $absent
Assert-Test ($absentWindow.state -ceq 'ABSENT' -and -not $absentWindow.total_tree_size_known) 'Missing path has no recursive size claim'
$single=Get-AuditDirectoryWindow $auditScript
Assert-Test ($single.state -ceq 'FILE_METADATA_ONLY' -and $single.immediate_file_bytes -gt 0) 'Regular file metadata without content'
$window=Get-AuditDirectoryWindow -Path $PSScriptRoot -Pattern '^read-server-paths\.ps1$'
Assert-Test ($window.state -ceq 'DIRECT_CHILDREN_ONLY' -and @($window.matches).Count -eq 1) 'Exact candidate matching in direct children'
Assert-Test (-not $window.deletion_approved -and -not $window.recursive -and -not $window.total_tree_size_known) 'Inventory never grants deletion or full coverage'
$partialWindow=Get-AuditDirectoryWindow -Path $PSScriptRoot -Limit 1
Assert-Test ($partialWindow.state -ceq 'ENTRY_LIMIT_PARTIAL' -and $partialWindow.observed_entries -eq 1) 'Limit reports partial, not complete'
Assert-Test ((Get-AuditProtectionClass 'C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs') -ceq 'PROTECT_RUNTIME_DATA_OR_INSTALL') 'Runtime child protected'
Assert-Test ((Get-AuditProtectionClass 'C:\Users\user\AppData\Roaming\SmartFactoryLogger-copy') -ceq 'REVIEW_ONLY_NOT_DELETE_APPROVED') 'Sibling name is not runtime child or deletion approval'
Assert-Test ((Get-AuditProtectionClass 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2') -ceq 'PROTECT_RUNTIME_DATA_OR_INSTALL') 'Installed directory protected'
[pscustomobject]@{
    result='READ_ONLY_PATH_DISCOVERY_FUNCTION_TEST_PASS';assertions=$checks.Count;checks=@($checks.ToArray())
    powershell=$PSVersionTable.PSVersion.ToString();server_main_executed=$false
    actual_server_scanned=$false;filesystem_writes_performed=$false
    limitations=@('No actual access-denied or reparse fixture tested','No hostile concurrent path replacement test',
        'No real server process/path inventory, recursive inventory or custom config resolution')
} | ConvertTo-Json -Depth 5
