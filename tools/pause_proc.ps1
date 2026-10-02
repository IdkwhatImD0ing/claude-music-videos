# Freezes or unfreezes processes in place (Windows NtSuspendProcess / NtResumeProcess): a true pause for a render
# that doesn't watch the STOP flag (for example another session's benchmark script). Nothing is lost; it continues
# from the same instruction when resumed.
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/pause_proc.ps1 -Action suspend            # every background Blender
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/pause_proc.ps1 -Action resume -Pids 30724
# Without -Pids it targets every blender.exe started with -b (background), never the user's own Blender window.
# On resume, delete the STOP flag FIRST if you set one: a resumed script that sees the flag exits instead.
param([ValidateSet('suspend', 'resume')][string]$Action = 'suspend', [int[]]$Pids)
Add-Type -Namespace W -Name Nt -MemberDefinition @'
[DllImport("ntdll.dll")] public static extern int NtSuspendProcess(IntPtr h);
[DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr h);
[DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int access, bool inherit, int pid);
[DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
'@
if (-not $Pids) {
  $Pids = Get-CimInstance Win32_Process -Filter "Name='blender.exe'" | Where-Object { $_.CommandLine -match ' -b ' } |
    ForEach-Object { [int]$_.ProcessId }
}
foreach ($id in $Pids) {
  $h = [W.Nt]::OpenProcess(0x0800, $false, $id)  # PROCESS_SUSPEND_RESUME
  if ($h -eq [IntPtr]::Zero) { "pid ${id}: can't open"; continue }
  $rc = if ($Action -eq 'suspend') { [W.Nt]::NtSuspendProcess($h) } else { [W.Nt]::NtResumeProcess($h) }
  [void][W.Nt]::CloseHandle($h)
  "{0} pid {1}: status {2}" -f $Action, $id, $rc
}
