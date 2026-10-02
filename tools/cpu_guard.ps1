# Keeps logical CPU 0 free for the user while renders run: every render-related process gets affinity 0xFFFE
# (CPUs 1-15 on this 16-thread PC) and below-normal priority, re-applied every 5 s. tools/render.py already does this
# for the Blenders it starts; the guard also covers ffmpeg, bun and anything started another way.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/cpu_guard.ps1 -Minutes 118   (run in the background)
param([int]$Minutes = 115)
$mask = [IntPtr]0xFFFE
$names = @('blender', 'ffmpeg', 'bun')
$end = (Get-Date).AddMinutes($Minutes)
while ((Get-Date) -lt $end) {
  foreach ($p in Get-Process -Name $names -ErrorAction SilentlyContinue) {
    try {
      if ($p.ProcessorAffinity -ne $mask) { $p.ProcessorAffinity = $mask }
      if ($p.PriorityClass -eq 'Normal' -or $p.PriorityClass -eq 'AboveNormal') { $p.PriorityClass = 'BelowNormal' }
    } catch {}
  }
  Start-Sleep -Seconds 5
}
