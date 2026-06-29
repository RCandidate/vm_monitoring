# send-metrics.ps1
# ver. 4.6
# 29-V-2026

# 🔝 В начало скрипта
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Требуются права администратора. Перезапуск..." -ForegroundColor Yellow
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}


$vm_id              = "VM-209-01"       
$vm_profile         = "TowerDE"      
$vm_threads         = "6"          
$vm_bas_version     = "29.3.1"       
$vm_project_version = "7.3"      


$server_ip = "47.82.5.187"
$api_endpoint = "http://$server_ip`:8080/metrics"


Write-Host "`n[=] Сбор метрик: ver. 4.6" -ForegroundColor Magenta
Write-Host "`n[+] Сбор метрик для ВМ:" -ForegroundColor Cyan
Write-Host "    ID:      $vm_id" -ForegroundColor White
Write-Host "    Profile: $vm_profile" -ForegroundColor White
Write-Host "    Threads: $vm_threads" -ForegroundColor Gray
Write-Host "    BAS Version: $vm_bas_version" -ForegroundColor Gray
Write-Host "    Project Version: $vm_project_version" -ForegroundColor Gray

# 1. Сбор метрик
try {
    $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    if ($null -eq $cpu) { $cpu = 0 }
    
    $diskObj = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    $disk_free = if ($diskObj) { $diskObj.FreeSpace } else { 0 }

    # Расчет uptime
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $uptime_seconds = [math]::Round(((Get-Date) - $osInfo.LastBootUpTime).TotalSeconds)

    # 🔍 ПРОВЕРКА BAS - ИСПРАВЛЕННАЯ ВЕРСИЯ
    Write-Host "`n[🔍] Проверка состояния BAS..." -ForegroundColor Cyan
    
    $basProc = Get-Process -Name "BrowserAutomationStudio" -ErrorAction SilentlyContinue
    
    if ($basProc) {
        Write-Host "  ✓ BAS найден (PID: $($basProc.Id))" -ForegroundColor Green
        
        # Ищем ВСЕ Chromium процессы (не только дочерние!)
        $allChromiums = Get-Process | Where-Object { 
            $_.ProcessName -match "^(chromium|chrome)$" 
        }
        
        # BAS использует Worker.exe для потоков
        $workerProcs = Get-Process -Name "worker" -ErrorAction SilentlyContinue
        
        $real_threads = @($allChromiums).Count
        $bas_running = $true
        
        Write-Host "  → Chromium процессов: $real_threads" -ForegroundColor Gray
        Write-Host "  → Worker процессов: $(@($workerProcs).Count)" -ForegroundColor Gray
        
        $bas_title = if ($real_threads -gt 0) {
            "BAS working with $real_threads Chromium instances"
        } else {
            "BAS running (idle)"
        }
        
    } else {
        Write-Host "  ✗ BAS НЕ найден!" -ForegroundColor Red
        $bas_running = $false
        $bas_title = "BAS not running :("
        $real_threads = 0
    }

    # Предупреждение о несоответствии потоков
    if ([int]$vm_threads -ne $real_threads) {
        Write-Host "`n[!] ВНИМАНИЕ: Заявлено потоков: $vm_threads, реально: $real_threads" -ForegroundColor Yellow
    }

    # Вывод метрик
    Write-Host "`n[@] Основные метрики:" -ForegroundColor Green
    Write-Host "    CPU Load:     $cpu%" -ForegroundColor Yellow
    Write-Host "    Disk Free:    $([math]::Round($disk_free / 1GB, 2)) GB" -ForegroundColor Gray
    Write-Host "    Uptime:       $([math]::Round($uptime_seconds/3600, 1)) ч" -ForegroundColor Cyan
    Write-Host "    BAS Running:  $bas_running" -ForegroundColor $(if ($bas_running) { "Green" } else { "Red" })
    Write-Host "    Status:       $bas_title" -ForegroundColor Gray
    if ($bas_running) {
        Write-Host "    Real Threads: $real_threads" -ForegroundColor Gray
    }
} catch {
    Write-Host "[-] Ошибка при сборе метрик: $($_.Exception.Message)" -ForegroundColor Red
    Start-Sleep -Seconds 15
    exit 1
}


# 2. Анализ логов BAS
$log_path = "C:\tmp\success.log"
$success_events = @()
if (Test-Path $log_path) {
    try {
        $lines = Get-Content $log_path -ErrorAction Stop | Select-Object -Last 100
        $matched = $lines | Where-Object { $_ -match "ПРОГОН ЗАКОНЧЕН!!!" }
        $success_events = foreach ($line in $matched) {
            @{
                timestamp = Get-Date -Format "o"
                message   = $line
            }
        }
        Write-Host "`n[*] Успешных прогонов в логе: $($success_events.Count)" -ForegroundColor Green
    } catch {
        Write-Host "[-] Ошибка при чтении лога: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[ ] Лог-файл не найден: $log_path" -ForegroundColor Gray
}

# 3. Формирование JSON
try {
    $bodyObj = @{
        vm_id            = $vm_id
        vm_profile       = $vm_profile
        vm_threads       = $vm_threads
        vm_bas_version   = $vm_bas_version
        vm_project_version = $vm_project_version
        timestamp        = Get-Date -Format "o"
        cpu              = $cpu
        disk_free        = $disk_free
        uptime_seconds   = $uptime_seconds  # 🆕
        bas_running      = $bas_running
        bas_title        = $bas_title
        success_events   = $success_events
    }
    $body = $bodyObj | ConvertTo-Json -Depth 3 -Compress
} catch {
    Write-Host "[-] Ошибка при создании JSON: $($_.Exception.Message)" -ForegroundColor Red
    Start-Sleep -Seconds 15
    exit 1
}

# 4. Отправка на сервер
$response = $null
try {
    Write-Host "`n[^] Отправка данных на $api_endpoint..." -ForegroundColor Cyan
    $response = Invoke-RestMethod -Uri $api_endpoint -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
} catch {
    $errorMessage = $_.Exception.Message
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "[-] HTTP ошибка ${statusCode}: $errorMessage" -ForegroundColor Red
    } else {
        Write-Host "[-] Ошибка подключения: $errorMessage" -ForegroundColor Red
    }
} finally {
    if ($response) {
        Write-Host "[*] Ответ от сервера получен." -ForegroundColor Green
        if ($response | Get-Member -Name status -MemberType NoteProperty) {
            Write-Host "    Статус: $($response.status)" -ForegroundColor Gray
        } else {
            Write-Host "    Ответ: $($response | ConvertTo-Json -Depth 2)" -ForegroundColor Gray
        }
    }
}

Write-Host "`n[=] Скрипт почти завершён....`n" -ForegroundColor Magenta
Start-Sleep -Seconds 1



# ----------------------------------


# $folder = "C:\Program Files\BrowserAutomationStudio\apps\29.3.1\prof"
# ✅ Стало изящно
$folder = "C:\Program Files\BrowserAutomationStudio\apps\$vm_bas_version\prof"

#Write-Host "Очистка папки: $folder" -ForegroundColor Yellow
#Remove-Item $folder -Recurse -Force -ErrorAction SilentlyContinue
#Write-Host "Создание папки заново..." -ForegroundColor Yellow
#New-Item -ItemType Directory -Path $folder -Force | Out-Null

# ✅ Очищаем только содержимое, папка остаётся

Write-Host "Очистка содержимого: $folder" -ForegroundColor Yellow
Get-ChildItem -Path $folder -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Готово!" -ForegroundColor Green
Write-Host "`n[=] Скрипт ПОЛНОСТЬЮ завершён....`n" -ForegroundColor Magenta

Start-Sleep -Seconds 5
Start-Sleep -Seconds 1