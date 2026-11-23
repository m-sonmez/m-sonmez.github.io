"""Windows konsolu (Win7–11) için sıfır bağımlılıklı VT100/Win32 Console API ve msvcrt tuş katmanı."""

from __future__ import annotations

import ctypes
import re
import shutil
import sys
from typing import Any, TextIO

_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
_STD_OUTPUT_HANDLE = -11
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class _COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int16), ("Y", ctypes.c_int16)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_int16),
        ("Top", ctypes.c_int16),
        ("Right", ctypes.c_int16),
        ("Bottom", ctypes.c_int16),
    ]


class _CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", _COORD),
        ("dwCursorPosition", _COORD),
        ("wAttributes", ctypes.c_uint16),
        ("srWindow", _SMALL_RECT),
        ("dwMaximumWindowSize", _COORD),
    ]


def _configure_kernel32(k32: Any) -> Any:
    k32.GetStdHandle.argtypes = [ctypes.c_int32]
    k32.GetStdHandle.restype = ctypes.c_void_p
    k32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    k32.GetConsoleMode.restype = ctypes.c_int
    k32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.SetConsoleMode.restype = ctypes.c_int
    k32.GetConsoleScreenBufferInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFO),
    ]
    k32.GetConsoleScreenBufferInfo.restype = ctypes.c_int
    k32.FillConsoleOutputCharacterW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar,
        ctypes.c_uint32,
        _COORD,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    k32.FillConsoleOutputCharacterW.restype = ctypes.c_int
    k32.FillConsoleOutputAttribute.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint16,
        ctypes.c_uint32,
        _COORD,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    k32.FillConsoleOutputAttribute.restype = ctypes.c_int
    k32.SetConsoleCursorPosition.argtypes = [ctypes.c_void_p, _COORD]
    k32.SetConsoleCursorPosition.restype = ctypes.c_int
    k32.SetConsoleTextAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
    k32.SetConsoleTextAttribute.restype = ctypes.c_int
    return k32


class WinConsoleBackend:
    """Windows 7–11 CMD / PowerShell / Windows Terminal için harici paket gerektirmeyen TUI arka ucu."""

    def __init__(self, out_stream: TextIO | None = None):
        self.out: TextIO = out_stream if out_stream is not None else sys.stdout
        self._vt_enabled = False
        self._active = False
        self._handle: Any = None
        self._k32: Any = None
        self._orig_attrs: int = 7

    @property
    def supports_ansi(self) -> bool:
        return self._vt_enabled

    def _resolve_kernel32(self) -> Any:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return None
        k32 = getattr(windll, "kernel32", None)
        if k32 is None:
            return None
        try:
            return _configure_kernel32(k32)
        except Exception:
            return k32

    def _win32_clear_screen(self) -> None:
        if self._k32 is None or not self._handle:
            return
        try:
            csbi = _CONSOLE_SCREEN_BUFFER_INFO()
            cols, rows = self.size()
            attrs = self._orig_attrs
            if self._k32.GetConsoleScreenBufferInfo(self._handle, ctypes.byref(csbi)):
                if csbi.dwSize.X > 0 and csbi.dwSize.Y > 0:
                    cols = int(csbi.dwSize.X)
                    rows = int(csbi.dwSize.Y)
                if csbi.wAttributes:
                    attrs = int(csbi.wAttributes)
            cells = max(1, cols * rows)
            origin = _COORD(0, 0)
            written = ctypes.c_uint32(0)
            self._k32.FillConsoleOutputCharacterW(self._handle, " ", cells, origin, ctypes.byref(written))
            self._k32.FillConsoleOutputAttribute(self._handle, attrs, cells, origin, ctypes.byref(written))
            self._k32.SetConsoleCursorPosition(self._handle, origin)
        except Exception:
            pass

    def enter(self) -> None:
        self._vt_enabled = False
        self._handle = None
        self._k32 = self._resolve_kernel32()
        if self._k32 is not None:
            try:
                handle = self._k32.GetStdHandle(_STD_OUTPUT_HANDLE)
                invalid_handle = ctypes.c_void_p(-1).value
                if handle not in (None, 0, invalid_handle):
                    self._handle = handle
                    csbi = _CONSOLE_SCREEN_BUFFER_INFO()
                    if self._k32.GetConsoleScreenBufferInfo(handle, ctypes.byref(csbi)):
                        if csbi.wAttributes:
                            self._orig_attrs = int(csbi.wAttributes)
                    mode = ctypes.c_uint32()
                    if self._k32.GetConsoleMode(handle, ctypes.byref(mode)):
                        if self._k32.SetConsoleMode(handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING):
                            self._vt_enabled = True
            except Exception:
                self._vt_enabled = False
        self._active = True
        if self._vt_enabled:
            self.out.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
            self.out.flush()
        else:
            self._win32_clear_screen()

    def leave(self) -> None:
        if self._active:
            if self._vt_enabled:
                self.out.write("\x1b[?25h\x1b[?1049l\x1b[0m")
                self.out.flush()
            else:
                if self._k32 is not None and self._handle:
                    try:
                        self._k32.SetConsoleTextAttribute(self._handle, self._orig_attrs)
                    except Exception:
                        pass
                    self._win32_clear_screen()
            self._active = False

    def size(self) -> tuple[int, int]:
        ts = shutil.get_terminal_size((100, 30))
        return max(40, ts.columns), max(14, ts.lines)

    def render(self, lines: list[str]) -> None:
        if self._vt_enabled:
            buf = ["\x1b[H"]
            for line in lines:
                buf.append(line + "\x1b[K\r\n")
            buf.append("\x1b[J")
            self.out.write("".join(buf))
            self.out.flush()
            return

        cols, _rows = self.size()
        if self._k32 is not None and self._handle:
            try:
                self._k32.SetConsoleCursorPosition(self._handle, _COORD(0, 0))
            except Exception:
                pass

        for line in lines:
            clean = _ANSI_ESCAPE_RE.sub("", line)
            padded = clean[: cols - 1].ljust(max(1, cols - 1))
            if self._k32 is not None and self._handle and clean.startswith("> "):
                try:
                    self._k32.SetConsoleTextAttribute(self._handle, 0x1F)
                    self.out.write(padded + "\r\n")
                    self.out.flush()
                    self._k32.SetConsoleTextAttribute(self._handle, self._orig_attrs)
                    continue
                except Exception:
                    pass
            self.out.write(padded + "\r\n")
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
