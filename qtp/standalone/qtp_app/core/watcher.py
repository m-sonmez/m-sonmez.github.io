"""Harici yapılandırma ve veri dosyası değişikliklerini (INI / JSON / ayarlar) canlı algılayan izleyici."""

from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator


@dataclass(frozen=True)
class FileChange:
    """Algılanan tek dosya değişimi olayı."""

    kind: str
    path: Path
    exists: bool


@dataclass
class ReloadEvent:
    """Canlı otomatik yenileme sonrası motor ve arayüz adaptörlerine iletilen özet."""

    settings_changed: bool = False
    hotkeys_changed: bool = False
    theme_changed: bool = False
    window_size_changed: bool = False
    data_path_changed: bool = False
    items_changed: bool = False
    log_level_changed: bool = False
    tray_changed: bool = False
    auto_reload_changed: bool = False
    item_count: int = 0
    source: str = ""
    warning: str | None = None


def compute_file_fingerprint(
    path: Path,
    cached: tuple[bool, int, int, str] | None = None,
) -> tuple[bool, int, int, str]:
    """Dosya varlığı, mtime_ns, boyut ve SHA-256 özetinden deterministik parmak izi döndürür."""
    try:
        if not path.is_file():
            return (False, 0, 0, "")
        st = path.stat()
        mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
        size = int(st.st_size)
        if cached is not None and cached[0] and cached[1] == mtime_ns and cached[2] == size and cached[3]:
            return cached
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return (True, mtime_ns, size, h.hexdigest())
    except OSError:
        return (False, 0, 0, "")


class ConfigFileWatcher:
    """
    qtp_settings.json, QuickTextPaste.ini ve data.json dosyalarını sıfır bağımlılıkla izler.
    Atomik os.replace() yazımlarını, debounce süresini ve QTP içi kendi yazımlarını güvenle yönetir.
    """

    def __init__(
        self,
        targets: dict[str, Path],
        on_change: Callable[[list[FileChange]], None],
        *,
        interval_ms: int = 500,
        debounce_ms: int = 250,
    ):
        self._on_change = on_change
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._interval_ms = max(100, min(10000, int(interval_ms)))
        self._debounce_ms = max(50, min(2000, int(debounce_ms)))
        self._targets: dict[str, Path] = {}
        self._fingerprints: dict[str, tuple[bool, int, int, str]] = {}
        self._suppressed: dict[Path, tuple[tuple[bool, int, int, str], float]] = {}
        self._active_internal_paths: set[Path] = set()
        self._pending: dict[str, FileChange] = {}
        self._last_change_ts: float = 0.0
        self.update_paths(targets)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def targets(self) -> dict[str, Path]:
        with self._lock:
            return dict(self._targets)

    def set_interval(self, interval_ms: int) -> None:
        with self._lock:
            self._interval_ms = max(100, min(10000, int(interval_ms)))

    def update_paths(self, targets: dict[str, Path]) -> None:
        with self._lock:
            resolved = {k: Path(v).resolve() for k, v in targets.items() if v is not None}
            new_fps: dict[str, tuple[bool, int, int, str]] = {}
            for k, p in resolved.items():
                if k in self._targets and self._targets[k] == p and k in self._fingerprints:
                    new_fps[k] = self._fingerprints[k]
                else:
                    new_fps[k] = compute_file_fingerprint(p)
            self._targets = resolved
            self._fingerprints = new_fps
            for stale_kind in [k for k in self._pending if k not in resolved]:
                self._pending.pop(stale_kind, None)

    def mark_internal_write(self, path: str | Path) -> None:
        resolved = Path(path).resolve()
        fp = compute_file_fingerprint(resolved)
        now = time.monotonic()
        with self._lock:
            self._suppressed[resolved] = (fp, now + 5.0)
            for kind, target_path in self._targets.items():
                if target_path == resolved:
                    self._fingerprints[kind] = fp
                    self._pending.pop(kind, None)

    @contextmanager
    def suppress_write(self, path: str | Path) -> Iterator[None]:
        resolved = Path(path).resolve()
        with self._lock:
            self._active_internal_paths.add(resolved)
        try:
            yield
        finally:
            self.mark_internal_write(resolved)
            with self._lock:
                self._active_internal_paths.discard(resolved)

    def start(self) -> None:
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            for k, p in self._targets.items():
                self._fingerprints[k] = compute_file_fingerprint(p)
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="qtp-config-watcher")
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        th = self._thread
        if th is not None and th is not threading.current_thread():
            th.join(timeout=timeout)
        with self._lock:
            self._thread = None
            self._pending.clear()

    def poll_once(self) -> list[FileChange]:
        """Tek bir kontrol adımı yürütür ve bekleme süresi (debounce) dolduğunda değişimleri döndürür."""
        now = time.monotonic()
        ready: list[FileChange] = []
        with self._lock:
            expired = [p for p, (_fp, exp) in self._suppressed.items() if exp < now]
            for p in expired:
                self._suppressed.pop(p, None)

            for kind, path in list(self._targets.items()):
                if path in self._active_internal_paths:
                    continue
                old_fp = self._fingerprints.get(kind)
                new_fp = compute_file_fingerprint(path, cached=old_fp)
                if old_fp is None:
                    self._fingerprints[kind] = new_fp
                    continue
                if new_fp != old_fp:
                    sup = self._suppressed.get(path)
                    if sup is not None and sup[0] == new_fp:
                        self._fingerprints[kind] = new_fp
                        self._suppressed.pop(path, None)
                        continue
                    self._fingerprints[kind] = new_fp
                    self._pending[kind] = FileChange(kind=kind, path=path, exists=new_fp[0])
                    self._last_change_ts = now

            if self._pending and (now - self._last_change_ts) >= (self._debounce_ms / 1000.0):
                ready = list(self._pending.values())
                self._pending.clear()
        return ready

    def _run_loop(self) -> None:
        last_scan = 0.0
        while not self._stop_event.is_set():
            now = time.monotonic()
            with self._lock:
                interval_s = self._interval_ms / 1000.0
                has_pending = bool(self._pending)
            effective_wait = min(0.08, interval_s) if has_pending else min(0.15, interval_s)
            if has_pending or (now - last_scan) >= interval_s:
                last_scan = now
                ready = self.poll_once()
                if ready:
                    try:
                        self._on_change(ready)
                    except Exception:
                        pass
            self._stop_event.wait(effective_wait)
