# send-metrics.ps1
# v3.0
# 28-I-2026

 $vm_id = "VM-303-15"         # Уникальный ID ВМ
 $vm_profile = "Cyber+Tower"  # Уникальный profile ВМ
 $vm_threads = "3"            # Сколько потоков может тащить ВМ
 $vm_bas_version = "28.8.1"   # Версия ПО, установленного на ВМ
 $vm_project_version = "7.3"  # Версия проекта, который выполняется на ВМ
 $server_ip = "47.82.5.187"
 $api_endpoint = "http://$server_ip`:8080/metrics"

Write-Host "`n[+] Сбор метрик для ВМ:" -ForegroundColor Cyan
Write-Host "    ID:      $vm_id" -ForegroundColor White
Write-Host "    Profile: $vm_profile" -ForegroundColor White
Write-Host "    Threads: $vm_threads" -ForegroundColor Gray
Write-Host "    BAS Version: $vm_bas_version" -ForegroundColor Gray
Write-Host "    Project Version: $vm_project_version" -ForegroundColor Gray

# 1. Сбор метрик
try {
    $cpu = (Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    if ($null -eq $cpu) { $cpu = 0 }
    $diskObj = Get-WmiObject Win32_LogicalDisk -Filter "DeviceID='C:'"
    $disk_free = if ($diskObj) { $diskObj.FreeSpace } else { 0 }

# Проверка, запущен ли процесс BAS и активны ли его дочерние процессы Chromium
 $basProc = Get-Process -Name "BrowserAutomationStudio" -ErrorAction SilentlyContinue
if ($basProc) {
    $basId = $basProc.Id
    # Изменение: используем LIKE для поиска процессов, начинающихся с "Chromium"
    $childChromiums = Get-CimInstance Win32_Process -Filter "ParentProcessId = $basId AND Name LIKE 'Chromium%'"
    $bas_running = $childChromiums.Count -gt 0
    $bas_title = if ($bas_running) {
        "BAS working with $($childChromiums.Count) Chromium processes"
    } else {
        "BAS running (idle or in tray)"
    }
} else {
    $bas_running = $false
    $bas_title = "BAS not running :("
}

    # Проверка соответствия заявленного количества потоков реальному
    $real_threads = if ($bas_running) { $childChromiums.Count } else { 0 }
    if ([int]$vm_threads -ne $real_threads) {
        Write-Host "[!] ВНИМАНИЕ: Заявленное количество потоков ($vm_threads) не совпадает с реальным ($real_threads)!" -ForegroundColor Yellow
    }

    # Красивый вывод основных метрик
    Write-Host "`n[✓] Основные метрики:" -ForegroundColor Green
    Write-Host "    CPU Load:     $cpu%" -ForegroundColor Yellow
    Write-Host "    Disk Free:    $([math]::Round($disk_free / 1GB, 2)) GB" -ForegroundColor Gray
    Write-Host "    BAS Running:  $bas_running" -ForegroundColor $(if ($bas_running) { "Green" } else { "Red" })
    if ($bas_running) {
        Write-Host "    Window Title: '$bas_title'" -ForegroundColor Gray
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
        Write-Host "`n[✓] Успешных прогонов в логе: $($success_events.Count)" -ForegroundColor Green
    } catch {
        Write-Host "[-] Ошибка при чтении лога: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[ ] Лог-файл не найден: $log_path" -ForegroundColor Gray
}

# 3. Формирование JSON (всё равно нужно для отправки)
try {
    $bodyObj = @{
        vm_id        = $vm_id
        vm_profile   = $vm_profile
        vm_threads   = $vm_threads
        vm_bas_version = $vm_bas_version
        vm_project_version = $vm_project_version
        timestamp    = Get-Date -Format "o"
        cpu          = $cpu
        disk_free    = $disk_free
        bas_running  = $bas_running
        bas_title    = $bas_title
        success_events = $success_events
    }
    $body = $bodyObj | ConvertTo-Json -Depth 3 -Compress
} catch {
    Write-Host "[-] Ошибка при создании JSON: $($_.Exception.Message)" -ForegroundColor Red
    Start-Sleep -Seconds 15
    exit 1
}

# 4. Отправка на сервер
 $response = $null  # важно инициализировать, иначе может быть undefined в finally
try {
    Write-Host "`n[→] Отправка данных на $api_endpoint..." -ForegroundColor Cyan
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
        Write-Host "[✓] Ответ от сервера получен." -ForegroundColor Green
        if ($response | Get-Member -Name status -MemberType NoteProperty) {
            Write-Host "    Статус: $($response.status)" -ForegroundColor Gray
        } else {
            Write-Host "    Ответ: $($response | ConvertTo-Json -Depth 2)" -ForegroundColor Gray
        }
    }
}

# 5. Финальное прощание
Write-Host "`n[=] Скрипт завершён.`n" -ForegroundColor Magenta
Start-Sleep -Seconds 1