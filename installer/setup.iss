; -- EVORA Windows Inno Setup Script --
; Compiles EVORA into a standalone Windows installer with custom AI setup wizard.

#define MyAppName "EVORA"
#define MyAppFullName "EVORA — Forensic Evidence Fusion & Investigation Workstation"
#define MyAppVersion "1.3.9"
#define MyAppPublisher "EVORA Team"
#define MyAppURL "https://github.com/yazh-07/EVORA"
#define MyAppExeName "EVORA.exe"

[Setup]
AppId={{D37E81A2-F9B1-4A56-B102-178A7E0CDD1C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppFullName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\EVORA
DefaultGroupName=EVORA
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=EVORA-Setup-Windows-x64
SetupIconFile=..\desktop\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Launch EVORA automatically on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
; The Go WebView2 Desktop & System Tray supervisor
Source: "..\desktop\evora-workstation.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
; Application Icon
Source: "..\desktop\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; The bundled PyInstaller Python + FastAPI backend & React frontend
Source: "..\dist\evora\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
; Copy core runtime DLLs directly into {app}\backend for immediate DLL search resolution
Source: "..\dist\evora\_internal\python3*.dll"; DestDir: "{app}\backend"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\evora\_internal\vcruntime140*.dll"; DestDir: "{app}\backend"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\evora\_internal\msvcp140*.dll"; DestDir: "{app}\backend"; Flags: ignoreversion skipifsourcedoesntexist
; Optional bundled Microsoft Visual C++ 2015-2022 Redistributable
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppFullName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: startupicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; Check: VCRedistNeedsInstall; StatusMsg: "Installing Microsoft Visual C++ Runtime..."; Flags: waituntilterminated skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppFullName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
  begin
    if Installed = 1 then
      Result := False;
  end;
end;

var
  AIPage: TWizardPage;
  OllamaRadio: TRadioButton;
  CloudRadio: TRadioButton;
  CustomRadio: TRadioButton;
  OllamaURLEdit: TNewEdit;
  OllamaModelEdit: TNewEdit;
  CloudURLEdit: TNewEdit;
  CloudModelEdit: TNewEdit;
  CloudKeyEdit: TPasswordEdit;
  OllamaLabel1, OllamaLabel2: TLabel;
  CloudLabel1, CloudLabel2, CloudLabel3: TLabel;

procedure OnAIRadioClick(Sender: TObject);
var
  UseCloudSettings: Boolean;
begin
  UseCloudSettings := CloudRadio.Checked or CustomRadio.Checked;

  OllamaURLEdit.Enabled := OllamaRadio.Checked;
  OllamaModelEdit.Enabled := OllamaRadio.Checked;
  OllamaLabel1.Enabled := OllamaRadio.Checked;
  OllamaLabel2.Enabled := OllamaRadio.Checked;

  CloudURLEdit.Enabled := UseCloudSettings;
  CloudModelEdit.Enabled := UseCloudSettings;
  CloudKeyEdit.Enabled := UseCloudSettings;
  CloudLabel1.Enabled := UseCloudSettings;
  CloudLabel2.Enabled := UseCloudSettings;
  CloudLabel3.Enabled := UseCloudSettings;

  if CustomRadio.Checked then
  begin
    CloudLabel1.Caption := 'Custom API Base URL:';
    CloudLabel2.Caption := 'Provider Model ID:';
    if CloudURLEdit.Text = 'https://openrouter.ai/api/v1' then
      CloudURLEdit.Text := '';
    if CloudModelEdit.Text = 'openai/gpt-4o-mini' then
      CloudModelEdit.Text := '';
  end
  else
  begin
    CloudLabel1.Caption := 'API Base URL:';
    CloudLabel2.Caption := 'Model Name:';
    if CloudRadio.Checked then
    begin
      if Trim(CloudURLEdit.Text) = '' then
        CloudURLEdit.Text := 'https://openrouter.ai/api/v1';
      if Trim(CloudModelEdit.Text) = '' then
        CloudModelEdit.Text := 'openai/gpt-4o-mini';
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = AIPage.ID) and (CloudRadio.Checked or CustomRadio.Checked) then
  begin
    if (Trim(CloudURLEdit.Text) = '') or (Trim(CloudModelEdit.Text) = '') then
    begin
      MsgBox('Enter the provider API base URL and model ID before continuing.', mbError, MB_OK);
      Result := False;
    end
    else if (Pos('https://', Lowercase(Trim(CloudURLEdit.Text))) <> 1) and
            (Pos('http://', Lowercase(Trim(CloudURLEdit.Text))) <> 1) then
    begin
      MsgBox('The provider API base URL must start with http:// or https://.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure InitializeWizard;
begin
  // Create Custom Page for AI Assistant Selection
  AIPage := CreateCustomPage(wpSelectDir,
    'Forensic AI Assistant Configuration',
    'Choose local Ollama, a hosted provider, or a custom OpenAI-compatible endpoint.');

  OllamaRadio := TRadioButton.Create(AIPage);
  OllamaRadio.Parent := AIPage.Surface;
  OllamaRadio.Top := ScaleY(10);
  OllamaRadio.Left := ScaleX(10);
  OllamaRadio.Width := ScaleX(400);
  OllamaRadio.Caption := 'Local Offline AI via Ollama (Air-gapped, zero cloud data transfer)';
  OllamaRadio.Font.Style := [fsBold];
  OllamaRadio.Checked := True;
  OllamaRadio.OnClick := @OnAIRadioClick;

  OllamaLabel1 := TLabel.Create(AIPage);
  OllamaLabel1.Parent := AIPage.Surface;
  OllamaLabel1.Top := ScaleY(116);
  OllamaLabel1.Left := ScaleX(30);
  OllamaLabel1.Caption := 'Ollama Endpoint URL:';

  OllamaURLEdit := TNewEdit.Create(AIPage);
  OllamaURLEdit.Parent := AIPage.Surface;
  OllamaURLEdit.Top := ScaleY(113);
  OllamaURLEdit.Left := ScaleX(160);
  OllamaURLEdit.Width := ScaleX(240);
  OllamaURLEdit.Text := 'http://127.0.0.1:11434';

  OllamaLabel2 := TLabel.Create(AIPage);
  OllamaLabel2.Parent := AIPage.Surface;
  OllamaLabel2.Top := ScaleY(146);
  OllamaLabel2.Left := ScaleX(30);
  OllamaLabel2.Caption := 'Model Name:';

  OllamaModelEdit := TNewEdit.Create(AIPage);
  OllamaModelEdit.Parent := AIPage.Surface;
  OllamaModelEdit.Top := ScaleY(143);
  OllamaModelEdit.Left := ScaleX(160);
  OllamaModelEdit.Width := ScaleX(240);
  OllamaModelEdit.Text := 'llama3.1:8b';

  // Cloud AI Radio Option
  CloudRadio := TRadioButton.Create(AIPage);
  CloudRadio.Parent := AIPage.Surface;
  CloudRadio.Top := ScaleY(44);
  CloudRadio.Left := ScaleX(10);
  CloudRadio.Width := ScaleX(400);
  CloudRadio.Caption := 'Hosted Provider (OpenAI, OpenRouter, Groq, OmniRoute)';
  CloudRadio.Font.Style := [fsBold];
  CloudRadio.Checked := False;
  CloudRadio.OnClick := @OnAIRadioClick;

  CustomRadio := TRadioButton.Create(AIPage);
  CustomRadio.Parent := AIPage.Surface;
  CustomRadio.Top := ScaleY(78);
  CustomRadio.Left := ScaleX(10);
  CustomRadio.Width := ScaleX(400);
  CustomRadio.Caption := 'Custom OpenAI-Compatible API';
  CustomRadio.Font.Style := [fsBold];
  CustomRadio.Checked := False;
  CustomRadio.OnClick := @OnAIRadioClick;

  CloudLabel1 := TLabel.Create(AIPage);
  CloudLabel1.Parent := AIPage.Surface;
  CloudLabel1.Top := ScaleY(166);
  CloudLabel1.Left := ScaleX(30);
  CloudLabel1.Caption := 'API Base URL:';

  CloudURLEdit := TNewEdit.Create(AIPage);
  CloudURLEdit.Parent := AIPage.Surface;
  CloudURLEdit.Top := ScaleY(163);
  CloudURLEdit.Left := ScaleX(160);
  CloudURLEdit.Width := ScaleX(240);
  CloudURLEdit.Text := 'https://openrouter.ai/api/v1';

  CloudLabel2 := TLabel.Create(AIPage);
  CloudLabel2.Parent := AIPage.Surface;
  CloudLabel2.Top := ScaleY(196);
  CloudLabel2.Left := ScaleX(30);
  CloudLabel2.Caption := 'Model Name:';

  CloudModelEdit := TNewEdit.Create(AIPage);
  CloudModelEdit.Parent := AIPage.Surface;
  CloudModelEdit.Top := ScaleY(193);
  CloudModelEdit.Left := ScaleX(160);
  CloudModelEdit.Width := ScaleX(240);
  CloudModelEdit.Text := 'openai/gpt-4o-mini';

  CloudLabel3 := TLabel.Create(AIPage);
  CloudLabel3.Parent := AIPage.Surface;
  CloudLabel3.Top := ScaleY(226);
  CloudLabel3.Left := ScaleX(30);
  CloudLabel3.Caption := 'API Key:';

  CloudKeyEdit := TPasswordEdit.Create(AIPage);
  CloudKeyEdit.Parent := AIPage.Surface;
  CloudKeyEdit.Top := ScaleY(223);
  CloudKeyEdit.Left := ScaleX(160);
  CloudKeyEdit.Width := ScaleX(240);
  CloudKeyEdit.Text := '';

  OnAIRadioClick(nil);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataDir, ConfigFile: String;
  ConfigContent: String;
  ProviderStr: String;
begin
  if CurStep = ssPostInstall then
  begin
    AppDataDir := ExpandConstant('{userappdata}\EVORA');
    ForceDirectories(AppDataDir);
    ConfigFile := AppDataDir + '\config.json';
    if FileExists(ConfigFile) then
      Exit;

    if OllamaRadio.Checked then
      ProviderStr := 'ollama'
    else
      ProviderStr := 'openai';

    ConfigContent := '{' + #13#10 +
      '  "mode": "webview",' + #13#10 +
      '  "port": 8000,' + #13#10 +
      '  "ai_provider": "' + ProviderStr + '",' + #13#10 +
      '  "ollama_url": "' + OllamaURLEdit.Text + '",' + #13#10 +
      '  "ollama_model": "' + OllamaModelEdit.Text + '",' + #13#10 +
      '  "cloud_base_url": "' + CloudURLEdit.Text + '",' + #13#10 +
      '  "cloud_model": "' + CloudModelEdit.Text + '",' + #13#10 +
      '  "cloud_api_key": "' + CloudKeyEdit.Text + '"' + #13#10 +
      '}';

    SaveStringToFile(ConfigFile, ConfigContent, False);
  end;
end;
