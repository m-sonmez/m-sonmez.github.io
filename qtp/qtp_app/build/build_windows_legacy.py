"""Windows 7 / 8 / 8.1 x64 (Python 3.8 hedefi) tek dosya paketleme betiği -> dist/qtp-win7.exe."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from qtp_app.build.build_windows import DIST_DIR, MAX_SIZE_BYTES, ROOT_DIR, sha256_file, write_build_info

BUILD_DIR = Path(__file__).resolve().parent
LEGACY_SPEC_PATH = BUILD_DIR / "qtp_win7.spec"


def build_windows_legacy() -> Path:
    if sys.platform != "win32":
        raise RuntimeError("Windows 7/8 eski sürüm ikilisi yalnızca Windows üzerinde derlenebilir.")

    if sys.version_info >= (3, 9):
        print(
            "UYARI: Windows 7/8.1 x64 hedefi için Python 3.8 x64 + requirements-win7.txt önerilir "
            "(Python 3.9+ üst akışta Win7 çekirdek ABI desteğini kaldırmıştır)."
        )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT_DIR / "build" / "pyinstaller_win7"),
        str(LEGACY_SPEC_PATH),
    ]
    print("PyInstaller (Win7/8.1) çalıştırılıyor:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)

    target_exe = DIST_DIR / "qtp-win7.exe"
    if not target_exe.is_file():
        raise FileNotFoundError(f"Beklenen Windows 7 çıktısı bulunamadı: {target_exe}")

    size_bytes = target_exe.stat().st_size
    if size_bytes > MAX_SIZE_BYTES:
        raise RuntimeError(
            f"Boyut sınırı aşıldı: {size_bytes / (1024 * 1024):.2f} MB > 60 MB"
        )

    for stale in list(DIST_DIR.iterdir()):
        if stale.resolve() != target_exe.resolve():
            if stale.is_dir():
                shutil.rmtree(stale)
            else:
                stale.unlink()

    dist_before = {p.name for p in DIST_DIR.iterdir()}
    proc = subprocess.run(
        [str(target_exe), "--selftest"],
        cwd=str(DIST_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    print(proc.stdout.strip())
    dist_after = {p.name for p in DIST_DIR.iterdir()}
    stray = sorted(dist_after - dist_before)
    if stray:
        raise RuntimeError(f"--selftest sonrası dist/ içinde yan etki dosyası oluştu: {stray}")

    digest = sha256_file(target_exe)
    write_build_info(target_exe, digest, target_os_note="Windows 7 / 8 / 8.1 x64 (Python 3.8 hedefi)")
    print(f"Derleme tamamlandı: {target_exe} ({size_bytes / (1024 * 1024):.2f} MB)")
    return target_exe


if __name__ == "__main__":
    build_windows_legacy()
