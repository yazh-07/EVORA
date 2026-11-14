package patcher

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func put(t *testing.T, root, name, value string) File {
	t.Helper()
	p := filepath.Join(root, filepath.FromSlash(name))
	if e := os.MkdirAll(filepath.Dir(p), 0755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(p, []byte(value), 0600); e != nil {
		t.Fatal(e)
	}
	h, e := Hash(p)
	if e != nil {
		t.Fatal(e)
	}
	return File{name, h, int64(len(value))}
}
func manifest(t *testing.T, path, version string, files []File) string {
	t.Helper()
	data, e := json.Marshal(Manifest{1, "windows-x64", version, files})
	if e != nil {
		t.Fatal(e)
	}
	if e = os.WriteFile(path, data, 0600); e != nil {
		t.Fatal(e)
	}
	h, e := Hash(path)
	if e != nil {
		t.Fatal(e)
	}
	return h
}
func fixture(t *testing.T) Plan {
	t.Helper()
	root, stage := t.TempDir(), t.TempDir()
	files := []File{}
	for _, name := range []string{"EVORA.exe", "evora-updater.exe", "backend/evora.exe", "backend/ui.js", "backend/obsolete.txt"} {
		files = append(files, put(t, root, name, "original "+name))
	}
	baseline := manifest(t, filepath.Join(root, Installed), "1.3.12", files)
	next := append([]File{}, files[:3]...)
	before := files[3].SHA
	updated := put(t, filepath.Join(stage, "payload"), "backend/ui.js", "new UI")
	added := put(t, filepath.Join(stage, "payload"), "backend/new.txt", "new asset")
	next = append(next, updated, added)
	hash := manifest(t, filepath.Join(stage, "manifest.json"), "1.4.0", next)
	put(t, root, "backend/user-note.txt", "unmanaged local file")
	return Plan{Root: root, Stage: stage, ManifestHash: hash, BaselineHash: baseline, Changes: []Change{{updated, &before}, {added, nil}}, Deletes: []File{files[4]}}
}
func expect(t *testing.T, root, name, value string) {
	t.Helper()
	data, e := os.ReadFile(filepath.Join(root, filepath.FromSlash(name)))
	if e != nil || string(data) != value {
		t.Fatalf("%s: %q, %v", name, data, e)
	}
}
func TestApplyRollbackAndRecoveryAreIdempotent(t *testing.T) {
	p := fixture(t)
	if e := Apply(p); e != nil {
		t.Fatal(e)
	}
	expect(t, p.Root, "backend/ui.js", "new UI")
	expect(t, p.Root, "backend/new.txt", "new asset")
	if _, e := os.Stat(filepath.Join(p.Root, "backend/obsolete.txt")); !os.IsNotExist(e) {
		t.Fatal("obsolete file not removed")
	}
	if e := Recover(p.Root); e != nil {
		t.Fatal(e)
	}
	if e := Recover(p.Root); e != nil {
		t.Fatal(e)
	}
	expect(t, p.Root, "backend/ui.js", "original backend/ui.js")
	expect(t, p.Root, "backend/obsolete.txt", "original backend/obsolete.txt")
	expect(t, p.Root, "backend/user-note.txt", "unmanaged local file")
	if _, e := os.Stat(filepath.Join(p.Root, "backend/new.txt")); !os.IsNotExist(e) {
		t.Fatal("new asset not removed")
	}
	h, _ := Hash(filepath.Join(p.Root, Installed))
	if h != p.BaselineHash {
		t.Fatal("inventory not restored")
	}
}
func TestCommitKeepsUpdatedFiles(t *testing.T) {
	p := fixture(t)
	if e := Apply(p); e != nil {
		t.Fatal(e)
	}
	if e := Commit(p.Root); e != nil {
		t.Fatal(e)
	}
	if e := Recover(p.Root); e != nil {
		t.Fatal(e)
	}
	expect(t, p.Root, "backend/ui.js", "new UI")
}
func TestTamperingIsRejectedBeforeMutation(t *testing.T) {
	for _, where := range []string{"staged", "baseline", "installed", "manifest", "new collision", "missing change", "missing removal"} {
		t.Run(where, func(t *testing.T) {
			p := fixture(t)
			switch where {
			case "staged":
				put(t, filepath.Join(p.Stage, "payload"), "backend/ui.js", "tampered")
			case "baseline":
				put(t, p.Root, Installed, "{}")
			case "installed":
				put(t, p.Root, "backend/ui.js", "local modification")
			case "manifest":
				put(t, p.Stage, "manifest.json", "{}")
			case "new collision":
				put(t, p.Root, "backend/new.txt", "local file")
			case "missing change":
				p.Changes = p.Changes[:1]
			case "missing removal":
				p.Deletes = nil
			}
			if e := Apply(p); e == nil {
				t.Fatal("tampering accepted")
			}
			if _, e := os.Stat(journalDir(p.Root)); !os.IsNotExist(e) {
				t.Fatal("mutation started before verification")
			}
		})
	}
}
func TestResumeInterruptedRollback(t *testing.T) {
	p := fixture(t)
	if e := Apply(p); e != nil {
		t.Fatal(e)
	}
	// Simulate a power loss after the inventory backup was restored. Recovery must
	// skip this consumed backup and finish restoring the remaining application files.
	if e := replace(filepath.Join(journalDir(p.Root), "backup", Installed), filepath.Join(p.Root, Installed)); e != nil {
		t.Fatal(e)
	}
	if e := Recover(p.Root); e != nil {
		t.Fatal(e)
	}
	expect(t, p.Root, "backend/ui.js", "original backend/ui.js")
}
func TestUnsafePathsAndDowngrades(t *testing.T) {
	root := t.TempDir()
	for _, name := range []string{"../EVORA.exe", "backend/../file", "backend/cases.sqlite3", "backend/vault/file", "backend/NUL.txt", "backend/a:stream", "/EVORA.exe", "backend/a.", "backend//file"} {
		if _, e := Safe(root, name); e == nil {
			t.Errorf("accepted %q", name)
		}
	}
	if Newer("1.3.1", "1.3.12") || Newer("1.3.12", "1.3.12") || !Newer("1.10.0", "1.9.9") {
		t.Fatal("version comparison")
	}
}
func TestLockExcludesConcurrentUpdate(t *testing.T) {
	root := t.TempDir()
	release, e := Lock(root)
	if e != nil {
		t.Fatal(e)
	}
	defer release()
	if second, e := Lock(root); e == nil {
		second()
		t.Fatal("second updater obtained lock")
	}
}

func TestRecoverBeforeFirstJournalSave(t *testing.T) {
	root := t.TempDir()
	put(t, root, "EVORA.exe", "intact launcher")
	if e := os.Mkdir(journalDir(root), 0700); e != nil {
		t.Fatal(e)
	}
	if e := Recover(root); e != nil {
		t.Fatal(e)
	}
	expect(t, root, "EVORA.exe", "intact launcher")
}
