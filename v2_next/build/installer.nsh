!include "getProcessInfo.nsh"
Var pid

!macro customCheckAppRunning
  !insertmacro _CHECK_APP_RUNNING

  DetailPrint "Removing stale packaged frontend assets..."
  RMDir /r "$INSTDIR\resources\frontend\dist"
  RMDir /r "$INSTDIR\resources\backend\frontend\dist"
!macroend
