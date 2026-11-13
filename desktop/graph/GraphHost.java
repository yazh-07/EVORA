// SPDX-License-Identifier: GPL-3.0-only
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;
import org.neo4j.dbms.api.DatabaseManagementService;
import org.neo4j.dbms.api.DatabaseManagementServiceBuilder;

/** Private database process. Parent death also runs the database shutdown hook. */
public final class GraphHost {
    public static void main(String[] args) throws Exception {
        Path home = Path.of(args[0]);
        Path config = Path.of(args[1]);
        Path stop = Path.of(args[2]);
        long parent = Long.parseLong(args[3]);
        long owner = args.length > 4 ? Long.parseLong(args[4]) : parent;
        var service = new AtomicReference<DatabaseManagementService>();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            var db = service.getAndSet(null);
            if (db != null) db.shutdown();
        }, "evora-graph-shutdown"));
        Thread watcher = new Thread(() -> {
            try {
                while (!Files.exists(stop) && ProcessHandle.of(parent).map(ProcessHandle::isAlive).orElse(false)
                        && ProcessHandle.of(owner).map(ProcessHandle::isAlive).orElse(false)) {
                    Thread.sleep(500);
                }
                System.exit(0);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }, "evora-parent-watch");
        watcher.setDaemon(true);
        watcher.start();
        service.set(new DatabaseManagementServiceBuilder(home).loadPropertiesFromFile(config).build());
        new CountDownLatch(1).await();
    }
}
