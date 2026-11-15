package patcher

import (
	"errors"
	"os"
	"path/filepath"
	"sort"
)

// Uninstall removes only inventory files whose contents still match the release.
// Untracked data and locally modified files are kept, including inside backend.
func Uninstall(root string) error {
	manifest, err := ReadManifest(filepath.Join(root, Installed))
	if err != nil {
		return err
	}
	if manifest.Platform != "linux-x64" {
		return errors.New("use the Windows uninstaller")
	}
	release, err := Lock(root)
	if err != nil {
		return err
	}
	defer release()
	if _, err = os.Stat(journalDir(root)); !os.IsNotExist(err) {
		return errors.New("recover the pending update before uninstalling")
	}
	directories := map[string]bool{}
	for _, file := range manifest.Files {
		path, err := Safe(root, file.Path)
		if err != nil {
			return err
		}
		hash, err := Hash(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return err
		}
		if hash != file.SHA {
			continue
		}
		if err = os.Remove(path); err != nil {
			return err
		}
		for dir := filepath.Dir(path); dir != root; dir = filepath.Dir(dir) {
			directories[dir] = true
		}
	}
	names := []string{}
	for dir := range directories {
		names = append(names, dir)
	}
	sort.Slice(names, func(i, j int) bool { return len(names[i]) > len(names[j]) })
	for _, dir := range names {
		_ = os.Remove(dir)
	} // Only empty directories are removed.
	return os.Remove(filepath.Join(root, Installed))
}
