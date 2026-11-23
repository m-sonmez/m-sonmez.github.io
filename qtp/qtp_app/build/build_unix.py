"""Linux, BSD (Unix-benzeri) ve macOS tek dosya taşınabilir paketleme betiği -> dist/qtp.bin (<= 60 MB)."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import platform
import shutil
import stat
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
        "- Windows için `dist/qtp.exe` yalnızca Windows üzerinde derlenir.\n"
        "- Linux ikilisi maksimum uyumluluk için Ubuntu 22.04 (glibc 2.35) tabanında derlenmelidir.\n"
        "- macOS ikilisinde Mach-O/PKG bütünlüğü için `strip` uygulanmaz; ad-hoc `codesign` uygulanır.\n"
    )
    (DIST_DIR / "BUILD_INFO.txt").write_text(info, encoding="utf-8")


def build_unix(
    *,
    target_arch: str | None = None,
    macosx_deployment_target: str | None = None,
) -> Path:
    if sys.platform == "win32" or sys.platform.startswith("win"):
        raise RuntimeError(
            "Uyarı: Linux/BSD/macOS için qtp.bin derlemesi Windows üzerinde desteklenmiyor; Unix/macOS üzerinde çalıştırın."
        )

    build_env = dict(os.environ)
    if target_arch:
        build_env["QTP_TARGET_ARCH"] = target_arch
    if sys.platform == "darwin":
        deploy_target = macosx_deployment_target or build_env.get("MACOSX_DEPLOYMENT_TARGET") or "11.0"
        build_env["MACOSX_DEPLOYMENT_TARGET"] = deploy_target

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
    subprocess.run(cmd, cwd=str(ROOT_DIR), env=build_env, check=True)

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

    if sys.platform == "darwin":
        print("macOS ad-hoc kod imzalama uygulanıyor...")
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(target_bin)], check=True)

    size_bytes = target_bin.stat().st_size
    if size_bytes > MAX_SIZE_BYTES:
        raise RuntimeError(
            f"Boyut sınırı aşıldı: {size_bytes / (1024 * 1024):.2f} MB > 60 MB"
        )

    env = dict(os.environ)
    if sys.platform != "darwin" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
        env["QT_QPA_PLATFORM"] = "offscreen"

    print("Otomatik doğrulama çalıştırılıyor: ./dist/qtp.bin --selftest")
    for stale in list(DIST_DIR.iterdir()):
        if stale.resolve() != target_bin.resolve():
            if stale.is_dir():
                shutil.rmtree(stale)
            else:
                stale.unlink()

    dist_before = {p.name for p in DIST_DIR.iterdir()}
    proc = subprocess.run(
        [str(target_bin), "--selftest"],
        cwd=str(DIST_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=True,
    )
    print(proc.stdout.strip())
    dist_after = {p.name for p in DIST_DIR.iterdir()}
    stray = sorted(dist_after - dist_before)
    if stray:
        raise RuntimeError(f"--selftest sonrası dist/ içinde yan etki dosyası oluştu: {stray}")

    digest = sha256_file(target_bin)
    write_build_info(target_bin, digest)
    size_mb = size_bytes / (1024 * 1024)
    print(f"Derleme tamamlandı: {target_bin}")
    print(f"Boyut: {size_mb:.2f} MB ({size_bytes} bayt)")
    print(f"SHA-256: {digest}")
    return target_bin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QTP Unix/macOS/BSD tek dosya derleyicisi")
    parser.add_argument(
        "--target-arch",
        choices=("x86_64", "arm64", "universal2"),
        default=None,
    )
    parser.add_argument("--macosx-deployment-target", default=None)
    args = parser.parse_args(argv)
    build_unix(
        target_arch=args.target_arch,
        macosx_deployment_target=args.macosx_deployment_target,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
