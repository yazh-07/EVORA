package patcher

import (
	"os"
	"path/filepath"
	"syscall"
	"unsafe"
)

func replaceFile(from, to string) error {
	a, e := syscall.UTF16PtrFromString(from)
	if e != nil {
		return e
	}
	b, e := syscall.UTF16PtrFromString(to)
	if e != nil {
		return e
	}
	result, _, err := syscall.NewLazyDLL("kernel32.dll").NewProc("MoveFileExW").Call(uintptr(unsafe.Pointer(a)), uintptr(unsafe.Pointer(b)), 0x1|0x8)
	if result == 0 {
		return err
	}
	return nil
}
func Lock(root string) (func(), error) {
	path, e := syscall.UTF16PtrFromString(filepath.Join(root, ".evora-update.lock"))
	if e != nil {
		return nil, e
	}
	h, e := syscall.CreateFile(path, syscall.GENERIC_READ|syscall.GENERIC_WRITE, 0, nil, syscall.OPEN_ALWAYS, syscall.FILE_ATTRIBUTE_NORMAL, 0)
	if e != nil {
		return nil, e
	}
	f := os.NewFile(uintptr(h), "update lock")
	return func() { f.Close() }, nil
}
