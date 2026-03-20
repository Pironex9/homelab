# Factory Defect Map Import Script

**Context:** Side project at a factory job (not part of the homelab)
**Language:** PowerShell
**Problem:** Broken file copy in an industrial cutting machine's control software

## The Problem

The factory used an industrial laser cutter controlled by EuroLaser LaserScout Connect. The machine processed defect map files - CSV files describing material flaws that the cutter needs to route around.

The software had a built-in import function, but it was unreliable: it frequently failed to copy defect map files into the import directory correctly. When a file wasn't imported properly, the entire textile roll associated with it couldn't be used - it was blocked until the import succeeded. Technologists had to manually copy the file back and forth multiple times before the machine would accept it.

The machines are centrally managed and locked down - no arbitrary software can be installed. So the technologists just kept doing it by hand. I wrote a script to fix it.

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
# Configuration
$sourceDir      = "C:\Users\operator\Desktop\to be backed up"           # Source folder where defect map files are placed
$importDir      = "C:\Program Files (x86)\CutterSoftware\Import"        # Software import directory
$processedDir   = "C:\Program Files (x86)\CutterSoftware\Backup"        # Software writes results here
$logFile        = Join-Path $sourceDir "Import_log.txt"
$MaxRetry       = 10
$WaitSeconds    = 10

# Process only .csv files
Get-ChildItem -Path $sourceDir -Filter *.csv | ForEach-Object {

    $originalFile = $_.FullName
    $filename     = $_.Name
    $retry        = 0
    $success      = $false

    do {
        # Copy file into the import directory
        Copy-Item -Path $originalFile -Destination (Join-Path $importDir $filename) -Force

        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $logFile -Value "Copying: $filename (attempt: $($retry + 1)) - $timestamp"

        # Wait for the software to process the file
        Start-Sleep -Seconds $WaitSeconds

        # Check the processed output directory
        $successPath = Join-Path $processedDir $filename
        $errorPath   = Join-Path $processedDir ("csv_format_error_" + $filename)

        if (Test-Path $successPath) {
            # Successfully processed
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Successfully imported: $filename - $timestamp"
            Remove-Item -Path $originalFile -Force
            $success = $true
            break
        }
        elseif (Test-Path $errorPath) {
            # CSV format error
            Remove-Item -Path $errorPath -Force
            $retry++
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Format error, retrying: $filename - $timestamp"
        }
        else {
            # File not yet processed - unknown state
            $retry++
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            Add-Content -Path $logFile -Value "Unknown state: $filename - retrying - $timestamp"
        }

    } while ($retry -lt $MaxRetry)

    if (-Not $success) {
        # All retries exhausted - rename to _FAILED for investigation
        $failedPath = [System.IO.Path]::ChangeExtension($originalFile, "FAILED")
        Rename-Item -Path $originalFile -NewName $failedPath -Force
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $logFile -Value "Import failed, renamed: $filename -> $($Split-Path $failedPath -Leaf) - $timestamp"
    }
}
```

## Result

The script was never deployed. The same centrally managed, locked-down environment that prevented installing software also made running an unsanctioned PowerShell script a non-starter.

It remained a proof of concept - built to demonstrate that the problem was solvable and to practice scripting against a real problem I could see in front of me every day.
