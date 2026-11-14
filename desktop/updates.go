package main

import (
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/energye/systray"
)

var updateExit = make(chan struct{})

func recoverApplicationUpdate() bool {
	root, e := os.Executable()
	if e != nil {
		return false
	}
	root = filepath.Dir(root)
	if os.Getenv("EVORA_UPDATE_HEALTH_FILE") != "" {
		return true
	}
	if _, e = os.Stat(filepath.Join(root, ".evora-update-journal")); os.IsNotExist(e) {
		return true
	}
	cmd := exec.Command(filepath.Join(root, "evora-updater.exe"), "--recover", root)
	hideWindow(cmd)
	return cmd.Run() == nil
}
func watchApplicationUpdate() {
	marker := backendMgr.stopPath + ".update"
	for {
		time.Sleep(250 * time.Millisecond)
		if _, e := os.Stat(marker); e != nil {
			continue
		}
		_ = os.Remove(marker)
		backendMgr.Stop()
		if wvWindow != nil {
			wvWindow.Dispatch(func() { wvWindow.Terminate() })
		}
		systray.Quit()
		close(updateExit)
		return
	}
}
func markApplicationHealthy() {
	path, expected := os.Getenv("EVORA_UPDATE_HEALTH_FILE"), os.Getenv("EVORA_UPDATE_EXPECTED_VERSION")
	if path == "" || expected == "" {
		return
	}
	client := http.Client{Timeout: 3 * time.Second}
	response, e := client.Get(backendMgr.url + "/api/v1/updates/health")
	if e != nil {
		return
	}
	defer response.Body.Close()
	var value struct {
		Version string `json:"version"`
	}
	if json.NewDecoder(response.Body).Decode(&value) != nil || value.Version != expected {
		return
	}
	data, _ := json.Marshal(value)
	_ = os.WriteFile(path, data, 0600)
}
