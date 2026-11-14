//go:build !windows

package patcher

import (
	"os"
	"syscall"
)

func replaceFile(from, to string) error { return os.Rename(from, to) }
func Lock(root string) (func(), error) {
	f, e := os.OpenFile(root+"/.evora-update.lock", os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		return nil, e
	}
	if e = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		f.Close()
		return nil, e
	}
	return func() { f.Close() }, nil
}
