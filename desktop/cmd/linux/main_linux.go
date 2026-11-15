//go:build linux

// The Linux launcher owns the backend lifetime and the update restart handshake.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type options struct {
	Database, Storage, GraphMode, GraphData string
	Port                                    int
	NoBrowser                               bool
}

func defaultData() string {
	cwd, _ := os.Getwd()
	candidate := filepath.Join(cwd, "evora_data")
	if _, err := os.Stat(filepath.Join(candidate, "cases.sqlite3")); err == nil {
		return candidate
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "evora_data")
}
func parse(args []string) (options, error) {
	var o options
	data := defaultData()
	f := flag.NewFlagSet("evora", flag.ContinueOnError)
	f.StringVar(&o.Database, "database", filepath.Join(data, "cases.sqlite3"), "Case database")
	f.StringVar(&o.Storage, "storage", filepath.Join(data, "evidence_vault"), "Evidence folder")
	f.StringVar(&o.GraphMode, "graph-mode", "auto", "auto, bundled or external")
	f.StringVar(&o.GraphData, "graph-data", "", "Graph data folder")
	f.IntVar(&o.Port, "port", 8000, "Local port")
	f.BoolVar(&o.NoBrowser, "no-browser", false, "Start without opening the browser")
	if err := f.Parse(args); err != nil {
		return o, err
	}
	if f.NArg() != 0 {
		return o, errors.New("unexpected launcher arguments")
	}
	if o.Port < 1 || o.Port > 65535 {
		return o, errors.New("invalid local port")
	}
	if o.GraphMode != "auto" && o.GraphMode != "bundled" && o.GraphMode != "external" {
		return o, errors.New("invalid graph mode")
	}
	var err error
	o.Database, err = filepath.Abs(o.Database)
	if err != nil {
		return o, err
	}
	o.Storage, err = filepath.Abs(o.Storage)
	if err != nil {
		return o, err
	}
	if o.GraphData != "" {
		o.GraphData, err = filepath.Abs(o.GraphData)
	}
	return o, err
}
func (o options) args() []string {
	args := []string{"--database", o.Database, "--storage", o.Storage, "--port", strconv.Itoa(o.Port), "--graph-mode", o.GraphMode}
	if o.GraphData != "" {
		args = append(args, "--graph-data", o.GraphData)
	}
	if o.NoBrowser {
		args = append(args, "--no-browser")
	}
	return args
}
func outsideBackend(root, path string) bool {
	rel, err := filepath.Rel(filepath.Join(root, "backend"), path)
	return err == nil && (rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)))
}
func ready(url, expected string) bool {
	client := http.Client{Timeout: 500 * time.Millisecond}
	response, err := client.Get(url + "/api/v1/updates/health")
	if err != nil {
		return false
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return false
	}
	var value struct {
		Version string `json:"version"`
	}
	if json.NewDecoder(io.LimitReader(response.Body, 1024)).Decode(&value) != nil || value.Version == "" {
		return false
	}
	return expected == "" || value.Version == expected
}
func run(root string, o options) error {
	for _, path := range []string{o.Database, o.Storage, o.GraphData} {
		if path != "" && !outsideBackend(root, path) {
			return errors.New("keep case data outside the backend application folder")
		}
	}
	// Normal starts also take the update lock through recovery. A second launch
	// cannot start the backend while the helper is applying a pending transaction.
	if os.Getenv("EVORA_UPDATE_HEALTH_FILE") == "" {
		cmd := exec.Command(filepath.Join(root, "evora-updater"), "--recover", root)
		if err := cmd.Run(); err != nil {
			return errors.New("an update is running or recovery could not finish")
		}
	}
	lock, err := os.OpenFile(filepath.Join(root, ".evora-session.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return errors.New("EVORA is already running")
	}
	for _, path := range []string{filepath.Dir(o.Database), o.Storage} {
		if err = os.MkdirAll(path, 0700); err != nil {
			return err
		}
	}
	listener, err := net.Listen("tcp", net.JoinHostPort("127.0.0.1", strconv.Itoa(o.Port)))
	if err != nil {
		listener, err = net.Listen("tcp", "127.0.0.1:0")
	}
	if err != nil {
		return err
	}
	o.Port = listener.Addr().(*net.TCPAddr).Port
	_ = listener.Close()
	marker := filepath.Join(filepath.Dir(o.Database), fmt.Sprintf("stop-%d", os.Getpid()))
	_ = os.Remove(marker)
	_ = os.Remove(marker + ".update")
	defer os.Remove(marker)
	defer os.Remove(marker + ".update")
	log, err := os.OpenFile(filepath.Join(filepath.Dir(o.Database), "evora.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	defer log.Close()
	args := o.args()
	backendArgs := []string{}
	for _, arg := range args {
		if arg != "--no-browser" {
			backendArgs = append(backendArgs, arg)
		}
	}
	backendArgs = append(backendArgs, "--no-browser", "--shutdown-file", marker, "--parent-pid", strconv.Itoa(os.Getpid()))
	cmd := exec.Command(filepath.Join(root, "backend/evora"), backendArgs...)
	cmd.Dir = root
	cmd.Stdout = log
	cmd.Stderr = log
	encoded, _ := json.Marshal(args)
	cmd.Env = append(os.Environ(), "EVORA_UPDATE_LAUNCH_ARGS="+string(encoded))
	if err = cmd.Start(); err != nil {
		return err
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	stop := func() {
		_ = os.WriteFile(marker, []byte("stop\n"), 0600)
		select {
		case <-done:
		case <-time.After(60 * time.Second):
			_ = cmd.Process.Kill()
			<-done
		}
	}
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(signals)
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	url := fmt.Sprintf("http://127.0.0.1:%d", o.Port)
	expected := os.Getenv("EVORA_UPDATE_EXPECTED_VERSION")
	deadline := time.Now().Add(180 * time.Second)
	started := false
	for {
		select {
		case err := <-done:
			return err
		case <-signals:
			stop()
			return nil
		case <-ticker.C:
			if _, err := os.Stat(marker + ".update"); err == nil {
				stop()
				return nil
			}
			if !started && ready(url, expected) {
				started = true
				if health := os.Getenv("EVORA_UPDATE_HEALTH_FILE"); health != "" {
					// The file was created by the private helper; the version came from the
					// running backend rather than a version compiled into this launcher.
					data, _ := json.Marshal(map[string]string{"version": expected})
					if err = os.WriteFile(health, data, 0600); err != nil {
						stop()
						return err
					}
				}
				if !o.NoBrowser {
					browser := exec.Command("xdg-open", url)
					if browser.Start() == nil {
						go browser.Wait()
					}
				}
				fmt.Println("EVORA:", url)
			}
			if !started && time.Now().After(deadline) {
				stop()
				return errors.New("backend did not become ready; see evora.log")
			}
		}
	}
}
func main() {
	o, err := parse(os.Args[1:])
	if err == nil {
		var executable string
		executable, err = os.Executable()
		if err == nil {
			executable, err = filepath.EvalSymlinks(executable)
		}
		if err == nil {
			err = run(filepath.Dir(executable), o)
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "EVORA:", err)
		os.Exit(1)
	}
}
