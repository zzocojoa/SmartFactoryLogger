[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$InventoryPath,
    [Parameter(Mandatory=$true)][string]$ReviewCsvPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedInventory='28E8C42D1395D1240DFDB4413135A3EA40BFA01FD8BF5D4AB7ADDE4EC4A6B1AD'
if((Get-FileHash -LiteralPath $InventoryPath -Algorithm SHA256).Hash -cne $expectedInventory -or
    (Get-FileHash -LiteralPath $ReviewCsvPath -Algorithm SHA256).Hash -cne '0D8978B3B9DDEB3D9D89B0DCBB3C88C635808471D744B276053304D19D22289F'){throw 'Reviewed source binding differs.'}
$inventory=Get-Content -LiteralPath $InventoryPath -Raw -Encoding UTF8|ConvertFrom-Json
$review=@(Import-Csv -LiteralPath $ReviewCsvPath -Encoding UTF8)
$excludeIds=@(11,12,16,17,18,19,20,41,43,47,48,60,72,73,74,75,76,77,136,137,138,139,146,147,150,151,152,157,
    160,161,162,163,164,165,166,171,172,173,175,176,177,181,182,184,185,186,187,188,189,191,192,193,
    197,198,199,200,201,202,203,204,205,219,220,221,222,472,474,475,541,554)
if($excludeIds.Count -ne 70 -or @($excludeIds|Select-Object -Unique).Count -ne 70){throw 'Exclusion contract.'}
$candidates=@($review|Where-Object {$_.reviewed_classification -cin @('SINGLE_FILE_REVIEW','OTHER_HISTORICAL_REVIEW')})
if($candidates.Count -ne 436){throw 'Reviewed candidate count.'}
$ids=@{};$newExclusions=[Collections.Generic.List[object]]::new()
foreach($row in $candidates){
    $id=[int]$row.id
    if($id -in $excludeIds){
        $reason=if($id -eq 41){'Updater cache use/version not established; no same-length copy in inventory.'}
            elseif($id -eq 472){'Actual server-evidence and install results mixed with release payload.'}
            elseif($id -in @(146,147,150,151,152,157)){'Package contains source_evidence; retain whole group in this batch.'}
            else{'Historical observation/diagnostic result or sidecar; not a disposable transfer-only file.'}
        $newExclusions.Add([pscustomobject]@{id=$id;path=$row.path;reason=$reason})
    }else{$ids[$id]=$true}
}
if($newExclusions.Count -ne 70){throw 'Exclusion is not in reviewed candidates.'}
$groups=@($inventory.groups|Where-Object {$ids.ContainsKey([int]$_.id)})
$entries=@($inventory.entries|Where-Object {$ids.ContainsKey([int]$_.group)})
$files=@($entries|Where-Object type -CEQ 'file')
if($groups.Count -ne 366 -or $files.Count -ne 959 -or ($files|Measure-Object bytes -Sum).Sum -ne 5380527285L){throw 'Scope totals differ.'}
$protected=@($inventory.groups|Where-Object {-not $ids.ContainsKey([int]$_.id)}|ForEach-Object {$_.path})+@($inventory.protected_operational_paths)
$refs=@(
    [pscustomobject]@{kind='shortcut';path='C:\Users\user\Desktop';depth=2},
    [pscustomobject]@{kind='shortcut';path='C:\Users\Public\Desktop';depth=2},
    [pscustomobject]@{kind='shortcut';path='C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu';depth=6},
    [pscustomobject]@{kind='shortcut';path='C:\ProgramData\Microsoft\Windows\Start Menu';depth=6}
)
foreach($root in @('C:\Users\user\Desktop\SmartFactory','C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302',
    'C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109','C:\ProgramData\SFL-9B645BE54EB0C6C7A7F1C482248174EB',
    'C:\ProgramData\SFL-B63483AD9AB07924E5F291076F911BDA','C:\ProgramData\SFL-v1023-v11-8C1B97EF0F3BA3DAC26F38CD7B8D5656',
    'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503','C:\ProgramData\SFL26S-ae681d39b54a40c59da518292d259f95')){
    $refs += [pscustomobject]@{kind='text';path=$root;depth=8}
}
$scope=[ordered]@{schema='sfl-batch-prepare-scope-v1';input_sha256=$expectedInventory;groups=$groups;entries=$entries;
    protected_paths=$protected;new_exclusions=$newExclusions.ToArray();reference_scopes=$refs}
$utf8=[Text.UTF8Encoding]::new($false)
$scopeBytes=$utf8.GetBytes(($scope|ConvertTo-Json -Depth 12 -Compress))
function BytesHash {param([byte[]]$Bytes);$sha=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','')}finally{$sha.Dispose()}}
$memory=[IO.MemoryStream]::new();$gzip=[IO.Compression.GZipStream]::new($memory,[IO.Compression.CompressionMode]::Compress,$true)
try{$gzip.Write($scopeBytes,0,$scopeBytes.Length)}finally{$gzip.Dispose()}
try{$scopeBase64=[Convert]::ToBase64String($memory.ToArray())}finally{$memory.Dispose()}
$sourcePath=Join-Path $PSScriptRoot 'read-quarantine-pre-v1020.ps1'
$tokens=$null;$parseErrors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($sourcePath,[ref]$tokens,[ref]$parseErrors)
if(@($parseErrors).Count -ne 0){throw 'Read-only source syntax.'}
$wanted=@('Assert-QPlain','Assert-QRelative','Get-QHash','Read-QText','Get-QTree','Find-QReferences','Get-QSystemReferences','Get-QFileReferences')
$functions=[Collections.Generic.List[string]]::new()
foreach($name in $wanted){
    $matches=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq $name},$true))
    if($matches.Count -ne 1){throw ('Read-only function count: '+$name)}
    $functions.Add($matches[0].Extent.Text)
}
$code=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'prepare-cleanup-batch.template.ps1'),$utf8).
    Replace('__READ_ONLY_FUNCTIONS__',[string]::Join("`n`n",$functions.ToArray())).
    Replace('__SCOPE_GZIP__',$scopeBase64).Replace('__SCOPE_SHA__',(BytesHash $scopeBytes)).Replace('__SCOPE_LENGTH__',[string]$scopeBytes.Length)
$tokens=$null;$parseErrors=$null;$null=[Management.Automation.Language.Parser]::ParseInput($code,[ref]$tokens,[ref]$parseErrors)
if(@($parseErrors).Count -gt 0){throw ('Prepared helper syntax: '+[string]::Join('; ',@($parseErrors.Message)))}
if(Test-Path -LiteralPath $OutputDirectory){throw 'New build output directory required; do not overwrite previous preparation.'}
$null=New-Item -ItemType Directory -Path $OutputDirectory
function Emit {param([string]$Name,[byte[]]$Bytes);$s=[IO.File]::Open((Join-Path $OutputDirectory $Name),'CreateNew','Write','None');try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}}
$helperName='prepare-cleanup-batch-r1.ps1';$helperBytes=$utf8.GetBytes($code);$helperHash=BytesHash $helperBytes
Emit $helperName $helperBytes
Emit ($helperName+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($helperHash+"`n"))
Emit 'batch-scope.json' $scopeBytes
$launch=@'
& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $script='C:\ProgramData\SFLOps\inbox\prepare-cleanup-batch-r1.ps1'
    $expected='__HELPER_HASH__'
    $bytes=[IO.File]::ReadAllBytes($script)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$actual=[BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','')}finally{$sha.Dispose()}
    if($bytes.Length -ne __HELPER_LENGTH__ -or $actual -cne $expected){throw 'Helper length/hash differs. No execution.'}
    if([IO.File]::ReadAllText($script+'.sha256.txt') -cnotmatch ('\A'+$expected+'(?:\r?\n)?\z')){throw 'Sidecar differs.'}
    Write-Host '[LAUNCH] Verified batch preparation only. No deletion, move, ACL repair, app restart or installer.'
    & ([scriptblock]::Create([Text.UTF8Encoding]::new($false,$true).GetString($bytes)))
}
'@
$launch=$launch.Replace('__HELPER_HASH__',$helperHash).Replace('__HELPER_LENGTH__',[string]$helperBytes.Length)
Emit 'RUN_BATCH_PREPARATION.txt' ($utf8.GetBytes($launch))
$guide=@"
# 일괄 정리 실행안 준비

이번 파일은 **삭제 기능이 없는 서버 비교 도우미**입니다. 과거 자료를 실행하지 않습니다.

## 전송과 실행

서버의 관리자 Windows PowerShell 5.1에서 사용합니다.
전송할 파일은 prepare-cleanup-batch-r1.ps1 및 같은 이름의 .sha256.txt 두 개뿐입니다.
서버 위치: C:\ProgramData\SFLOps\inbox
inbox가 없으면 관리자 권한으로 이 자식 폴더만 생성하세요. 기존 SFLOps 권한은 변경하지 않습니다.
RUN_BATCH_PREPARATION.txt의 코드만 복사해 실행합니다. Markdown 표시나 > 문자는 복사하지 않습니다.
batch-scope.json은 개발 PC 검토용이며 서버에 옮길 필요 없습니다. 같은 내용이 도우미에 해시 결합되어 있습니다.

도우미 SHA256: $helperHash
길이: $($helperBytes.Length)bytes
입력 목록 SHA256: $expectedInventory

## 이번 비교 범위

이전 검토436묶음 중 관측/실행 증거62묶음, source_evidence 포함6묶음, v1.0.22 혼재1묶음,
현재 사용이 미확정인 updater1묶음 등 총70묶음을 더 제외했습니다.
대상은366묶음/959파일, 논리적5,380,527,285bytes입니다. 이는 삭제량이 아닙니다.
기존 보존132묶음과 추가 제외70묶음, 운영 설치/설정/데이터는 삭제 후보가 아닙니다.
참조 검사는 보호된 과거 helper/증거의 작은 텍스트도 읽지만 원문을 출력하지 않습니다.

## 한 번의 실행 흐름

1. 기존 SFLOps/inventory 권한과 내장 목록을 확인합니다. 권한이 다르면 자동 복구하지 않습니다.
2. 후보의 현재 경로·타입·크기·수정 시각을 확인하고 일치한 파일만 SHA256 비교합니다.
3. ZIP 이름이 아니라 모든 대응 파일의 정확한 상대경로·길이·해시를 비교합니다. 압축을 풀지 않습니다.
4. 프로세스·서비스·시작 항목·예약 작업·바로가기·한정된 보존 텍스트의 참조 단서를 수집합니다.
5. 결과를 SFLOps\inventory\batch-plan-<id>\batch-plan.json 및 .sha256.txt에 저장합니다.

마지막 YES 질문은 없습니다. 결과 두 파일만 개발 PC에 전달하면 됩니다. 별도 ZIP 생성도 없습니다.
개별 항목 변경/접근 오류는 보존 이유로 기록하고 다른 항목을 계속합니다.
호스트·내장 목록·출력 경계 오류는 중단합니다. 자동 재시도/정리/설치/롤백은 하지 않습니다.

## 비용과 한계

최초 해시 약5.01GiB 외에 ZIP 재검증과 실제 매칭 항목의 압축 해제 스트림 읽기가 발생합니다.
디스크에 따라 몇 분 이상 걸릴 수 있으며, 파일 해시 단계20분/ZIP 단계총25분의 단계 예산이 있습니다.
개별 OS/COM 호출은 강제 취소하지 못합니다. 장시간 원본 잠금 대신 파일별 읽기 잠금이므로
전체 파일 간 원자적 스냅샷이 아니고 미래 삭제 시점 무변경을 보장하지 않습니다.
참조 조회는 한정된 범위의 단서입니다. 빈 결과도 미사용 증명이 아니며 누락은 보고서에 남습니다.
주 스트림 바이트 일치는 ACL/ADS/하드링크/빈 디렉터리 등 전체 메타데이터 복구를 보장하지 않습니다.
이 보고서로 바로 삭제할 수 없으며 최종 승인 대상과 삭제 직전 검증이 별도로 필요합니다.

## 운영 영향

제품 변경·재시작·API 요청·관측·삭제·이동·기존 ACL 변경 없음. 디스크 읽기 부하는 발생합니다.
변경점은 새 결과 폴더뿐이므로 제품 롤백이나 데이터 마이그레이션은 필요하지 않습니다.
관측성: 기존 오류/감사/정리 기록은 보존합니다. 실패 시 부분 출력도 보존합니다.
서버 실행·실제 전체 참조 검증은 아직 하지 않았습니다. 개발 PC의 동일 이름 서버 경로는 열지 않았습니다.
원본 경로/메타데이터가 포함된 사내 전용 자료입니다. 공개하지 마세요.
"@
Emit 'BATCH_PREPARATION_GUIDE.md' ($utf8.GetBytes($guide))
Emit 'build-receipt.json' ($utf8.GetBytes(([ordered]@{result='OFFLINE_BATCH_PREPARATION_BUILT_NOT_SERVER_RUN';helper=$helperName;
    sha256=$helperHash;length=$helperBytes.Length;scope_sha256=(BytesHash $scopeBytes);groups=366;files=959;logical_bytes=5380527285L;
    added_exclusions=70;deletion_authorized=$false;server_run=$false}|ConvertTo-Json)))
Write-Output ([pscustomobject]@{output=$OutputDirectory;helper_sha256=$helperHash;helper_length=$helperBytes.Length;groups=366;files=959;server_run=$false})
