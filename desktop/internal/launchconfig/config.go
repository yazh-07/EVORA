package launchconfig

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Preferences struct {
	NetworkAvailable bool `json:"network_available"`
	Port             int  `json:"port"`
	MinimizeToTray   bool `json:"minimize_to_tray"`
}

func Load(database string, defaultPort int) Preferences {
	defaults := Preferences{Port: defaultPort, MinimizeToTray: true}
	p := defaults
	b, e := os.ReadFile(filepath.Join(filepath.Dir(database), "launcher.json"))
	if e != nil {
		return defaults
	}
	if json.Unmarshal(b, &p) != nil || p.Port < 1 || p.Port > 65535 {
		return defaults
	}
	return p
}
