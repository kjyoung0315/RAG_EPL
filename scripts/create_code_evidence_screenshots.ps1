Add-Type -AssemblyName System.Drawing

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $projectRoot "evidence_screenshots"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

function Save-CodeScreenshot {
    param(
        [string]$SourceFile,
        [int]$StartLine,
        [int]$EndLine,
        [string]$OutputName,
        [string]$Caption
    )

    $allLines = Get-Content -LiteralPath (Join-Path $projectRoot $SourceFile) -Encoding UTF8
    $selected = @($allLines[($StartLine - 1)..($EndLine - 1)])
    $width = 1800
    $lineHeight = 31
    $height = 150 + ($selected.Count * $lineHeight)
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $graphics.Clear([System.Drawing.Color]::FromArgb(246, 248, 250))

    $headerBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(31, 41, 55))
    $captionBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(75, 85, 99))
    $lineNumberBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(148, 163, 184))
    $codeBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(17, 24, 39))
    $codeBackBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $headerFont = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
    $captionFont = New-Object System.Drawing.Font("Segoe UI", 13)
    $codeFont = New-Object System.Drawing.Font("Cascadia Mono", 16)

    $graphics.FillRectangle($codeBackBrush, 34, 102, $width - 68, $height - 136)
    $graphics.DrawString($Caption, $headerFont, $headerBrush, 36, 25)
    $graphics.DrawString("$SourceFile  |  lines $StartLine-$EndLine", $captionFont, $captionBrush, 38, 68)

    for ($index = 0; $index -lt $selected.Count; $index++) {
        $y = 115 + ($index * $lineHeight)
        $lineNumber = "{0,4}" -f ($StartLine + $index)
        $graphics.DrawString($lineNumber, $codeFont, $lineNumberBrush, 55, $y)
        $graphics.DrawString($selected[$index], $codeFont, $codeBrush, 145, $y)
    }

    $bitmap.Save((Join-Path $outputDir $OutputName), [System.Drawing.Imaging.ImageFormat]::Png)
    $codeFont.Dispose(); $captionFont.Dispose(); $headerFont.Dispose()
    $codeBrush.Dispose(); $lineNumberBrush.Dispose(); $captionBrush.Dispose(); $headerBrush.Dispose(); $codeBackBrush.Dispose()
    $graphics.Dispose(); $bitmap.Dispose()
}

Save-CodeScreenshot "src/collector.py" 287 315 "05_F2005_chunking_code.png" "F2005 - External document chunking and indexing"
Save-CodeScreenshot "src/retriever.py" 11 25 "06_F2006_topk_code.png" "F2006 - Top-K similarity search from settings"
Save-CodeScreenshot "src/config.py" 56 69 "06_F2006_topk_setting_code.png" "F2006 - RETRIEVAL_TOP_K environment setting"
