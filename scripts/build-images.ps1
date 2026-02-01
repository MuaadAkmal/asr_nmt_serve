# Build script for ASR-NMT Docker images (PowerShell)

param(
    [string]$Registry = "your-registry",
    [string]$Tag = "latest",
    [switch]$Push
)

Write-Host "Building ASR-NMT images..." -ForegroundColor Green
Write-Host "Registry: $Registry"
Write-Host "Tag: $Tag"

# Build CPU image (for API and CPU workers)
Write-Host ""
Write-Host "=== Building CPU image ===" -ForegroundColor Yellow
docker build `
    --target base `
    -t "${Registry}/asr-nmt-serve:${Tag}" `
    -t "${Registry}/asr-nmt-serve:cpu-${Tag}" `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build CPU image" -ForegroundColor Red
    exit 1
}

# Build GPU image (for GPU workers)
Write-Host ""
Write-Host "=== Building GPU image ===" -ForegroundColor Yellow
docker build `
    --target gpu `
    -t "${Registry}/asr-nmt-serve:gpu-${Tag}" `
    .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build GPU image" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Images built successfully ===" -ForegroundColor Green
Write-Host "CPU image: ${Registry}/asr-nmt-serve:${Tag}"
Write-Host "GPU image: ${Registry}/asr-nmt-serve:gpu-${Tag}"

# Push if requested
if ($Push) {
    Write-Host ""
    Write-Host "=== Pushing images ===" -ForegroundColor Yellow
    docker push "${Registry}/asr-nmt-serve:${Tag}"
    docker push "${Registry}/asr-nmt-serve:cpu-${Tag}"
    docker push "${Registry}/asr-nmt-serve:gpu-${Tag}"
    Write-Host "Images pushed successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "To push images manually:"
Write-Host "  docker push ${Registry}/asr-nmt-serve:${Tag}"
Write-Host "  docker push ${Registry}/asr-nmt-serve:gpu-${Tag}"
