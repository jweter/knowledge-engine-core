param(
    [string]$Database = "work\corpus-recovery\knowledge-engine.sqlite",
    [string]$TargetDir = "papers\corpora\glp1_weight_loss",
    [string]$Receipts = "work\corpus-recovery\reacquisition_receipts.jsonl",
    [int]$Limit = 0,
    [int]$StartId = 0,
    [switch]$DryRun,
    [switch]$ReplaceMismatch,
    [double]$RequestDelay = 0.4
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {
    throw "Recovery database not found: $Database"
}

if (-not (Test-Path -LiteralPath "tools\reacquire_corpus_pdfs.py" -PathType Leaf)) {
    throw "tools\reacquire_corpus_pdfs.py is missing. Run this script from the repository root on the corpus-recovery branch."
}

$arguments = @(
    "tools/reacquire_corpus_pdfs.py",
    "--database", $Database,
    "--target-dir", $TargetDir,
    "--receipts", $Receipts,
    "--start-id", $StartId,
    "--request-delay", $RequestDelay
)

if ($Limit -gt 0) {
    $arguments += @("--limit", $Limit)
}
if ($DryRun) {
    $arguments += "--dry-run"
}
if ($ReplaceMismatch) {
    $arguments += "--replace-mismatch"
}

Write-Host "Knowledge Engine corpus PDF reacquisition"
Write-Host "Database : $Database"
Write-Host "Target   : $TargetDir"
Write-Host "Receipts : $Receipts"
if ($Limit -gt 0) {
    Write-Host "Limit    : $Limit"
}
if ($DryRun) {
    Write-Host "Mode     : dry run (resolve only)"
} else {
    Write-Host "Mode     : reacquire missing OA PDFs"
}
Write-Host ""

& python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Corpus reacquisition exited with code $LASTEXITCODE"
}
