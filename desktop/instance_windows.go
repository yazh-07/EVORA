package main

import (
	"crypto/sha256"
	"fmt"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"unsafe"
)

var kernel32 = syscall.NewLazyDLL("kernel32.dll")
var createMutex = kernel32.NewProc("CreateMutexW")
var createEvent = kernel32.NewProc("CreateEventW")
var setEvent = kernel32.NewProc("SetEvent")
var waitObject = kernel32.NewProc("WaitForSingleObject")
var closeHandle = kernel32.NewProc("CloseHandle")

type workstationInstance struct {
	mutex, event uintptr
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
	eventName, _ := syscall.UTF16PtrFromString(key + "-activate")
	event, _, err := createEvent.Call(0, 0, 0, uintptr(unsafe.Pointer(eventName)))
	if event == 0 {
		return nil, fmt.Errorf("create activation event: %w", err)
	}
	mutexName, _ := syscall.UTF16PtrFromString(key)
	mutex, _, err := createMutex.Call(0, 0, uintptr(unsafe.Pointer(mutexName)))
	if mutex == 0 {
		closeHandle.Call(event)
		return nil, fmt.Errorf("create workstation lock: %w", err)
	}
	if err == syscall.Errno(183) { // ERROR_ALREADY_EXISTS
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
	return &workstationInstance{mutex: mutex, event: event, stop: make(chan struct{}), done: make(chan struct{})}, nil
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
func (i *workstationInstance) Close() {
	i.once.Do(func() { close(i.stop); <-i.done; closeHandle.Call(i.mutex); closeHandle.Call(i.event) })
}
