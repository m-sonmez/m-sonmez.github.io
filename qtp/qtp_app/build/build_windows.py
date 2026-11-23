"""Windows tek dosya yürütülebilir paketleme betiği -> dist/qtp.exe (<= 60 MB)."""

from __future__ import annotations

import datetime as _dt
import hashlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
ROOT_DIR = BUILD_DIR.parent.parent
SPEC_PATH = BUILD_DIR / "qtp.spec"
DIST_DIR = ROOT_DIR / "dist"
MAX_SIZE_BYTES = 60 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_build_info(target: Path, digest: str) -> None:
    size_bytes = target.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    info = (
        "QTP Derleme Bilgisi (BUILD_INFO)\n"
        "===================================\n"
        f"Ana Bilgisayar (Host OS): {platform.system()} {platform.release()} ({sys.platform})\n"
        f"Mimari: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        f"Üretilen İkili Dosya: dist/{target.name}\n"
        f"Boyut: {size_bytes} bayt ({size_mb:.2f} MB)\n"
        f"SHA-256: {digest}\n"
        f"Derleme Zamanı: {stamp}\n\n"
        "Çapraz Derleme Notu:\n"
        "- Linux ve macOS için `dist/qtp.bin` ikili dosyası Windows üzerinde derlenmez (Wine kullanılmaz).\n"
        "- `qtp.bin` üretimi için ilgili yerel işletim sisteminde `python -m qtp_app.build.build_unix` veya `make build` çalıştırılmalıdır.\n"
    )
    (DIST_DIR / "BUILD_INFO.txt").write_text(info, encoding="utf-8")


def build_windows() -> Path:
    if sys.platform != "win32":
        raise RuntimeError("Windows ikili dosyası yalnızca Windows üzerinde derlenebilir.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT_DIR / "build" / "pyinstaller_win"),
        str(SPEC_PATH),
    ]
    print("PyInstaller çalıştırılıyor:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)

    built_exe = DIST_DIR / "QTP.exe"
    target_exe = DIST_DIR / "qtp.exe"
    if built_exe.is_file() and built_exe.name != target_exe.name:
        if built_exe.resolve() == target_exe.resolve():
            tmp_exe = DIST_DIR / "_qtp_tmp_rename.exe"
            if tmp_exe.exists():
                tmp_exe.unlink()
            built_exe.rename(tmp_exe)
            tmp_exe.rename(target_exe)
        else:
            if target_exe.exists():
                target_exe.unlink()
            shutil.move(str(built_exe), str(target_exe))

    if not target_exe.is_file():
        raise FileNotFoundError(f"Beklenen Windows çıktısı bulunamadı: {target_exe}")

    size_bytes = target_exe.stat().st_size
    if size_bytes > MAX_SIZE_BYTES:
        raise RuntimeError(
            f"Boyut sınırı aşıldı: {size_bytes / (1024 * 1024):.2f} MB > 60 MB"
        )

    print("Otomatik doğrulama çalıştırılıyor: qtp.exe --selftest")
    proc = subprocess.run(
        [str(target_exe), "--selftest"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    print(proc.stdout.strip())

    digest = sha256_file(target_exe)
    write_build_info(target_exe, digest)
    size_mb = size_bytes / (1024 * 1024)
    print(f"Derleme tamamlandı: {target_exe}")
    print(f"Boyut: {size_mb:.2f} MB ({size_bytes} bayt)")
    print(f"SHA-256: {digest}")
    return target_exe


if __name__ == "__main__":
    build_windows()
