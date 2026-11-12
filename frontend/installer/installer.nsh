; SIMBA's additions to electron-builder's NSIS installer (2026-11-13).
;
; electron-builder's own check, when SIMBA is open during an install or an
; uninstall, stops every process running from the install folder - by
; `taskkill /IM` or a matched Stop-Process. CLAUDE.md allows no kill by name or
; pattern, from anything in this repository. This replaces it: the installer
; only looks, and asks the person to close SIMBA themselves. Closing the window
; is enough - the host stops its own backend by PID on the way out
; (frontend/electron/backend.ts).

!macro customCheckAppRunning
  ${Do}
    ; Exit code 0: something is running from the install folder.
    nsExec::Exec `"$PowerShellPath" -NoProfile -NonInteractive -C "if ((Get-CimInstance -ClassName Win32_Process | ? {$$_.Path -and $$_.Path.StartsWith('$INSTDIR', 'CurrentCultureIgnoreCase')}).Count -gt 0) { exit 0 } else { exit 1 }"`
    Pop $R0
    ${If} $R0 != 0
      ${Break}
    ${EndIf}
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "SIMBA is still open.$\r$\n$\r$\nClose the SIMBA window, then press Retry." /SD IDCANCEL IDRETRY +2
    Quit
  ${Loop}
!macroend
