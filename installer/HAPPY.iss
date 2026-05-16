; ============================================================
; HAPPY v1.032 — Inno Setup Script
; Compile: ISCC.exe HAPPY.iss
; ============================================================

#define MyAppName "HAPPY"
#define MyAppVersion "1.032"
#define MyAppPublisher "Nick SuksanTr"
#define MyAppURL "https://github.com/nicksuksantr/happy-ai-agent"
#define MyAppExeName "HAPPY.exe"
#define MyDistDir "..\dist\HAPPY"

[Setup]
; AppId — unique identifier ของ HAPPY (อย่าเปลี่ยน — ใช้ track uninstall + upgrade)
AppId={{F7E3D2A1-9B4C-4E5F-A6B7-C8D9E0F1A2B3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; ติดตั้งใน user-local — ไม่ต้อง admin
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output settings
OutputDir=output
OutputBaseFilename=HAPPY-Setup-{#MyAppVersion}

; Branding
SetupIconFile=happy.ico
WizardImageFile=wizard-image.bmp
WizardSmallImageFile=wizard-small.bmp
WizardStyle=modern
WizardImageStretch=yes
WizardSizePercent=100

; Compression — LZMA2 max กดขนาด 330 MB → ~130 MB
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Uninstall
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

; Language picker — บังคับโชว์ทุกครั้ง + ไม่ cache language ที่เลือก
; (Fix 2026-05-16: cache เคยทำให้ Thai stuck แม้ user pick English)
ShowLanguageDialog=yes
UsePreviousLanguage=no

; Modern theme
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no
AlwaysShowDirOnReadyPage=yes
AlwaysShowGroupOnReadyPage=yes

; Misc
ChangesEnvironment=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartIfNeededByRun=no


[Languages]
; English first = fallback default ถ้า auto-detect ไม่ได้
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "license-en.txt"
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"; LicenseFile: "license-th.txt"


[CustomMessages]
; Thai
thai.AutoStartTask=เปิด HAPPY อัตโนมัติเมื่อ Windows boot
thai.DesktopIconDesc=สร้าง shortcut บน Desktop
thai.LaunchHappy=เปิด HAPPY ทันที 🚀
thai.WelcomeSubtitle=กำลังจะติดตั้ง HAPPY {#MyAppVersion} บนเครื่องของคุณ
thai.FinishedSubtitle=HAPPY พร้อมใช้งานแล้ว ✨

; English
english.AutoStartTask=Start HAPPY automatically when Windows boots
english.DesktopIconDesc=Create a shortcut on the Desktop
english.LaunchHappy=Launch HAPPY now 🚀
english.WelcomeSubtitle=This will install HAPPY {#MyAppVersion} on your computer
english.FinishedSubtitle=HAPPY is ready to use ✨


[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIconDesc}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autostart"; Description: "{cm:AutoStartTask}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked


[Files]
; HAPPY.exe + _internal/ — bundled from PyInstaller output
Source: "{#MyDistDir}\HAPPY.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyDistDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\ถอนการติดตั้ง {#MyAppName}"; Filename: "{uninstallexe}"; Languages: thai
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Languages: english

; Desktop (optional via Tasks)
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Auto-start (optional via Tasks)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: autostart


[Run]
; เปิด HAPPY ทันทีหลังติดตั้งจบ — มี checkbox
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchHappy}"; Flags: nowait postinstall skipifsilent unchecked


[UninstallDelete]
; ลบไฟล์ที่ HAPPY สร้างตอน runtime (sessions, cache, etc.)
; user data ใน ~/.happy/ ไม่ลบ — เป็นของ user (API key)
Type: filesandordirs; Name: "{app}\sessions"
Type: filesandordirs; Name: "{app}\__pycache__"


[Code]
// แสดง message ถ้า user ติดตั้งทับเวอร์ชันที่ HAPPY กำลังรันอยู่
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // ไม่ทำอะไรเพิ่ม — postinstall task ใน [Run] section ดูแลแล้ว
  end;
end;
