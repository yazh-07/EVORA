package main

import (
	_ "embed"
	"fmt"
	"html"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	"github.com/energye/systray"
	webview2 "github.com/jchv/go-webview2"
)

//go:embed icon.ico
var iconIcoData []byte

//go:embed icon.png
var iconPngData []byte

var (
	backendMgr *BackendManager
	appConfig  Config
	wvWindow   webview2.WebView
)

func main() {
	if !recoverApplicationUpdate() {
		return
	}
	appConfig = LoadConfig()
	port, err := availablePort(appConfig.Port)
	if err != nil {
		fmt.Println("Could not allocate a local workstation port")
		return
	}
	appConfig.Port = port
	backendMgr = NewBackendManager(appConfig)
	defer backendMgr.Stop()

	// Attempt to start backend server
	_ = backendMgr.Start(appConfig)

	// Wait for the backend, including a cold start of the bundled graph service.
	ready := backendMgr.WaitReady(180 * time.Second)
	if ready {
		markApplicationHealthy()
	}
	go watchApplicationUpdate()

	// Run system tray in parallel
	go systray.Run(onTrayReady, onTrayExit)

	targetURL := fmt.Sprintf("http://127.0.0.1:%d", appConfig.Port)

	if appConfig.Mode == "webview" && runtime.GOOS == "windows" {
		openNativeWindow(targetURL, ready)
	} else {
		if ready {
			openSystemBrowser(targetURL)
		} else {
			diag := backendMgr.GetDiagnosticInfo()
			fmt.Printf("[EVORA] Engine offline: %s\nLogs: %s\n", diag.LastError, diag.LogPath)
			openSystemBrowser(targetURL)
		}
		<-updateExit
	}
}

func openNativeWindow(targetURL string, initialReady bool) {
	wv := webview2.NewWithOptions(webview2.WebViewOptions{
		Debug:     false,
		AutoFocus: true,
		WindowOptions: webview2.WindowOptions{
			Title:  "EVORA — Forensic Evidence Fusion & Investigation Workspace",
			Width:  1440,
			Height: 900,
			IconId: 1,
			Center: true,
		},
	})
	if wv == nil {
		openSystemBrowser(targetURL)
		<-updateExit
		return
	}

	wvWindow = wv
	wv.SetSize(1440, 900, webview2.HintNone)
	_ = wv.Bind("evoraOpenChatGPT", func(raw string) error {
		if !validChatGPTAuthorizationURL(raw) {
			return fmt.Errorf("invalid sign-in destination")
		}
		return openSystemBrowser(raw)
	})

	// Bind JS helpers for the custom error page
	_ = wv.Bind("evoraRetry", func() {
		wv.Dispatch(func() {
			wv.SetHtml(buildLoadingHTML())
		})
		go func() {
			_ = backendMgr.Start(appConfig)
			if backendMgr.WaitReady(180 * time.Second) {
				wv.Dispatch(func() {
					wv.Navigate(targetURL)
				})
			} else {
				diag := backendMgr.GetDiagnosticInfo()
				wv.Dispatch(func() {
					wv.SetHtml(buildErrorHTML(diag))
				})
			}
		}()
	})

	_ = wv.Bind("evoraOpenLogs", func() {
		diag := backendMgr.GetDiagnosticInfo()
		if diag.LogPath != "" {
			openSystemBrowser(diag.LogPath)
		}
	})

	if initialReady {
		wv.Navigate(targetURL)
	} else {
		diag := backendMgr.GetDiagnosticInfo()
		wv.SetHtml(buildErrorHTML(diag))
	}

	wv.Run()
}

func buildLoadingHTML() string {
	return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Connecting to EVORA...</title>
  <style>
    body { background: #0b1120; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .spinner { width: 48px; height: 48px; border: 4px solid #1e293b; border-top-color: #38bdf8; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 24px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    h2 { margin: 0 0 8px; font-weight: 600; font-size: 1.3rem; }
    p { margin: 0; color: #94a3b8; font-size: 0.95rem; }
  </style>
</head>
<body>
  <div class="spinner"></div>
  <h2>Initializing Forensic Engine...</h2>
  <p>Connecting to local backend service on 127.0.0.1:8000</p>
</body>
</html>`
}

func buildErrorHTML(diag DiagnosticInfo) string {
	avWarning := ""
	if !diag.BinExists {
		avWarning = `
      <div class="warning-box">
        <strong>⚠️ Backend Executable Not Found:</strong><br>
        The backend engine (<code>` + html.EscapeString(diag.BinPath) + `</code>) is missing from disk.<br>
        <strong>Your antivirus software (e.g. Windows Defender) likely blocked or quarantined it during extraction.</strong><br>
        Please open <em>Windows Security &rarr; Virus &amp; threat protection &rarr; Protection history</em>, allow the file, or add an exclusion for the EVORA installation folder.
      </div>
    `
	}

	lastErrSnippet := ""
	if diag.LastError != "" {
		lastErrSnippet = `<div class="error-detail"><strong>Last error:</strong> ` + html.EscapeString(diag.LastError) + `</div>`
	}

	return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>EVORA — Engine Offline</title>
  <style>
    body { background: #0b1120; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 24px; box-sizing: border-box; }
    .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 14px; max-width: 680px; width: 100%; padding: 36px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); text-align: center; }
    .logo { width: 52px; height: 52px; margin-bottom: 16px; color: #38bdf8; }
    h1 { margin: 0 0 8px; font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
    p.sub { margin: 0 0 24px; color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
    .warning-box { background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 8px; color: #fca5a5; padding: 14px 18px; margin-bottom: 20px; text-align: left; font-size: 0.88rem; line-height: 1.6; }
    .error-detail { background: #1e293b; border-radius: 6px; color: #f87171; padding: 10px 14px; margin-bottom: 20px; text-align: left; font-size: 0.82rem; font-family: monospace; overflow-x: auto; }
    .log-box { background: #020617; border: 1px solid #1e293b; border-radius: 8px; padding: 14px; text-align: left; font-family: monospace; font-size: 0.78rem; color: #cbd5e1; max-height: 140px; overflow-y: auto; white-space: pre-wrap; margin-bottom: 24px; }
    .actions { display: flex; gap: 12px; justify-content: center; }
    button { background: #0284c7; color: #fff; border: none; padding: 11px 22px; border-radius: 8px; font-size: 0.92rem; font-weight: 600; cursor: pointer; transition: background 0.15s; }
    button:hover { background: #0369a1; }
    button.secondary { background: #1e293b; color: #cbd5e1; }
    button.secondary:hover { background: #334155; }
  </style>
</head>
<body>
  <div class="card">
    <svg class="logo" viewBox="0 0 28 30" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 2 25 7v8c0 6-5 10-11 13C8 25 3 21 3 15V7L14 2Z" />
      <path d="M9 10h10M9 15h8M9 20h5" />
    </svg>
    <h1>Unable to Reach EVORA Engine</h1>
    <p class="sub">The desktop interface cannot connect to the local background server on <code>` + html.EscapeString(diag.URL) + `</code>.</p>
    ` + avWarning + lastErrSnippet + `
    <div class="log-box">` + html.EscapeString(diag.RecentLogs) + `</div>
    <div class="actions">
      <button onclick="window.evoraRetry()">⟲ Retry Connection</button>
      <button class="secondary" onclick="window.evoraOpenLogs()">Open Log File</button>
    </div>
  </div>
</body>
</html>`
}

func openSystemBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Start()
}

func onTrayReady() {
	if runtime.GOOS == "windows" && len(iconIcoData) > 0 {
		systray.SetIcon(iconIcoData)
	} else if len(iconPngData) > 0 {
		systray.SetIcon(iconPngData)
	}

	systray.SetTitle("EVORA Workstation")
	systray.SetTooltip("EVORA — Forensic Evidence Fusion")

	mOpen := systray.AddMenuItem("Open Workstation", "Open the investigation workspace")
	mBrowser := systray.AddMenuItem("Open in Web Browser", "Open in default browser")
	systray.AddSeparator()

	statusText := fmt.Sprintf("Backend: Port %d", appConfig.Port)
	mStatus := systray.AddMenuItem(statusText, "Server status")
	mStatus.Disable()

	mConfig := systray.AddMenuItem("Open Data Folder", "Show local evidence & database directory")
	systray.AddSeparator()
	mQuit := systray.AddMenuItem("Exit EVORA", "Shutdown workstation and quit")

	targetURL := fmt.Sprintf("http://127.0.0.1:%d", appConfig.Port)

	mOpen.Click(func() {
		if wvWindow != nil {
			wvWindow.Navigate(targetURL)
		} else {
			openSystemBrowser(targetURL)
		}
	})

	mBrowser.Click(func() {
		openSystemBrowser(targetURL)
	})

	mConfig.Click(func() {
		openConfigFolder()
	})

	mQuit.Click(func() {
		systray.Quit()
	})
}

func openConfigFolder() {
	appData := os.Getenv("APPDATA")
	var path string
	if appData != "" {
		path = filepath.Join(appData, "EVORA")
	} else {
		home, _ := os.UserHomeDir()
		path = filepath.Join(home, ".evora")
	}
	_ = os.MkdirAll(path, 0755)
	openSystemBrowser(path)
}

func onTrayExit() {
	if backendMgr != nil {
		backendMgr.Stop()
	}
	os.Exit(0)
}
