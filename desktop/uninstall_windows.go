package main

import (
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

const runtimeMutexName = `Local\EVORA.Workstation.Runtime`
const maintenanceMutexName = `Local\EVORA.Workstation.Maintenance`

func maintenanceActive() bool {
	name, _ := syscall.UTF16PtrFromString(maintenanceMutexName)
	handle, _, _ := kernel32.NewProc("OpenMutexW").Call(0x100000, 0, uintptr(unsafe.Pointer(name)))
	if handle == 0 {
		return false
	}
	closeHandle.Call(handle)
	return true
}
func registerRuntime() (func(), error) {
	name, _ := syscall.UTF16PtrFromString(runtimeMutexName)
	handle, _, err := kernel32.NewProc("CreateMutexW").Call(0, 0, uintptr(unsafe.Pointer(name)))
	if handle == 0 {
		return nil, err
	}
	return func() { closeHandle.Call(handle) }, nil
}

// A shutdown request never acquires ownership, opens a window, or starts a server.
func requestWorkstationShutdown(database string, timeout time.Duration) error {
	lockPath, _ := syscall.UTF16PtrFromString(filepath.Join(filepath.Dir(database), "workstation.lock"))
	handle, err := syscall.CreateFile(lockPath, syscall.GENERIC_READ|syscall.GENERIC_WRITE,
		syscall.FILE_SHARE_READ|syscall.FILE_SHARE_WRITE, nil, syscall.OPEN_EXISTING, syscall.FILE_ATTRIBUTE_NORMAL, 0)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return errors.New("could not check the running workstation")
	}
	defer syscall.CloseHandle(handle)
	var overlap syscall.Overlapped
	tryLock := func() bool {
		ok, _, _ := lockFile.Call(uintptr(handle), 3, 0, 1, 0, uintptr(unsafe.Pointer(&overlap)))
		if ok == 0 {
			return false
		}
		unlockFile.Call(uintptr(handle), 0, 1, 0, uintptr(unsafe.Pointer(&overlap)))
		return true
	}
	if tryLock() {
		return nil
	}
	key, err := workstationKey(database)
	if err != nil {
		return err
	}
	name, _ := syscall.UTF16PtrFromString(key + "-shutdown")
	event, _, _ := kernel32.NewProc("OpenEventW").Call(2, 0, uintptr(unsafe.Pointer(name)))
	if event == 0 {
		return errors.New("exit EVORA from its tray menu before uninstalling")
	}
	defer closeHandle.Call(event)
	if ok, _, _ := setEvent.Call(event); ok == 0 {
		return errors.New("could not request EVORA shutdown")
	}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if tryLock() {
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return errors.New("EVORA is still shutting down")
}
