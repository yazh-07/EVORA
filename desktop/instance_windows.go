package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

var kernel32 = syscall.NewLazyDLL("kernel32.dll")
var lockFile = kernel32.NewProc("LockFileEx")
var unlockFile = kernel32.NewProc("UnlockFileEx")
var createEvent = kernel32.NewProc("CreateEventW")
var setEvent = kernel32.NewProc("SetEvent")
var waitObject = kernel32.NewProc("WaitForSingleObject")
var closeHandle = kernel32.NewProc("CloseHandle")

type workstationInstance struct {
	mutex, event uintptr
	closing      uintptr
	stop         chan struct{}
	done         chan struct{}
	once         sync.Once
}

// Kernel handles disappear after a crash, so no stale PID/lock file can block launch.
func acquireWorkstation(database string) (*workstationInstance, error) {
	path, err := filepath.Abs(database)
	if err != nil {
		return nil, err
	}
	key := fmt.Sprintf(`Local\EVORA-Workstation-%x`, sha256.Sum256([]byte(strings.ToLower(filepath.Clean(path)))))
	closingName, _ := syscall.UTF16PtrFromString(key + "-closing")
	closing, _, err := createEvent.Call(0, 1, 0, uintptr(unsafe.Pointer(closingName)))
	if closing == 0 {
		return nil, fmt.Errorf("create closing event: %w", err)
	}
	keepClosing := false
	defer func() {
		if !keepClosing {
			closeHandle.Call(closing)
		}
	}()
	eventName, _ := syscall.UTF16PtrFromString(key + "-activate")
	event, _, err := createEvent.Call(0, 0, 0, uintptr(unsafe.Pointer(eventName)))
	if event == 0 {
		return nil, fmt.Errorf("create activation event: %w", err)
	}
	// File locking is atomic across processes and released by Windows on exit.
	// Unlike GetLastError after CreateMutex, success is determined by its return value.
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		closeHandle.Call(event)
		return nil, err
	}
	lockPath, _ := syscall.UTF16PtrFromString(filepath.Join(filepath.Dir(path), "workstation.lock"))
	handle, err := syscall.CreateFile(lockPath, syscall.GENERIC_READ|syscall.GENERIC_WRITE,
		syscall.FILE_SHARE_READ|syscall.FILE_SHARE_WRITE, nil, syscall.OPEN_ALWAYS, syscall.FILE_ATTRIBUTE_NORMAL, 0)
	if err != nil {
		closeHandle.Call(event)
		return nil, err
	}
	mutex := uintptr(handle)
	var overlap syscall.Overlapped
	locked, _, lockErr := lockFile.Call(mutex, 3, 0, 1, 0, uintptr(unsafe.Pointer(&overlap)))
	// A launch during shutdown waits for ownership; it must not open a browser
	// against the backend being stopped or create another tray.
	closingState, _, _ := waitObject.Call(closing, 0)
	if locked == 0 && lockErr == syscall.Errno(33) && closingState == 0 {
		deadline := time.Now().Add(70 * time.Second)
		for locked == 0 && lockErr == syscall.Errno(33) && time.Now().Before(deadline) {
			time.Sleep(100 * time.Millisecond)
			locked, _, lockErr = lockFile.Call(mutex, 3, 0, 1, 0, uintptr(unsafe.Pointer(&overlap)))
		}
		if locked == 0 {
			closeHandle.Call(mutex)
			closeHandle.Call(event)
			return nil, fmt.Errorf("EVORA is still shutting down; try again shortly")
		}
	}
	if locked == 0 {
		if lockErr != syscall.Errno(33) {
			closeHandle.Call(mutex)
			closeHandle.Call(event)
			return nil, fmt.Errorf("lock workstation: %w", lockErr)
		}
		// The newly launched process may transfer its foreground permission to EVORA.
		user32.NewProc("AllowSetForegroundWindow").Call(0xffffffff)
		ok, _, signalErr := setEvent.Call(event)
		closeHandle.Call(mutex)
		closeHandle.Call(event)
		if ok == 0 {
			return nil, fmt.Errorf("activate workstation: %w", signalErr)
		}
		return nil, nil
	}
	kernel32.NewProc("ResetEvent").Call(closing)
	keepClosing = true
	return &workstationInstance{mutex: mutex, event: event, closing: closing, stop: make(chan struct{}), done: make(chan struct{})}, nil
}

func (i *workstationInstance) serve(ready <-chan struct{}) {
	defer close(i.done)
	select {
	case <-ready:
	case <-i.stop:
		return
	}
	for {
		select {
		case <-i.stop:
			return
		default:
		}
		result, _, _ := waitObject.Call(i.event, 250)
		if result == 0 {
			openWorkstation()
		}
		if result == 0xffffffff {
			return
		}
	}
}
func (i *workstationInstance) markClosing() { setEvent.Call(i.closing) }

func (i *workstationInstance) Close() {
	i.once.Do(func() {
		i.markClosing()
		close(i.stop)
		<-i.done
		var overlap syscall.Overlapped
		unlockFile.Call(i.mutex, 0, 1, 0, uintptr(unsafe.Pointer(&overlap)))
		closeHandle.Call(i.mutex)
		closeHandle.Call(i.event)
		closeHandle.Call(i.closing)
	})
}
