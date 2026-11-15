package main

import (
	"fmt"
	"sync"
	"sync/atomic"
	"syscall"
	"unsafe"

	webview2 "github.com/jchv/go-webview2"
	"github.com/yazh-07/evora/desktop/internal/launchconfig"
)

var trayReady atomic.Bool
var quitting atomic.Bool
var nativeMu sync.Mutex
var user32 = syscall.NewLazyDLL("user32.dll")
var comctl32 = syscall.NewLazyDLL("comctl32.dll")
var showWindow = user32.NewProc("ShowWindow")
var setForeground = user32.NewProc("SetForegroundWindow")
var setSubclass = comctl32.NewProc("SetWindowSubclass")
var removeSubclass = comctl32.NewProc("RemoveWindowSubclass")
var defSubclass = comctl32.NewProc("DefSubclassProc")
var closeCallback uintptr

func init() { closeCallback = syscall.NewCallback(closeWindowProcedure) }

const traySubclassID = 0x45564f52

func minimizeOnClose() bool {
	if quitting.Load() || !trayReady.Load() {
		return false
	}
	if backendMgr == nil {
		return true
	}
	return launchconfig.Load(backendMgr.dbPath, backendMgr.port).MinimizeToTray
}
func closeWindowProcedure(hwnd, msg, wp, lp, id, data uintptr) uintptr {
	switch msg {
	case 0x0010: // WM_CLOSE
		if minimizeOnClose() {
			showWindow.Call(hwnd, 0)
			return 0
		}
		beginWorkstationShutdown()
	case 0x0011:
		quitting.Store(true) // Windows is ending the session.
	case 0x0016:
		if wp == 0 {
			quitting.Store(false)
		}
	case 0x0082:
		removeSubclass.Call(hwnd, closeCallback, traySubclassID)
	}
	result, _, _ := defSubclass.Call(hwnd, msg, wp, lp)
	return result
}
func installCloseToTray(window unsafe.Pointer) error {
	result, _, err := setSubclass.Call(uintptr(window), closeCallback, traySubclassID, 0)
	if result == 0 {
		return fmt.Errorf("window close handler: %v", err)
	}
	return nil
}
func setNativeWindow(window webview2.WebView) { nativeMu.Lock(); wvWindow = window; nativeMu.Unlock() }
func nativeWindow() webview2.WebView          { nativeMu.Lock(); defer nativeMu.Unlock(); return wvWindow }
func restoreNativeWindow() bool {
	window := nativeWindow()
	if window == nil {
		return false
	}
	window.Dispatch(func() { hwnd := uintptr(window.Window()); showWindow.Call(hwnd, 9); setForeground.Call(hwnd) })
	return true
}
func terminateNativeWindow() {
	if window := nativeWindow(); window != nil {
		window.Dispatch(func() { window.Destroy() })
	}
}
