Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$scriptPath=Join-Path $PSScriptRoot 'review-build-cache.ps1'
$parseErrors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($scriptPath,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Review helper syntax errors'}
# Import pure functions only; never run the real review or write its registry.
foreach($name in @('GetReviewDecision','HashStream','AssertRecordMapping','TimestampMatches')){
    $function=$ast.Find({param($node) $node-is[Management.Automation.Language.FunctionDefinitionAst]-and$node.Name-ceq$name},$true)
    if($null-eq$function){throw 'Missing function under test'}
    . ([scriptblock]::Create($function.Extent.Text))
}
$count=0
function AssertEqual($Actual,$Expected){if($Actual-cne$Expected){throw "Expected $Expected; received $Actual"}}
$prefix='v2_next/backend/build/SmartFactoryBackend/'
foreach($leaf in @('warn-SmartFactoryBackend.txt','xref-SmartFactoryBackend.html','Analysis-00.toc','COLLECT-00.toc','EXE-00.toc','PKG-00.toc','PYZ-00.toc')){
    AssertEqual (GetReviewDecision ($prefix+$leaf)).action 'KEEP';$count++
}
foreach($leaf in @('SmartFactoryBackend.pkg','SmartFactoryBackend.exe','PYZ-00.pyz','base_library.zip','localpycs/struct.pyc','localpycs/pyimod04_pywin32.pyc','localpycs/pyimod03_ctypes.pyc','localpycs/pyimod02_importers.pyc','localpycs/pyimod01_archive.pyc')){
    AssertEqual (GetReviewDecision ($prefix+$leaf)).action 'DELETE_CANDIDATE';$count++
}
foreach($relative in @('v2_next/backend/__pycache__/config.cpython-312.pyc','v2_next/backend/FacilityData/drivers/__pycache__/spot_api.cpython-312.pyc','v2_next/scripts/__pycache__/report.cpython-312.pyc')){
    $result=GetReviewDecision $relative
    AssertEqual $result.action 'DELETE_CANDIDATE'
    AssertEqual $result.source_relative ($relative-replace'/__pycache__/([^/]+)\.cpython-312\.pyc$','/$1.py');$count++
}
foreach($relative in @('v2_next/.mypy_cache/3.12/cache.db','v2_next/.mypy_cache/.gitignore','v2_next/.mypy_cache/CACHEDIR.TAG','v2_next/.ruff_cache/.gitignore','v2_next/.ruff_cache/CACHEDIR.TAG','v2_next/.ruff_cache/0.15.15/900808267868730199')){
    AssertEqual (GetReviewDecision $relative).reason 'TYPECHECK_OR_LINT_CACHE';$count++
}
foreach($relative in @('../v2_next/.mypy_cache/3.12/cache.db','v2_next/../.mypy_cache/3.12/cache.db','C:/v2_next/.mypy_cache/3.12/cache.db','v2_next\.mypy_cache\3.12\cache.db','v2_next/.mypy_cache/3.12/cache.db:secret','v2_next/.mypy_cache-other/cache.db','v2_next/.mypy_cache/notes.md','v2_next/backend/build/SmartFactoryBackend/private.log','v2_next/backend/dist/SmartFactoryBackend.exe','v2_next/node_modules/cache.pyc','v2_next/backend/__pycache__/source.py','v2_next/backend/__pycache__/source.cpython-311.pyc','v2_next/backend/__pycache__/source.cpython-312.pyc/extra','V2_NEXT/backend/__pycache__/source.cpython-312.pyc')){
    $rejected=$false
    try{[void](GetReviewDecision $relative)}catch{$rejected=$true}
    if(-not$rejected){throw "Unexpected allowlist expansion: $relative"};$count++
}
$buffer=[IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes('abc'))
try{
    $expected='BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD'
    AssertEqual (HashStream $buffer) $expected
    AssertEqual (HashStream $buffer) $expected
    $count+=2
}finally{$buffer.Dispose()}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.tmp\review-mapping-fixture'))
$relative='v2_next/backend/__pycache__/config.cpython-312.pyc'
$decision=GetReviewDecision $relative
$record=[pscustomobject]@{relative=$relative;file=[pscustomobject]@{path=(Join-Path $root $relative)};action=$decision.action;reason=$decision.reason;retained_source=[pscustomobject]@{path=(Join-Path $root $decision.source_relative)}}
AssertEqual (AssertRecordMapping $record $root).action 'DELETE_CANDIDATE';$count++
foreach($case in @('outside','wrong-decision','wrong-source')){
    $copy=$record|ConvertTo-Json -Depth 5|ConvertFrom-Json
    switch($case){
        'outside'{$copy.file.path=Join-Path ($root+'-other') $relative}
        'wrong-decision'{$copy.action='KEEP'}
        'wrong-source'{$copy.retained_source.path=Join-Path $root 'v2_next/backend/other.py'}
    }
    $rejected=$false;try{[void](AssertRecordMapping $copy $root)}catch{$rejected=$true}
    if(-not$rejected){throw "Mapping accepted: $case"};$count++
}
$ticks=[long]639000000000000021
AssertEqual (TimestampMatches $ticks $ticks.ToString()) $true
AssertEqual (TimestampMatches $ticks '639000000000000020') $false
AssertEqual (TimestampMatches $ticks ([long]639000000000000000)) $true
AssertEqual (TimestampMatches $ticks ([long]639000000100000000)) $false
AssertEqual (TimestampMatches $ticks $null) $false
$json=@{ticks=$ticks.ToString()}|ConvertTo-Json -Compress|ConvertFrom-Json
AssertEqual $json.ticks $ticks.ToString();$count+=6
Write-Host "[PASS] $count review cases: exact scope, source mapping, diagnostic preservation, path rejection and stable SHA256. No source or registry writes."
