package main

import (
	"os"
	"path/filepath"
	"runtime"
	"syscall"
	"testing"
	"unsafe"
)

func TestCloseHidesWindowOnlyWhenTrayReadyAndEnabled(t *testing.T) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	previous := backendMgr
	defer func() { backendMgr = previous; quitting.Store(false); trayReady.Store(false) }()
	backendMgr = &BackendManager{dbPath: filepath.Join(t.TempDir(), "cases.sqlite3"), port: 8000}
	class, _ := syscall.UTF16PtrFromString("STATIC")
	title, _ := syscall.UTF16PtrFromString("EVORA tray acceptance")
	hwnd, _, err := user32.NewProc("CreateWindowExW").Call(0, uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(title)), 0x10cf0000, 0, 0, 320, 200, 0, 0, 0, 0)
	if hwnd == 0 {
		t.Fatal(err)
	}
	defer user32.NewProc("DestroyWindow").Call(hwnd)
	if err := installCloseToTray(unsafe.Pointer(hwnd)); err != nil {
		t.Fatal(err)
	}
	trayReady.Store(true)
	quitting.Store(false)
	user32.NewProc("SendMessageW").Call(hwnd, 0x10, 0, 0)
	valid, _, _ := user32.NewProc("IsWindow").Call(hwnd)
	visible, _, _ := user32.NewProc("IsWindowVisible").Call(hwnd)
	if valid == 0 || visible != 0 {
		t.Fatal("close must hide, not destroy", valid, visible)
	}
	showWindow.Call(hwnd, 9)
	visible, _, _ = user32.NewProc("IsWindowVisible").Call(hwnd)
	if visible == 0 {
		t.Fatal("hidden window cannot be restored")
	}
	_ = os.WriteFile(filepath.Join(filepath.Dir(backendMgr.dbPath), "launcher.json"), []byte(`{"port":8000,"minimize_to_tray":false}`), 0600)
	user32.NewProc("SendMessageW").Call(hwnd, 0x10, 0, 0)
	valid, _, _ = user32.NewProc("IsWindow").Call(hwnd)
	if valid != 0 {
		t.Fatal("disabled close-to-tray must destroy the window")
	}
	trayReady.Store(false)
	if minimizeOnClose() {
		t.Fatal("never hide without a usable tray")
	}
	trayReady.Store(true)
	quitting.Store(true)
	if minimizeOnClose() {
		t.Fatal("explicit quit must bypass close-to-tray")
	}
}
