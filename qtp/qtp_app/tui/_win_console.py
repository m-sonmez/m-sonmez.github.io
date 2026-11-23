"""Windows konsolu için sıfır bağımlılıklı ANSI/VT100 ve msvcrt tuş okuma katmanı."""

from __future__ import annotations

import ctypes
import shutil
import sys
from typing import TextIO

_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_STD_OUTPUT_HANDLE = -11


class WinConsoleBackend:
    """Windows CMD / PowerShell / Windows Terminal için harici paket gerektirmeyen TUI arka ucu."""

    def __init__(self, out_stream: TextIO | None = None):
        self.out: TextIO = out_stream if out_stream is not None else sys.stdout
        self._vt_enabled = False
        self._active = False

    def enter(self) -> None:
        if sys.platform == "win32":
            try:
                k32 = ctypes.windll.kernel32
                handle = k32.GetStdHandle(_STD_OUTPUT_HANDLE)
                mode = ctypes.c_uint32()
                if k32.GetConsoleMode(handle, ctypes.byref(mode)):
                    k32.SetConsoleMode(handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING)
                    self._vt_enabled = True
            except Exception:
                pass
        self._active = True
        self.out.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
        self.out.flush()

    def leave(self) -> None:
        if self._active:
            self.out.write("\x1b[?25h\x1b[?1049l\x1b[0m")
            self.out.flush()
            self._active = False

    def size(self) -> tuple[int, int]:
        ts = shutil.get_terminal_size((100, 30))
        return max(40, ts.columns), max(14, ts.lines)

    def render(self, ansi_lines: list[str]) -> None:
        buf = ["\x1b[H"]
        for line in ansi_lines:
            buf.append(line + "\x1b[K\r\n")
        buf.append("\x1b[J")
        self.out.write("".join(buf))
        self.out.flush()

    def read_key(self) -> str:
        """Tek tuşu standart TUI belirtecine çevirir ('UP', 'DOWN', 'ENTER', 'ESC', 'F1', ...)."""
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        if ch in ("\x08", "\x7f"):
            return "BACKSPACE"
        if ch == "\t":
            return "TAB"
        if ch == "\x03":
            return "ESC"
        if ch in ("\x00", "\xe0"):
            ext = msvcrt.getwch()
            ext_map = {
                "H": "UP",
                "P": "DOWN",
                "I": "PGUP",
                "Q": "PGDN",
                ";": "F1",
            }
            return ext_map.get(ext, "")
        return ch
