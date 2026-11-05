package main

import (
	_ "embed"
	"fmt"
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
	appConfig = LoadConfig()
	backendMgr = NewBackendManager(appConfig)

	// Start backend server
	if err := backendMgr.Start(appConfig); err != nil {
		fmt.Printf("[EVORA Desktop] Backend start warning: %v\n", err)
	}

	// Wait up to 10 seconds for backend to start serving
	_ = backendMgr.WaitReady(10 * time.Second)

	// Run system tray in parallel
	go systray.Run(onTrayReady, onTrayExit)

	// Presentation mode
	targetURL := fmt.Sprintf("http://127.0.0.1:%d", appConfig.Port)

	if appConfig.Mode == "webview" && runtime.GOOS == "windows" {
		openNativeWindow(targetURL)
	} else {
		openSystemBrowser(targetURL)
		// Keep process alive for tray
		select {}
	}
}

func openNativeWindow(url string) {
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
		// Fallback to browser if WebView2 is missing
		openSystemBrowser(url)
		select {}
		return
	}

	wvWindow = wv
	wv.SetSize(1440, 900, webview2.HintNone)
	wv.Navigate(url)
	wv.Run()
}

func openSystemBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Start()
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

	statusText := fmt.Sprintf("Backend: Running (Port %d)", appConfig.Port)
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
