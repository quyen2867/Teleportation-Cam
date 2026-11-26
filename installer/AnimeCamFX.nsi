Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!ifndef PAYLOAD
  !error "PAYLOAD is required"
!endif
!ifndef SOURCE_EXE
  !error "SOURCE_EXE is required"
!endif
!ifndef OUTPUT
  !error "OUTPUT is required"
!endif
!ifndef APP_VERSION
  !define APP_VERSION "0.4.0"
!endif

Name "AnimeCam FX"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\AnimeCamFX"
InstallDirRegKey HKCU "Software\AnimeCamFX\Installer" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 16
BrandingText "AnimeCam FX • Hiệu ứng webcam trên máy"
Icon "${PAYLOAD}\_internal\assets\animecam.ico"
UninstallIcon "${PAYLOAD}\_internal\assets\animecam.ico"
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=1066 "ProductName" "AnimeCam FX"
VIAddVersionKey /LANG=1066 "FileDescription" "Bộ cài AnimeCam FX"
VIAddVersionKey /LANG=1066 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1066 "LegalCopyright" "AnimeCam FX project"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Cài đặt AnimeCam FX"
!define MUI_WELCOMEPAGE_TEXT "Vui lòng đóng AnimeCam FX trước khi cài đặt.$\r$\n$\r$\nỨng dụng chỉ bật camera khi bạn yêu cầu."
!define MUI_FINISHPAGE_RUN "$INSTDIR\AnimeCamFX.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Mở AnimeCam FX"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE ValidateInstallDirectory
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Vietnamese"

Function .onInit
  SetShellVarContext current
  SetRegView 64
FunctionEnd

Function ValidateInstallDirectory
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "AnimeCamFX"
    MessageBox MB_OK|MB_ICONSTOP "Thư mục cài đặt phải có tên cuối là AnimeCamFX, ví dụ C:\Users\ban\AppData\Local\Programs\AnimeCamFX." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
FunctionEnd

Section "Ứng dụng và biểu tượng Start Menu" SEC_APP
  SectionIn RO
  Call ValidateInstallDirectory
  ; Refuse to upgrade a running app before modifying its installed files.
  IfFileExists "$INSTDIR\AnimeCamFX.exe" 0 app_not_running
  ClearErrors
  FileOpen $0 "$INSTDIR\AnimeCamFX.exe" a
  IfErrors app_busy
  FileClose $0
  Goto app_not_running
  app_busy:
    MessageBox MB_OK|MB_ICONSTOP "Hãy thoát AnimeCam FX trước khi cập nhật." /SD IDOK
    SetErrorLevel 2
    Quit
  app_not_running:
  ; Remove only the known documentation and shortcut files from earlier versions.
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\docs\VALIDATION.md"
  RMDir "$INSTDIR\docs"
  Delete "$DESKTOP\AnimeCam FX - Google Meet.lnk"
  Delete "$DESKTOP\AnimeCam FX - Zoom.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\Google Meet cùng AnimeCam.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\Zoom cùng AnimeCam.lnk"
  ; Replace the owned runtime to avoid stale dependencies from older releases.
  IfFileExists "$INSTDIR\animecam-install.id" 0 copy_payload
  FileOpen $0 "$INSTDIR\animecam-install.id" r
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "AnimeCamFX-owned-install-v1$\r$\n" 0 copy_payload
  RMDir /r "$INSTDIR\_internal"
  copy_payload:
  SetOutPath "$INSTDIR"
  File /oname=AnimeCamFX.exe "${PAYLOAD}\${SOURCE_EXE}"
  SetOutPath "$INSTDIR\_internal"
  File /r "${PAYLOAD}\_internal\*.*"
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\animecam-install.id" w
  FileWrite $0 "AnimeCamFX-owned-install-v1$\r$\n"
  FileClose $0
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\AnimeCamFX\Installer" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "DisplayName" "AnimeCam FX"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "Publisher" "AnimeCam FX project"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "DisplayIcon" "$INSTDIR\AnimeCamFX.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\AnimeCam FX"
  CreateShortCut "$SMPROGRAMS\AnimeCam FX\AnimeCam FX.lnk" "$INSTDIR\AnimeCamFX.exe" "" "$INSTDIR\AnimeCamFX.exe"
  CreateShortCut "$SMPROGRAMS\AnimeCam FX\Gỡ cài đặt.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Biểu tượng AnimeCam FX trên Desktop" SEC_DESKTOP
  CreateShortCut "$DESKTOP\AnimeCam FX.lnk" "$INSTDIR\AnimeCamFX.exe" "" "$INSTDIR\AnimeCamFX.exe"
SectionEnd

Section /o "Khởi động cùng Windows (không bật webcam)" SEC_STARTUP
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AnimeCamFX" '$\"$INSTDIR\AnimeCamFX.exe$\" --tray'
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_APP} "Cài ứng dụng độc lập, mô hình AI, âm thanh và trình gỡ cài đặt. Không cần Python trên máy đích."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} "Bấm đúp biểu tượng để mở giao diện. Webcam chưa bật cho đến khi bạn yêu cầu."
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_STARTUP} "Chạy ứng dụng ở khay hệ thống khi đăng nhập Windows. Không tự bật webcam."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function un.onInit
  SetShellVarContext current
  SetRegView 64
  ; Before recursive removal, verify the exact registered install path and our
  ; marker. A moved uninstaller must never remove an unrelated directory.
  ReadRegStr $0 HKCU "Software\AnimeCamFX\Installer" "InstallLocation"
  ${If} $0 == ""
  ${OrIf} $0 != $INSTDIR
    MessageBox MB_ICONSTOP "Không xác minh được thư mục cài đặt. Đã dừng gỡ cài đặt."
    Abort
  ${EndIf}
  ${GetFileName} "$INSTDIR" $0
  ${If} $0 != "AnimeCamFX"
    Abort
  ${EndIf}
  ${If} $INSTDIR == $LOCALAPPDATA
  ${OrIf} $INSTDIR == $PROFILE
  ${OrIf} $INSTDIR == $WINDIR
  ${OrIf} $INSTDIR == $PROGRAMFILES
    Abort
  ${EndIf}
  ClearErrors
  FileOpen $1 "$INSTDIR\animecam-install.id" r
  IfErrors unsafe_uninstall
  FileRead $1 $2
  FileClose $1
  StrCmp $2 "AnimeCamFX-owned-install-v1$\r$\n" safe_uninstall
  unsafe_uninstall:
    MessageBox MB_ICONSTOP "Không tìm thấy dấu xác nhận thư mục AnimeCam FX. Đã dừng gỡ cài đặt."
    Abort
  safe_uninstall:
FunctionEnd

Section "Uninstall"
  ClearErrors
  Delete "$INSTDIR\AnimeCamFX.exe"
  IfErrors busy_uninstall
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "AnimeCamFX"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AnimeCamFX"
  DeleteRegKey HKCU "Software\AnimeCamFX\Installer"
  Delete "$DESKTOP\AnimeCam FX.lnk"
  Delete "$DESKTOP\AnimeCam FX - Google Meet.lnk"
  Delete "$DESKTOP\AnimeCam FX - Zoom.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\AnimeCam FX.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\Google Meet cùng AnimeCam.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\Zoom cùng AnimeCam.lnk"
  Delete "$SMPROGRAMS\AnimeCam FX\Gỡ cài đặt.lnk"
  RMDir "$SMPROGRAMS\AnimeCam FX"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\docs\VALIDATION.md"
  RMDir "$INSTDIR\docs"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\animecam-install.id"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  ; User settings and logs are deliberately retained in AppData/HKCU.
  Goto uninstall_done
  busy_uninstall:
    MessageBox MB_OK|MB_ICONSTOP "Hãy chọn Thoát trong AnimeCam FX rồi gỡ cài đặt lại. Camera và ứng dụng vẫn đang chạy." /SD IDOK
    SetErrorLevel 2
  uninstall_done:
SectionEnd
