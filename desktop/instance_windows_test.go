package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestSecondLaunchActivatesExistingWorkstation(t *testing.T) {
	if database := os.Getenv("EVORA_TEST_INSTANCE_DATABASE"); database != "" {
		instance, err := acquireWorkstation(database)
		if err != nil {
			t.Fatal(err)
		}
		if instance != nil {
			t.Fatal("second process acquired the same workstation")
		}
		return
	}
	database := filepath.Join(t.TempDir(), "cases.sqlite3")
	instance, err := acquireWorkstation(database)
	if err != nil || instance == nil {
		t.Fatalf("first launch: %v", err)
	}
	ready := make(chan struct{}) // Keep the handler waiting so the test can inspect the event.
	go instance.serve(ready)
	defer instance.Close()
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command(exe, "-test.run=^TestSecondLaunchActivatesExistingWorkstation$")
	cmd.Env = append(os.Environ(), "EVORA_TEST_INSTANCE_DATABASE="+database)
	if output, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("second launch: %s %v", output, err)
	}
	result, _, _ := waitObject.Call(instance.event, 3000)
	if result != 0 {
		t.Fatal("existing workstation did not receive activation", result)
	}
	instance.Close()
	replacement, err := acquireWorkstation(database)
	if err != nil || replacement == nil {
		t.Fatalf("restart after exit: %v", err)
	}
	go replacement.serve(ready)
	replacement.Close()
}
