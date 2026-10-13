param([Parameter(Mandatory=$true)][string]$TestRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Require([bool]$Value,[string]$Message){if(-not $Value){throw $Message}}
Require (-not [IO.Directory]::Exists($TestRoot)) 'test root must be new'
[void][IO.Directory]::CreateDirectory($TestRoot)
. (Join-Path $PSScriptRoot 'read-operating-data-inventory.ps1')
$source=Join-Path $TestRoot 'source'
$outside=Join-Path $TestRoot 'outside'
[void][IO.Directory]::CreateDirectory($source)
[void][IO.Directory]::CreateDirectory($outside)
[IO.File]::WriteAllText((Join-Path $source 'sample.csv'),"sample_seq,Temperature`r`n1,500`r`n")
[IO.File]::WriteAllText((Join-Path $outside 'must-not-follow.csv'),'outside')
$junction=Join-Path $source 'linked'
$null=New-Item -ItemType Junction -Path $junction -Target $outside -ErrorAction Stop
$before=(Get-FileHash -LiteralPath (Join-Path $source 'sample.csv') -Algorithm SHA256).Hash
$records=[Collections.Generic.List[object]]::new()
$callback={param($entry) $records.Add($entry)}
$result=Read-SFLDataInventory -Roots @([pscustomobject]@{id='fixture';path=$source;recursive=$true}) -OnEntry $callback
Require ($result.file_count -eq 1) 'only regular source file is counted'
Require ($result.reparse_count -eq 1) 'junction must be recorded'
Require (@($records|Where-Object {$_.path -like '*must-not-follow*'}).Count -eq 0) 'junction target was followed'
Require ($before -ceq (Get-FileHash -LiteralPath (Join-Path $source 'sample.csv') -Algorithm SHA256).Hash) 'source bytes changed'
Require ($result.full_data_gate -ceq 'NOT_EVALUATED') 'metadata inventory cannot certify full data'
$relativeResult=Read-SFLDataInventory -Roots @([pscustomobject]@{id='invalid';path='C:';recursive=$false}) -OnEntry {param($entry)} -MaxSeconds 0
Require ($relativeResult.root_ledger[0].state -ceq 'UNSUPPORTED_ROOT') 'drive-relative roots must fail before enumeration'
[void][IO.Directory]::CreateDirectory((Join-Path $source 'child'))
[IO.File]::WriteAllText((Join-Path $source 'child/another.csv'),'another')
$outputCalls=[Collections.Generic.List[string]]::new()
$failedOutput={param($entry) $outputCalls.Add($entry.path);throw 'simulated output failure'}
$failedResult=Read-SFLDataInventory -Roots @([pscustomobject]@{id='output_failure';path=$source;recursive=$true}) -OnEntry $failedOutput
Require ($outputCalls.Count -eq 1) 'output failure must stop the scan rather than repeatedly write'
Require ($failedResult.output_error -ceq 'simulated output failure') 'output failure must be explicit'
Require ($failedResult.rows_emitted -eq 0) 'failed output is not an emitted row'
Require ((Convert-SFLInventoryPath 'C:\') -ceq 'C:\') 'volume roots must retain their separator'
$uncRoot=Convert-SFLInventoryPath '\\inventory-host\inventory-share\'
Require ((Convert-SFLInventoryPath $uncRoot) -ceq $uncRoot) 'normalized UNC share root must remain accepted during plain-path checks'
Require ((Convert-SFLInventoryPath '\\inventory-host\inventory-share') -ceq $uncRoot) 'UNC share root without trailing separator must be absolute'
$incompleteUncAccepted=$false
try{[void](Convert-SFLInventoryPath '\\inventory-host');$incompleteUncAccepted=$true}catch{}
Require (-not $incompleteUncAccepted) 'UNC host without a share must be rejected'
$dedupeRows=[Collections.Generic.List[object]]::new()
$dedupeCallback={param($entry) $dedupeRows.Add($entry)}
$dedupe=Read-SFLDataInventory -Roots @(
    [pscustomobject]@{id='parent';path=$source;recursive=$true},
    [pscustomobject]@{id='child';path=(Join-Path $source 'child').ToUpperInvariant();recursive=$true}
) -OnEntry $dedupeCallback
Require ($dedupe.file_count -eq 2) 'nested roots double-counted files'
Require ($dedupe.root_ledger[1].state -ceq 'COVERED_BY_PREVIOUS_RECURSIVE_ROOT') 'root overlap is not documented'
$excluded=Read-SFLDataInventory -Roots @([pscustomobject]@{id='exclude';path=$source;recursive=$true}) -ExcludedRoot (Join-Path $source 'child') -OnEntry {param($entry)}
Require ($excluded.file_count -eq 1 -and $excluded.excluded_current_bundle -eq 1) 'current result bundle must be excluded explicitly'
$budget=Read-SFLDataInventory -Roots @([pscustomobject]@{id='budget';path=$source;recursive=$true}) -OnEntry {param($entry)} -MaxSeconds 0
Require ($budget.budget_exhausted -and $budget.root_ledger[0].state -ceq 'PARTIAL_TIME_BUDGET') 'budget exhaustion is not explicit'
$security=New-SFLInventorySecurity ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
Require $security.AreAccessRulesProtected 'new result ACL must not inherit parent writes'
Require ($security.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'new result owner must be Administrators'
$rules=@($security.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier]))
Require ($rules.Count -eq 3) 'unexpected new result permissions'
$operator=@($rules|Where-Object {$_.IdentityReference.Value -ceq [Security.Principal.WindowsIdentity]::GetCurrent().User.Value})
$readRights=[Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize
Require ($operator.Count -eq 1 -and $operator[0].FileSystemRights -eq $readRights) 'operating user must have read/execute plus Windows Allow synchronize only'
$roundtripPath=Join-Path $TestRoot 'read-only-acl-fixture'
$fixtureSecurity=New-SFLInventorySecurity ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
# Non-admin fixture validates the real access-rule roundtrip, not production BA ownership.
$fixtureSecurity.SetOwner([Security.Principal.WindowsIdentity]::GetCurrent().User)
[void][IO.Directory]::CreateDirectory($roundtripPath,$fixtureSecurity)
$roundtrip=Get-Acl -LiteralPath $roundtripPath
Require (Test-SFLInventoryAccessRules $roundtrip $fixtureSecurity) 'Windows ACL canonicalization changed the actual rule contract'
$expandedAcl=New-SFLInventorySecurity ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$expandedAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Write','ContainerInherit,ObjectInherit','None','Allow'))
Require (-not (Test-SFLInventoryAccessRules $expandedAcl $fixtureSecurity)) 'unexpected Everyone write was accepted'
$jsonPath=Join-Path $TestRoot 'new-only.json'
Write-SFLNewJson $jsonPath @{value=1}
$overwritten=$false
try{Write-SFLNewJson $jsonPath @{value=2};$overwritten=$true}catch{}
Require (-not $overwritten -and (Get-Content -LiteralPath $jsonPath -Raw|ConvertFrom-Json).value -eq 1) 'new result files must not overwrite existing bytes'
$scopeFixture=[pscustomobject]@{expected_app_version='1.0.26';expected_logger_service_instance_id='expected-live-instance'}
$healthFixture=[pscustomobject]@{running=$true;mode='REAL';app_version='1.0.26';spot_temperature=[pscustomobject]@{v2_4_operational=[pscustomobject]@{logger_service_instance_id='expected-live-instance'}}}
Assert-SFLInventorySource $healthFixture $scopeFixture
$healthFixture.spot_temperature.v2_4_operational.logger_service_instance_id='different-pc-or-restart'
$wrongIdentityAccepted=$false
try{Assert-SFLInventorySource $healthFixture $scopeFixture;$wrongIdentityAccepted=$true}catch{}
Require (-not $wrongIdentityAccepted) 'wrong host/restarted logger must not be mistaken for original operating server'
Write-Output 'SELF_TEST_PASS: source/link/path/output/overlap/exclusion/budget/ACL-contract/new-file/operating-identity checks; admin folder materialization not executed'
