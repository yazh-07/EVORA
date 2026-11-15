package main

import (
	"bufio"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

func TestSecondLaunchActivatesExistingWorkstation(t *testing.T) {
	if database := os.Getenv("EVORA_TEST_INSTANCE_DATABASE"); database != "" {
		instance, err := acquireWorkstation(database)
		if err != nil {
			t.Fatal(err)
		}
		if os.Getenv("EVORA_TEST_RELAUNCH") == "1" {
			if instance == nil {
				os.Stdout.WriteString("reused\n")
				return
			}
			os.Stdout.WriteString("owned\n")
			io.Copy(io.Discard, os.Stdin)
			os.Exit(0)
		}
		if os.Getenv("EVORA_TEST_EXPECT_OWNER") == "1" {
			if instance == nil {
				t.Fatal("launch during shutdown did not acquire ownership")
			}
			os.Exit(0)
		}
		if os.Getenv("EVORA_TEST_HOLD_INSTANCE") == "1" {
			if instance == nil {
				t.Fatal("holder failed to acquire workstation")
			}
			os.Stdout.WriteString("ready\n")
			io.Copy(io.Discard, os.Stdin)
			os.Exit(0)
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
	var group sync.WaitGroup
	for n := 0; n < 12; n++ {
		group.Add(1)
		go func() {
			defer group.Done()
			cmd := exec.Command(exe, "-test.run=^TestSecondLaunchActivatesExistingWorkstation$")
			cmd.Env = append(os.Environ(), "EVORA_TEST_INSTANCE_DATABASE="+database)
			if output, err := cmd.CombinedOutput(); err != nil {
				t.Errorf("concurrent launch: %s %v", output, err)
			}
		}()
	}
	group.Wait()
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

func TestCrashedWorkstationReleasesLock(t *testing.T) {
	exe, _ := os.Executable()
	database := filepath.Join(t.TempDir(), "cases.sqlite3")
	cmd := exec.Command(exe, "-test.run=^TestSecondLaunchActivatesExistingWorkstation$")
	cmd.Env = append(os.Environ(), "EVORA_TEST_INSTANCE_DATABASE="+database, "EVORA_TEST_HOLD_INSTANCE=1")
	output, _ := cmd.StdoutPipe()
	input, _ := cmd.StdinPipe()
	defer input.Close()
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { cmd.Process.Kill(); cmd.Wait() }()
	marker := make([]byte, 6)
	if _, err := io.ReadFull(output, marker); err != nil || string(marker) != "ready\n" {
		t.Fatalf("holder did not start: %q %v", marker, err)
	}
	if err := cmd.Process.Kill(); err != nil {
		t.Fatal(err)
	}
	cmd.Wait()
	instance, err := acquireWorkstation(database)
	if err != nil || instance == nil {
		t.Fatalf("crash left stale ownership: %v", err)
	}
	ready := make(chan struct{})
	go instance.serve(ready)
	instance.Close()
}

func TestLaunchDuringShutdownWaitsForPreviousOwner(t *testing.T) {
	database := filepath.Join(t.TempDir(), "cases.sqlite3")
	instance, err := acquireWorkstation(database)
	if err != nil || instance == nil {
		t.Fatalf("first owner: %v", err)
	}
	ready := make(chan struct{})
	go instance.serve(ready)
	defer instance.Close()
	instance.markClosing()
	exe, _ := os.Executable()
	cmd := exec.Command(exe, "-test.run=^TestSecondLaunchActivatesExistingWorkstation$")
	cmd.Env = append(os.Environ(), "EVORA_TEST_INSTANCE_DATABASE="+database, "EVORA_TEST_EXPECT_OWNER=1")
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer cmd.Process.Kill()
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case err := <-done:
		t.Fatalf("launch returned before shutdown finished: %v", err)
	case <-time.After(300 * time.Millisecond):
	}
	instance.Close()
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("launch did not resume after shutdown")
	}
}

func TestConcurrentRelaunchesDuringShutdownHaveOnlyOneNewOwner(t *testing.T) {
	database := filepath.Join(t.TempDir(), "cases.sqlite3")
	first, err := acquireWorkstation(database)
	if err != nil || first == nil {
		t.Fatalf("first launch: %v", err)
	}
	go first.serve(make(chan struct{}))
	defer first.Close()
	first.markClosing()
	exe, _ := os.Executable()
	results := make(chan string, 6)
	for n := 0; n < 6; n++ {
		cmd := exec.Command(exe, "-test.run=^TestSecondLaunchActivatesExistingWorkstation$")
		cmd.Env = append(os.Environ(), "EVORA_TEST_INSTANCE_DATABASE="+database, "EVORA_TEST_RELAUNCH=1")
		output, _ := cmd.StdoutPipe()
		input, _ := cmd.StdinPipe()
		if err := cmd.Start(); err != nil {
			t.Fatal(err)
		}
		defer func() { input.Close(); cmd.Process.Kill(); cmd.Wait() }()
		go func() {
			line, err := bufio.NewReader(output).ReadString('\n')
			if err != nil {
				results <- err.Error()
			} else {
				results <- line
			}
		}()
	}
	time.Sleep(300 * time.Millisecond)
	first.Close()
	owners := 0
	for n := 0; n < 6; n++ {
		select {
		case result := <-results:
			if result == "owned\n" {
				owners++
			} else if result != "reused\n" {
				t.Fatalf("unexpected launch result: %q", result)
			}
		case <-time.After(10 * time.Second):
			t.Fatal("relaunch remained blocked after another process took ownership")
		}
	}
	if owners != 1 {
		t.Fatalf("expected one replacement owner, got %d", owners)
	}
}
