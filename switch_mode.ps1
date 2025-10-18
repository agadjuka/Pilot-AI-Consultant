# PowerShell скрипт для переключения между режимами
# Используется для тестирования webhook'ов без базы данных

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("stub", "normal", "status")]
    [string]$Mode
)

Write-Host "🔄 Переключение режима работы приложения..." -ForegroundColor Cyan

switch ($Mode) {
    "stub" {
        Write-Host "🔧 Включаем режим заглушки (без БД)..." -ForegroundColor Yellow
        
        # Создаем резервные копии оригинальных файлов
        if (Test-Path "app/main.py") {
            Copy-Item "app/main.py" "app/main_original.py.bak"
            Write-Host "✅ Резервная копия main.py создана" -ForegroundColor Green
        }
        
        if (Test-Path "app/api/telegram.py") {
            Copy-Item "app/api/telegram.py" "app/api/telegram_original.py.bak"
            Write-Host "✅ Резервная копия telegram.py создана" -ForegroundColor Green
        }
        
        # Заменяем на версии с заглушками
        if (Test-Path "app/main_stub.py") {
            Copy-Item "app/main_stub.py" "app/main.py"
            Write-Host "✅ main.py заменен на версию с заглушками" -ForegroundColor Green
        } else {
            Write-Host "❌ Файл app/main_stub.py не найден" -ForegroundColor Red
        }
        
        if (Test-Path "app/api/telegram_stub.py") {
            Copy-Item "app/api/telegram_stub.py" "app/api/telegram.py"
            Write-Host "✅ telegram.py заменен на версию с заглушками" -ForegroundColor Green
        } else {
            Write-Host "❌ Файл app/api/telegram_stub.py не найден" -ForegroundColor Red
        }
        
        Write-Host ""
        Write-Host "✅ Режим заглушки включен!" -ForegroundColor Green
        Write-Host "📊 Webhook'и будут работать без базы данных" -ForegroundColor Cyan
        Write-Host "🎯 Сообщения будут обрабатываться заглушками" -ForegroundColor Cyan
    }
    
    "normal" {
        Write-Host "🔧 Включаем обычный режим (с БД)..." -ForegroundColor Yellow
        
        # Восстанавливаем оригинальные файлы
        if (Test-Path "app/main_original.py.bak") {
            Copy-Item "app/main_original.py.bak" "app/main.py"
            Write-Host "✅ main.py восстановлен" -ForegroundColor Green
        } else {
            Write-Host "❌ Резервная копия main.py не найдена" -ForegroundColor Red
        }
        
        if (Test-Path "app/api/telegram_original.py.bak") {
            Copy-Item "app/api/telegram_original.py.bak" "app/api/telegram.py"
            Write-Host "✅ telegram.py восстановлен" -ForegroundColor Green
        } else {
            Write-Host "❌ Резервная копия telegram.py не найдена" -ForegroundColor Red
        }
        
        Write-Host ""
        Write-Host "✅ Обычный режим включен!" -ForegroundColor Green
        Write-Host "📊 Webhook'и будут работать с базой данных" -ForegroundColor Cyan
        Write-Host "🎯 Сообщения будут обрабатываться полноценно" -ForegroundColor Cyan
    }
    
    "status" {
        Write-Host "📊 Проверка текущего режима..." -ForegroundColor Cyan
        
        if (Test-Path "app/main.py") {
            $content = Get-Content "app/main.py" -Raw
            if ($content -match "STUB") {
                Write-Host "🔧 Текущий режим: ЗАГЛУШКА (без БД)" -ForegroundColor Yellow
            } else {
                Write-Host "🔧 Текущий режим: ОБЫЧНЫЙ (с БД)" -ForegroundColor Green
            }
        } else {
            Write-Host "❌ Файл app/main.py не найден" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "💡 Использование:" -ForegroundColor Cyan
Write-Host "  .\switch_mode.ps1 stub    - включить режим заглушки (без БД)" -ForegroundColor White
Write-Host "  .\switch_mode.ps1 normal  - включить обычный режим (с БД)" -ForegroundColor White
Write-Host "  .\switch_mode.ps1 status  - проверить текущий режим" -ForegroundColor White
