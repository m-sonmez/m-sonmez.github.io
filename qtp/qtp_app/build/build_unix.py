"""Linux ve macOS tek dosya taşınabilir paketleme betiği -> dist/qtp.bin."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
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


def build_unix() -> Path:
    if sys.platform == "win32":
        raise RuntimeError(
            "Uyarı: Linux/macOS için qtp.bin derlemesi Windows üzerinde desteklenmiyor; Linux veya macOS üzerinde çalıştırın."
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
        str(ROOT_DIR / "build" / "pyinstaller_unix"),
        str(SPEC_PATH),
    ]
    print("PyInstaller çalıştırılıyor:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)

    built_bin = DIST_DIR / "QTP"
    target_bin = DIST_DIR / "qtp.bin"
    if built_bin.is_file() and built_bin.name != target_bin.name:
        if built_bin.resolve() == target_bin.resolve():
            tmp_bin = DIST_DIR / "_qtp_tmp_rename.bin"
            if tmp_bin.exists():
                tmp_bin.unlink()
            built_bin.rename(tmp_bin)
            tmp_bin.rename(target_bin)
        else:
            if target_bin.exists():
                target_bin.unlink()
            shutil.move(str(built_bin), str(target_bin))

    if not target_bin.is_file():
        raise FileNotFoundError(f"Beklenen Unix çıktısı bulunamadı: {target_bin}")

    mode = target_bin.stat().st_mode
    target_bin.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    strip_tool = shutil.which("strip")
    if strip_tool and sys.platform.startswith("linux"):
        subprocess.run([strip_tool, str(target_bin)], check=False)

    if sys.platform == "darwin":
        print("macOS ad-hoc kod imzalama uygulanıyor...")
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(target_bin)], check=True)

    env = dict(os.environ)
    if sys.platform.startswith("linux") and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
        env["QT_QPA_PLATFORM"] = "offscreen"

    print("Otomatik doğrulama çalıştırılıyor: ./dist/qtp.bin --selftest")
    proc = subprocess.run(
        [str(target_bin), "--selftest"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=True,
    )
    print(proc.stdout.strip())

    size_mb = target_bin.stat().st_size / (1024 * 1024)
    digest = sha256_file(target_bin)
    print(f"Derleme tamamlandı: {target_bin}")
    print(f"Boyut: {size_mb:.2f} MB ({target_bin.stat().st_size} bayt)")
    print(f"SHA-256: {digest}")
    return target_bin


if __name__ == "__main__":
    build_unix()
