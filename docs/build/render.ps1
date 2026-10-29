# Render a .pptx to one PNG per slide, or a .docx to PDF, with the installed Microsoft Office (visual QA).
param([string]$In, [string]$OutDir)
$In = (Resolve-Path $In).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
if ($In -like "*.pptx") {
  $app = New-Object -ComObject PowerPoint.Application
  $p = $app.Presentations.Open($In, $true, $false, $false)
  $i = 1
  foreach ($s in $p.Slides) { $s.Export((Join-Path $OutDir ("slide-{0:d2}.png" -f $i)), "PNG", 1600, 900); $i++ }
  $p.Close(); $app.Quit()
} else {
  $app = New-Object -ComObject Word.Application
  $app.Visible = $false
  $d = $app.Documents.Open($In, $false, $false)
  foreach ($t in $d.TablesOfContents) { $t.Update() }
  $d.Fields.Update() | Out-Null
  $d.Save()
  $pdf = Join-Path $OutDir ([IO.Path]::GetFileNameWithoutExtension($In) + ".pdf")
  $d.ExportAsFixedFormat($pdf, 17)
  $d.Close($false); $app.Quit()
  Write-Output $pdf
}
