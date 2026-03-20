# Factory Defect Map Import Script

**Context:** Side project at a factory job (not part of the homelab)
**Language:** PowerShell
**Problem:** Broken file copy in an industrial cutting machine's control software

## The Problem

The factory used an industrial laser cutter controlled by EuroLaser LaserScout Connect. The machine processed defect map files - CSV files describing material flaws that the cutter needs to route around.

The software had a built-in import function, but it was unreliable: it would silently fail to copy files into the import directory, or copy them in a broken state, causing the machine to skip the defect map entirely and cut through flawed material.

Nobody investigated it. The operators worked around it manually - re-copying files by hand, re-running imports, hoping it worked. I wrote a script to fix it.

## What the Script Does

1. Scans a watched source folder for `.csv` defect map files
2. Copies each file into the software's import directory
3. Waits for the software to process it (polls the processed/error output directories)
4. On success: removes the original source file, logs the result
5. On CSV format error: logs the specific error, moves on
6. On unknown state: retries up to 10 times with a 10-second wait between attempts
7. On final failure: renames the file with a `_FAILED` suffix (preserves it for investigation) and logs it

All results are written to a timestamped log file.

## The Script

```powershell
# Beállítások
$sourceDir      = "C:\Users\operator\Desktop\to be backed up"           # A mappa, ahonnan a fájlokat vesszük
$importDir      = "C:\Program Files (x86)\CutterSoftware\Import"        # Ide másoljuk be a fájlokat importáláshoz
$processedDir   = "C:\Program Files (x86)\CutterSoftware\Backup"        # A program ide menti az eredményt
$logFile        = Join-Path $sourceDir "Import_log.txt"
$MaxRetry       = 10
$WaitSeconds    = 10

# Csak .csv fájlok feldolgozása
Get-ChildItem -Path $sourceDir -Filter *.csv | ForEach-Object {

    $originalFile = $_.FullName
    $filename     = $_.Name
    $retry        = 0
    $success      = $false

    do {
        # Másolás az import mappába
        Copy-Item -Path $originalFile -Destination (Join-Path $importDir $filename) -Force

        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $logFile -Value "Másolás: $filename (próbálkozás: $($retry + 1)) - $timestamp"

        # Várjuk, hogy a program feldolgozza
        Start-Sleep -Seconds $WaitSeconds

        # Ellenőrzés a feldolgozott mappában
        $successPath = Join-Path $processedDir $filename
        $errorPath   = Join-Path $processedDir ("csv_format_error_" + $filename)

        if (Test-Path $successPath) {
            # Sikeres feldolgozás
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Sikeresen importálva: $filename - $timestamp"
            Remove-Item -Path $originalFile -Force
            $success = $true
            break
        }
        elseif (Test-Path $errorPath) {
            # Hibás feldolgozás
            Remove-Item -Path $errorPath -Force
            $retry++
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Hiba történt: újrapróbálás ($filename) - $timestamp"
        }
        else {
            # Fájl nincs feldolgozva
            $retry++
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Ismeretlen állapot: $filename - újrapróbálás - $timestamp"
        }

    } while ($retry -lt $MaxRetry)

    if (-Not $success) {
        # 5 próbálkozás után sem sikerült: _FAILED-re nevezzük
        $failedPath = [System.IO.Path]::ChangeExtension($originalFile, "FAILED")
        Rename-Item -Path $originalFile -NewName $failedPath -Force
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $logFile -Value "Sikertelen import, átnevezve: $filename → $($Split-Path $failedPath -Leaf) - $timestamp"
    }
}
```

## Result

The script ran via Windows Task Scheduler. Operators dropped defect map files into the watched folder and the import happened automatically without manual intervention. Failed imports were flagged with `_FAILED` and logged, making them visible instead of silently skipped.

Nobody asked for this. I built it because the workaround was slowing people down and the root cause was fixable.
