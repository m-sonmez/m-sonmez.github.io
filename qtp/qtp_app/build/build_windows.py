"""Windows tek dosya yürütülebilir paketleme betiği -> dist/qtp.exe."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
ROOT_DIR = BUILD_DIR.parent.parent
SPEC_PATH = BUILD_DIR / "qtp.spec"
DIST_DIR = ROOT_DIR / "dist"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
            # Büyük/küçük harf duyarsız NTFS üzerinde aynı dosya: geçici ad üzerinden yeniden adlandır
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

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    digest = sha256_file(target_exe)
    print(f"Derleme tamamlandı: {target_exe}")
    print(f"Boyut: {size_mb:.2f} MB ({target_exe.stat().st_size} bayt)")
    print(f"SHA-256: {digest}")
    return target_exe


if __name__ == "__main__":
    build_windows()
