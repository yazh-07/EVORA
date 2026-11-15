package launchconfig

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultsAndSavedPreferences(t *testing.T) {
	db := filepath.Join(t.TempDir(), "cases.sqlite3")
	p := Load(db, 8123)
	if p.Port != 8123 || p.NetworkAvailable || !p.MinimizeToTray {
		t.Fatal(p)
	}
	path := filepath.Join(filepath.Dir(db), "launcher.json")
	if err := os.WriteFile(path, []byte(`{"port":8999,"network_available":true,"minimize_to_tray":false}`), 0600); err != nil {
		t.Fatal(err)
	}
	p = Load(db, 8123)
	if p.Port != 8999 || !p.NetworkAvailable || p.MinimizeToTray {
		t.Fatal(p)
	}
	_ = os.WriteFile(path, []byte(`{"port":0,"network_available":true}`), 0600)
	p = Load(db, 8123)
	if p.Port != 8123 || p.NetworkAvailable || !p.MinimizeToTray {
		t.Fatal("invalid settings must fail closed", p)
	}
}
