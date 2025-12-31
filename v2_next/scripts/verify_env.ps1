# Check for WebView2 Runtime
$webview2 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue

Write-Host "=== V2 Environment Verification ==="
Write-Host "1. WebView2 Runtime Check"
if ($webview2) {
    Write-Host "   [OK] WebView2 Runtime found (Version: $($webview2.pv))" -ForegroundColor Green
} else {
    Write-Host "   [WARNING] WebView2 Runtime NOT found. It may be required depending on the wrapper." -ForegroundColor Yellow
}

# Check Node.js and Python
Write-Host "`n2. Development Tools Check"
try {
    $nodeVer = node -v
    Write-Host "   [OK] Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "   [ERR] Node.js not found" -ForegroundColor Red
}

try {
    $pyVer = python --version
    Write-Host "   [OK] $pyVer" -ForegroundColor Green
} catch {
    Write-Host "   [ERR] Python not found" -ForegroundColor Red
}

Write-Host "`n=== Verification Complete ==="
