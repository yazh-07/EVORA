// Package patcher applies only verified, managed application files with a durable rollback journal.
package patcher

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

const Installed = "evora-install.json"

type File struct {
	Path string `json:"path"`
	SHA  string `json:"sha256"`
	Size int64  `json:"size"`
}
type Change struct {
	File
	Before *string `json:"before"`
}
type Manifest struct {
	Format   int    `json:"format"`
	Platform string `json:"platform"`
	Version  string `json:"version"`
	Files    []File `json:"files"`
}
type Plan struct {
	Root         string   `json:"root"`
	Stage        string   `json:"stage"`
	ManifestHash string   `json:"manifest_sha256"`
	BaselineHash string   `json:"baseline_sha256"`
	Changes      []Change `json:"changes"`
	Deletes      []File   `json:"deletes"`
	OwnerPID     int      `json:"owner_pid"`
	BackendPID   int      `json:"backend_pid"`
	StopMarker   string   `json:"stop_marker"`
	HealthFile   string   `json:"health_file"`
	ResultFile   string   `json:"result_file"`
}
type Entry struct {
	Path    string `json:"path"`
	Existed bool   `json:"existed"`
	NewHash string `json:"new_hash"`
}
type Journal struct {
	Entries []Entry `json:"entries"`
	Phase   string  `json:"phase"`
}

var hashPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)
var versionPattern = regexp.MustCompile(`^\d+\.\d+\.\d+$`)
var reserved = regexp.MustCompile(`(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$`)

func Hash(path string) (string, error) {
	f, e := os.Open(path)
	if e != nil {
		return "", e
	}
	defer f.Close()
	h := sha256.New()
	_, e = io.Copy(h, f)
	return hex.EncodeToString(h.Sum(nil)), e
}
func Safe(root, name string) (string, error) {
	if name == "" || len(name) > 240 || strings.ContainsAny(name, "\\:\x00") || strings.HasPrefix(name, "/") {
		return "", errors.New("invalid update path")
	}
	parts := strings.Split(name, "/")
	for _, p := range parts {
		if p == "" || p == "." || p == ".." || strings.TrimRight(p, " .") != p || reserved.MatchString(p) {
			return "", errors.New("invalid update path")
		}
	}
	if name != Installed && name != "EVORA.exe" && name != "evora-updater.exe" && name != "icon.ico" && (len(parts) < 2 || parts[0] != "backend") {
		return "", errors.New("unmanaged update path")
	}
	if len(parts) > 1 {
		switch strings.ToLower(parts[1]) {
		case "storage", "evidence", "vault", "evidence_vault", "updates":
			return "", errors.New("user data cannot be updated")
		}
	}
	switch strings.ToLower(filepath.Ext(name)) {
	case ".db", ".sqlite", ".sqlite3":
		return "", errors.New("database cannot be updated")
	}
	target := filepath.Join(root, filepath.FromSlash(name))
	for current := target; ; current = filepath.Dir(current) {
		if f, e := os.Lstat(current); e == nil && f.Mode()&os.ModeSymlink != 0 {
			return "", errors.New("linked update path")
		}
		if current == root {
			break
		}
		if filepath.Dir(current) == current {
			return "", errors.New("path outside installation")
		}
	}
	return target, nil
}
func ReadManifest(path string) (Manifest, error) {
	var m Manifest
	f, e := os.Open(path)
	if e != nil {
		return m, e
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, 8*1024*1024+1))
	if e != nil || len(b) > 8*1024*1024 {
		return m, errors.New("invalid manifest size")
	}
	if e = json.Unmarshal(b, &m); e != nil {
		return m, e
	}
	if m.Format != 1 || m.Platform != "windows-x64" || !versionPattern.MatchString(m.Version) || len(m.Files) == 0 || len(m.Files) > 20000 {
		return m, errors.New("unsupported manifest")
	}
	seen := map[string]bool{}
	for _, f := range m.Files {
		if f.Path == Installed {
			return m, errors.New("manifest cannot manage itself")
		}
		if _, e = Safe(filepath.Dir(path), f.Path); e != nil {
			return m, e
		}
		key := strings.ToLower(f.Path)
		if seen[key] || !hashPattern.MatchString(f.SHA) || f.Size < 0 || f.Size > 2<<30 {
			return m, errors.New("invalid file manifest")
		}
		seen[key] = true
	}
	for _, name := range []string{"evora.exe", "evora-updater.exe", "backend/evora.exe"} {
		if !seen[name] {
			return m, errors.New("incomplete application manifest")
		}
	}
	return m, nil
}
func atomicJSON(path string, value any) error {
	b, e := json.Marshal(value)
	if e != nil {
		return e
	}
	tmp := path + ".new"
	f, e := os.OpenFile(tmp, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	_, e = f.Write(b)
	if e == nil {
		e = f.Sync()
	}
	closeErr := f.Close()
	if e != nil {
		return e
	}
	if closeErr != nil {
		return closeErr
	}
	return replace(tmp, path)
}
func replace(from, to string) error { // Destination replacement is platform-specific.
	return replaceFile(from, to)
}
func copyFile(from, to string) error {
	in, e := os.Open(from)
	if e != nil {
		return e
	}
	defer in.Close()
	out, e := os.OpenFile(to, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if e != nil {
		return e
	}
	_, e = io.Copy(out, in)
	if e == nil {
		e = out.Sync()
	}
	c := out.Close()
	if e == nil {
		e = c
	}
	return e
}
func journalDir(root string) string { return filepath.Join(root, ".evora-update-journal") }
func checkedJournal(root string) (string, error) {
	d := journalDir(root)
	if f, e := os.Lstat(d); e == nil && (!f.IsDir() || f.Mode()&os.ModeSymlink != 0) {
		return "", errors.New("invalid update journal")
	}
	return d, nil
}

// Validate is repeated after shutdown, before any installed application file changes.
func Validate(p Plan) (Manifest, error) {
	var none Manifest
	if !filepath.IsAbs(p.Root) || !filepath.IsAbs(p.Stage) || filepath.Clean(p.Root) != p.Root || filepath.Clean(p.Stage) != p.Stage {
		return none, errors.New("absolute application paths required")
	}
	if _, e := Safe(p.Root, Installed); e != nil {
		return none, e
	}
	h, e := Hash(filepath.Join(p.Root, Installed))
	if e != nil || h != p.BaselineHash {
		return none, errors.New("installation changed; check for updates again")
	}
	manifest := filepath.Join(p.Stage, "manifest.json")
	h, e = Hash(manifest)
	if e != nil || h != p.ManifestHash {
		return none, errors.New("update manifest verification failed")
	}
	current, e := ReadManifest(filepath.Join(p.Root, Installed))
	if e != nil {
		return none, e
	}
	next, e := ReadManifest(manifest)
	if e != nil {
		return none, e
	}
	if !Newer(next.Version, current.Version) {
		return none, errors.New("update is not newer")
	}
	old := map[string]File{}
	for _, f := range current.Files {
		old[strings.ToLower(f.Path)] = f
	}
	newFiles := map[string]File{}
	for _, f := range next.Files {
		newFiles[strings.ToLower(f.Path)] = f
	}
	changed := map[string]bool{}
	for _, c := range p.Changes {
		key := strings.ToLower(c.Path)
		entry, ok := newFiles[key]
		if !ok || changed[key] || entry.SHA != c.SHA || entry.Size != c.Size {
			return none, errors.New("invalid changed file list")
		}
		changed[key] = true
		target, e := Safe(p.Root, c.Path)
		if e != nil {
			return none, e
		}
		before, e := Hash(target)
		if c.Before == nil {
			if !os.IsNotExist(e) {
				return none, errors.New("new file destination changed")
			}
		} else if e != nil || before != *c.Before {
			return none, errors.New("application file changed during download")
		}
		if c.Before != nil {
			if _, ok := old[key]; !ok {
				return none, errors.New("cannot replace unmanaged file")
			}
		}
		staged, e := Safe(filepath.Join(p.Stage, "payload"), c.Path)
		if e != nil {
			return none, e
		}
		h, e := Hash(staged)
		if e != nil || h != c.SHA {
			return none, errors.New("staged file verification failed")
		}
		stat, e := os.Stat(staged)
		if e != nil || stat.Size() != c.Size {
			return none, errors.New("staged file size invalid")
		}
	}
	for _, f := range next.Files {
		if changed[strings.ToLower(f.Path)] {
			continue
		}
		path, e := Safe(p.Root, f.Path)
		if e != nil {
			return none, e
		}
		h, e := Hash(path)
		if e != nil || h != f.SHA {
			return none, errors.New("required changed file missing")
		}
	}
	removed := map[string]bool{}
	for _, f := range p.Deletes {
		key := strings.ToLower(f.Path)
		original, ok := old[key]
		_, exists := newFiles[key]
		if !ok || exists || removed[key] || f.SHA != original.SHA {
			return none, errors.New("invalid removal list")
		}
		removed[key] = true
		path, e := Safe(p.Root, f.Path)
		if e != nil {
			return none, e
		}
		h, e := Hash(path)
		if e != nil || h != f.SHA {
			return none, errors.New("modified application file cannot be deleted")
		}
	}
	for key, f := range old {
		if _, ok := newFiles[key]; !ok && !removed[key] {
			path, e := Safe(p.Root, f.Path)
			if e != nil {
				return none, e
			}
			if _, e = os.Lstat(path); !os.IsNotExist(e) {
				return none, errors.New("required removal missing")
			}
		}
	}
	return next, nil
}

// Apply keeps the journal until the newly started application passes its health check.
func Apply(p Plan) error {
	if _, e := Validate(p); e != nil {
		return e
	}
	d, e := checkedJournal(p.Root)
	if e != nil {
		return e
	}
	if _, e = os.Stat(d); !os.IsNotExist(e) {
		return errors.New("pending update requires recovery")
	}
	if e = os.Mkdir(d, 0700); e != nil {
		return e
	}
	j := Journal{Phase: "applying"}
	save := func() error { return atomicJSON(filepath.Join(d, "journal.json"), j) }
	if e = save(); e != nil {
		return e
	}
	mutate := func(name, source, newHash string) error {
		target, e := Safe(p.Root, name)
		if e != nil {
			return e
		}
		_, statErr := os.Lstat(target)
		existed := statErr == nil
		if statErr != nil && !os.IsNotExist(statErr) {
			return statErr
		}
		backup := filepath.Join(d, "backup", filepath.FromSlash(name))
		if e = os.MkdirAll(filepath.Dir(backup), 0700); e != nil {
			return e
		}
		j.Entries = append(j.Entries, Entry{name, existed, newHash})
		if e = save(); e != nil {
			return e
		}
		if existed {
			// Keep the executable at its installed path even during a power loss.
			// Publish a complete backup before atomically replacing the target.
			if e = copyFile(target, backup+".new"); e != nil {
				return e
			}
			if e = replace(backup+".new", backup); e != nil {
				return e
			}
		}
		if source != "" {
			if e = os.MkdirAll(filepath.Dir(target), 0755); e != nil {
				return e
			}
			temp := filepath.Join(d, "new", filepath.FromSlash(name))
			if e = os.MkdirAll(filepath.Dir(temp), 0700); e != nil {
				return e
			}
			if e = copyFile(source, temp); e != nil {
				return e
			}
			if e = replace(temp, target); e != nil {
				return e
			}
		} else if existed {
			if e = os.Remove(target); e != nil {
				return e
			}
		}
		return nil
	}
	for _, f := range p.Changes {
		if e = mutate(f.Path, filepath.Join(p.Stage, "payload", filepath.FromSlash(f.Path)), f.SHA); e != nil {
			return e
		}
	}
	for _, f := range p.Deletes {
		if e = mutate(f.Path, "", ""); e != nil {
			return e
		}
	}
	if e = mutate(Installed, filepath.Join(p.Stage, "manifest.json"), p.ManifestHash); e != nil {
		return e
	}
	j.Phase = "pending_health"
	return save()
}
func Commit(root string) error {
	d, e := checkedJournal(root)
	if e != nil {
		return e
	}
	var j Journal
	b, e := os.ReadFile(filepath.Join(d, "journal.json"))
	if e != nil {
		return e
	}
	if e = json.Unmarshal(b, &j); e != nil {
		return e
	}
	j.Phase = "committed"
	if e = atomicJSON(filepath.Join(d, "journal.json"), j); e != nil {
		return e
	}
	return os.RemoveAll(d)
}

// Recover resumes interrupted rollback; each backup replacement is atomic.
func Recover(root string) error {
	d, e := checkedJournal(root)
	if e != nil {
		return e
	}
	b, e := os.ReadFile(filepath.Join(d, "journal.json"))
	if os.IsNotExist(e) {
		if _, statErr := os.Stat(d); os.IsNotExist(statErr) {
			return nil
		}
		// No application files can have changed before the first journal save.
		// Only an empty directory or its unpublished initial journal is safe.
		entries, err := os.ReadDir(d)
		if err != nil {
			return err
		}
		for _, entry := range entries {
			if entry.Name() != "journal.json.new" || !entry.Type().IsRegular() {
				return errors.New("update journal is incomplete")
			}
		}
		return os.RemoveAll(d)
	}
	if e != nil {
		return e
	}
	var j Journal
	if e = json.Unmarshal(b, &j); e != nil {
		return e
	}
	if j.Phase == "committed" {
		return os.RemoveAll(d)
	}
	for i := len(j.Entries) - 1; i >= 0; i-- {
		entry := j.Entries[i]
		target, e := Safe(root, entry.Path)
		if e != nil {
			return e
		}
		backup := filepath.Join(d, "backup", filepath.FromSlash(entry.Path))
		if entry.Existed {
			if _, e = os.Stat(backup); os.IsNotExist(e) {
				continue
			} else if e != nil {
				return e
			}
			if e = replace(backup, target); e != nil {
				return e
			}
		} else if _, e = os.Stat(target); e == nil {
			h, e := Hash(target)
			if e != nil || h != entry.NewHash {
				return fmt.Errorf("new file changed during recovery: %s", entry.Path)
			}
			if e = os.Remove(target); e != nil {
				return e
			}
		}
	}
	return os.RemoveAll(d)
}

func Newer(next, current string) bool {
	a := strings.Split(next, ".")
	b := strings.Split(current, ".")
	if len(a) != 3 || len(b) != 3 {
		return false
	}
	for i := 0; i < 3; i++ {
		x, e := strconv.ParseUint(a[i], 10, 32)
		y, f := strconv.ParseUint(b[i], 10, 32)
		if e != nil || f != nil {
			return false
		}
		if x != y {
			return x > y
		}
	}
	return false
}
