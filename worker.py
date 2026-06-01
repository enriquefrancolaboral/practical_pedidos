import threading
import queue
import time
import subprocess
from sync_main import run_sincronizar

MONITOR_HOST     = "nodo-practical.nodosolutions.com"
MONITOR_INTERVAL = 1
TIMEOUT_REQUEST  = 5


class SyncWorker:
    def __init__(self):
        self.log_queue:     queue.Queue  = queue.Queue()
        self.latency_queue: queue.Queue  = queue.Queue()
        self._thread:       threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event:   threading.Event = threading.Event()
        self._reset_event:  threading.Event = threading.Event()
        self._lock:         threading.Lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.is_running():
                return
            self._stop_event.clear()
            self._reset_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self._monitor_thread = threading.Thread(target=self._monitor_red, daemon=True)
            self._monitor_thread.start()

    def stop(self):
        self._stop_event.set()

    def resume(self):
        self._stop_event.clear()

    def reset(self):
        with self._lock:
            self._reset_event.set()
            self._stop_event.clear()
            if self._thread and self._thread.is_alive():
                self._log("[INFO] Esperando a que el hilo principal termine.")
                self._thread.join(timeout=5.0)
                if self._thread.is_alive():
                    self._log("[WARN] El hilo principal no terminó en 5 segundos.")
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=2.0)
            self._thread = None
            self._monitor_thread = None
            self._reset_event.clear()
            self._stop_event.clear()
            for q in (self.log_queue, self.latency_queue):
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            self._log("[INFO] Worker reiniciado completamente.")

    def _run(self):
        try:
            run_sincronizar(
                log_fn=self._log,
                stop_event=self._stop_event,
                reset_event=self._reset_event,
            )
        except Exception as e:
            self._log(f"[ERROR CRÍTICO en worker] {e}")
        finally:
            self._log("__DONE__")

    def _monitor_red(self):
        import socket
        while self._thread is not None and self._thread.is_alive():
            if self._reset_event.is_set():
                break
            try:
                t = time.time()
                # Realizar un handshake socket rápido en puerto HTTPS (443)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((MONITOR_HOST, 443))
                s.close()
                latencia_ms = int((time.time() - t) * 1000)
                self.latency_queue.put(("ok", latencia_ms))
            except Exception:
                self.latency_queue.put(("sin_conexion", None))
            time.sleep(MONITOR_INTERVAL)

    def _log(self, message: str):
        self.log_queue.put(message)