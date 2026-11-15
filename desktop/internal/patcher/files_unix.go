//go:build !windows

package patcher

import (
	"os"
	"path/filepath"
	"syscall"
)

func replaceFile(from, to string) error {
	if err := os.Rename(from, to); err != nil {
		return err
	}
	for _, path := range []string{filepath.Dir(from), filepath.Dir(to)} {
		dir, err := os.Open(path)
		if err != nil {
			return err
		}
		err = dir.Sync()
		_ = dir.Close()
		if err != nil {
			return err
		}
	}
	return nil
}
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
