[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

function Invoke-Speak {
    param([string]$Text)
    & "$PSScriptRoot\speak.ps1" -Text $Text
}

$uiProcess = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*ui_qt.py*" }
if (-not $uiProcess) {
    Write-Host "Initializing Holographic UI..." -ForegroundColor Cyan
    Start-Process py -ArgumentList "-3.12", "`"$PSScriptRoot\ui_qt.py`"" -WindowStyle Hidden
}

Write-Host "Jarvis Central System is online." -ForegroundColor Cyan
Invoke-Speak "ระบบจาร์วิสส่วนกลาง พร้อมรับใช้บอสแล้วครับ"

while ($true) {
    "AWAITING" | Out-File "$PSScriptRoot\state.txt" -Encoding utf8
    Write-Host "Ready! Say 'Jarvis' to wake me up..." -ForegroundColor Gray
    
    $voiceOutput = py -3.12 "$PSScriptRoot\listen.py"
    $voiceOutputStr = $voiceOutput -join "`n"
    
    if ($voiceOutputStr -and ($voiceOutputStr -match "RESULT:(.*)")) {
        $recognizedText = $matches[1].Trim()
        if ($recognizedText -eq "NONE" -or $recognizedText -eq "") { continue }
        
        Write-Host "Boss: $recognizedText" -ForegroundColor Green
        if ($recognizedText -match "^(เลิกงาน|บ๊ายบาย|ปิดระบบ|หยุดทำงาน)$") {
            Invoke-Speak "รับทราบครับบอส พักผ่อนให้เต็มที่นะครับ"
            break
        }
        
        "THINKING" | Out-File "$PSScriptRoot\state.txt" -Encoding utf8
        Write-Host "Jarvis is thinking..." -ForegroundColor Yellow
        $aiResponse = py -3.12 "$PSScriptRoot\brain.py" $recognizedText 2>$null
        $aiResponseStr = $aiResponse -join "`n"
        
        if ($aiResponseStr) {
            Write-Host "Jarvis: $aiResponseStr" -ForegroundColor Cyan
            Invoke-Speak $aiResponseStr
        } else {
            Invoke-Speak "ขออภัยครับบอส สมองส่วนกลางไม่ตอบสนองครับ"
        }
    }
}
