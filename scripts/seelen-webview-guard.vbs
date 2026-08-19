' Launcher for seelen-webview-guard.ps1 that produces no visible window.
'
' Running powershell.exe directly from Task Scheduler flashes a console window
' every time the task fires, even with -WindowStyle Hidden: the console host is
' created before PowerShell parses its own parameters, so the window exists for
' a few hundred milliseconds regardless. On a 5-minute schedule that is a blink
' on the desktop twelve times an hour, and it can steal focus.
'
' wscript.exe has no console of its own, and Run(cmd, 0, True) starts the child
' with SW_HIDE and waits for it, so the task's runtime still reflects the real
' work and the task's execution time limit still applies.

Dim shell, cmd
Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden " & _
      "-ExecutionPolicy Bypass -File ""C:\Users\Nex\seelen-webview-guard.ps1"""
shell.Run cmd, 0, True
