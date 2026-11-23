"""Windows tek dosya yürütülebilir paketleme ve Authenticode imzalama betiği -> dist/qtp.exe (<= 60 MB)."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
ROOT_DIR = BUILD_DIR.parent.parent
QTP_ROOT = ROOT_DIR.parent
SPEC_PATH = BUILD_DIR / "qtp.spec"
SIGN_SCRIPT = BUILD_DIR / "sign_windows.ps1"
CERT_EXPORT_PATH = QTP_ROOT / "certs" / "MuratSonmez-QTP.cer"
DIST_DIR = ROOT_DIR / "dist"
MAX_SIZE_BYTES = 60 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_windows_binary(target: Path) -> dict[str, str]:
    """Windows yürütülebilir dosyasını CN=Murat Sönmez sertifikasıyla imzalar ve yalnızca ortak .cer dosyasını dışa aktarır."""
    shell_exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    cmd = [
        shell_exe,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SIGN_SCRIPT),
        "-ExePath",
        str(target),
        "-ExportCerPath",
        str(CERT_EXPORT_PATH),
    ]
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        cmd.append("-AllowUntrustedRoot")
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            parsed = json.loads(ln)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
    raise RuntimeError(f"İmzalama çıktısı ayrıştırılamadı: {proc.stdout}\n{proc.stderr}")


def write_build_info(
    target: Path,
    digest: str,
    *,
    target_os_note: str = "Windows 10 / 11 (x64)",
    sign_info: dict[str, str] | None = None,
) -> None:
    size_bytes = target.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    sig_block = ""
    if sign_info:
        sig_block = (
            f"Dijital İmza Durumu: {sign_info.get('Status', '')}\n"
            f"İmzalayıcı (Publisher): {sign_info.get('Subject', '')}\n"
            f"Sertifika Parmak İzi: {sign_info.get('Thumbprint', '')}\n"
            f"Zaman Damgası Sunucusu: {sign_info.get('TimestampServer', '')}\n"
        )
    info = (
        "QTP Derleme Bilgisi (BUILD_INFO)\n"
        "===================================\n"
        f"Ana Bilgisayar (Host OS): {platform.system()} {platform.release()} ({sys.platform})\n"
        f"Hedef Sistem: {target_os_note}\n"
        f"Mimari: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        f"Üretilen İkili Dosya: dist/{target.name}\n"
        f"Boyut: {size_bytes} bayt ({size_mb:.2f} MB)\n"
        f"SHA-256: {digest}\n"
        f"{sig_block}"
        f"Derleme Zamanı: {stamp}\n\n"
        "Çapraz Derleme Notu:\n"
        "- Linux, BSD ve macOS için `dist/qtp.bin` ikili dosyası Windows üzerinde derlenmez (Wine kullanılmaz).\n"
        "- Windows 7 / 8 / 8.1 x64 için `python -m qtp_app.build.build_windows_legacy` (Python 3.8 x64 + `requirements-win7.txt`) kullanılmalıdır.\n"
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

    print("Authenticode dijital imza uygulanıyor (CN=Murat Sönmez)...")
    sign_info = sign_windows_binary(target_exe)
    print(
        f"İmza doğrulandı: {sign_info.get('Subject')} | Durum={sign_info.get('Status')} | "
        f"Parmak İzi={sign_info.get('Thumbprint')} | Zaman Damgası={sign_info.get('TimestampServer')}"
    )

    size_bytes = target_exe.stat().st_size
    if size_bytes > MAX_SIZE_BYTES:
        raise RuntimeError(
            f"Boyut sınırı aşıldı: {size_bytes / (1024 * 1024):.2f} MB > 60 MB"
        )

    print("Otomatik doğrulama çalıştırılıyor (imzalı ikili): qtp.exe --selftest")
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
    write_build_info(target_exe, digest, sign_info=sign_info)
    size_mb = size_bytes / (1024 * 1024)
    print(f"Derleme tamamlandı: {target_exe}")
    print(f"Boyut: {size_mb:.2f} MB ({size_bytes} bayt)")
    print(f"SHA-256: {digest}")
    return target_exe


if __name__ == "__main__":
    build_windows()
