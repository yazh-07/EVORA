// Synthetic backend used only by the native installer/uninstaller acceptance test.
package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	host := flag.String("host", "127.0.0.1", "")
	port := flag.Int("port", 8000, "")
	stop := flag.String("shutdown-file", "", "")
	flag.Bool("no-browser", false, "")
	flag.String("database", "", "")
	flag.String("storage", "", "")
	flag.Int("parent-pid", 0, "")
	flag.Parse()
	server := &http.Server{Addr: fmt.Sprintf("%s:%d", *host, *port), Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("synthetic backend ready")) })}
	go func() {
		for {
			if _, err := os.Stat(*stop); err == nil {
				server.Shutdown(context.Background())
				return
			}
			time.Sleep(50 * time.Millisecond)
		}
	}()
	server.ListenAndServe()
}
