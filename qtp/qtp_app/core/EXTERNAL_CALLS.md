# QTP Harici Çağrı Denetimi (EXTERNAL_CALLS)

Bu belge, `qtp_app/` içindeki tüm dış süreç (`subprocess.run`, `subprocess.Popen`) ve yürütülebilir dosya (`shutil.which`) çağrılarının sıfır çalışma zamanı bağımlılığı denetimini listeler.

| Modül | Çağrı / Sembol | Amaç | Sınıf | Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| `qtp_app/core/engine.py` | `subprocess.run(["git", "rev-parse", "--short", "HEAD"])` | `--version` çıktısına varsa kısa Git SHA eklemek | `optional` | Yalnızca geliştirme deposunda mevcutsa kullanılır; hata durumunda sessizce atlanır. |
| `qtp_app/core/paster.py` | `shutil.which("wtype")` / `subprocess.run([wtype, ...])` | Linux Wayland üzerinde yapay `Ctrl+V` / `Enter` basımı | `optional` | Yalnızca Linux Wayland oturumunda ve `wtype` kuruluysa çağrılır; yoksa `SSS.md` ile uyumlu uyarı basar ve çıkış kodu `4` döner. |
| `qtp_app/core/paster.py` | `shutil.which("ydotool")` / `subprocess.run([ydotool, ...])` | Wayland üzerinde `wtype` yoksa alternatif tuş basımı | `optional` | Yalnızca Linux Wayland oturumunda ve `ydotool` kuruluysa çağrılır. |
| `qtp_app/core/paster.py` | `shutil.which("pbcopy")` / `subprocess.run([pbcopy])` | macOS üzerinde AppKit başarısız olursa son çare pano | `os-stock` | Yalnızca macOS üzerinde yerleşik `/usr/bin/pbcopy` için son yedek yol; zorunlu değildir. |
| `qtp_app/core/paster.py` | `subprocess.run(["osascript", ...])` | macOS üzerinde `NSWorkspace` başarısız olursa ön uygulama odak geri yüklemesi | `os-stock` | Yalnızca macOS üzerinde yerleşik sistem aracı için yedek yol. |
| `qtp_app/core/paster.py` | `import pyperclip` (`try/except ImportError`) | Pano için en son isteğe bağlı Python geri dönüşü | `optional` | `ImportError` yakalanır; Windows `ctypes` ve Linux X11/Qt/OSC-52 önce çalışır. |
| `qtp_app/build/build_windows.py` | `subprocess.run([sys.executable, "-m", "PyInstaller", ...])` | Derleme zamanı Windows tek dosya paketleme | `build-only` | Çalışma zamanı ikilisinde çalıştırılmaz. |
| `qtp_app/build/build_unix.py` | `subprocess.run(["strip", ...])` / `codesign` | Derleme zamanı Unix küçültme ve macOS imzalama | `build-only` | Çalışma zamanı ikilisinde çalıştırılmaz. |
| `qtp_app/core/hotkeys.py` | Win32 `RegisterHotKey` / `UnregisterHotKey` (`ctypes`) | Windows 7–11 üzerinde sıfır bağımlılıklı, tuş tüketen yerel global kısayol kaydı | `os-stock` | Yalnızca Windows stok `user32.dll` / `kernel32.dll` API'leri kullanır; Linux/macOS'ta `pynput` devreye girer. |
| **Yasaklanmış Harici Çağrılar** | `xclip`, `xsel`, `xdotool`, `wmctrl`, `win32clipboard`, `QuickTextPaste.exe` | — | `forbidden — none` | **Hiçbiri çalışma zamanında kullanılmaz.** |
