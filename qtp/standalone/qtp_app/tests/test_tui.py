"""TUI sütun genişliği hesaplama, Unicode/emoji kırpma, dar ekran ve ESCDELAY testleri."""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest import mock

from qtp_app.core.engine import QtpEngine
from qtp_app.tui.app import QtpTui, clip_to_width, display_width, run_tui

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_display_width_and_clip_to_width_wide_emojis():
    assert display_width("") == 0
    assert display_width("merhaba") == 7
    assert display_width("şğıöç") == 5
    assert display_width("😊a") == 3
    assert display_width("e\u0301") == 1

    assert clip_to_width("abc", 5) == "abc"
    clipped_emoji = clip_to_width("abc😊def", 6)
    assert clipped_emoji == "abc😊…"
    assert display_width(clipped_emoji) == 6
    assert clip_to_width("abc😊def", 5) == "abc…"
    assert clip_to_width("abc😊def", 0) == ""


def test_tui_clips_every_line_and_compacts_narrow_categories(tmp_path: Path):
    work = tmp_path / "tui_width"
    work.mkdir()
    eng = QtpEngine(work_dir=work)
    eng.op_add_item("🚀" * 50 + " çok uzun mesaj satırı", keys="L-Win+A", group="Genel", label="Uzun")

    for width in (50, 80, 100):
        tui = QtpTui(eng, term_size=(width, 20), use_color=True)
        plain = tui.render_plain_lines()
        for line in plain:
            assert display_width(line) <= width, f"width={width} satır taştı ({display_width(line)}): {line!r}"
        ansi = tui.render_ansi_lines()
        for line in ansi:
            stripped = _ANSI_RE.sub("", line)
            assert display_width(stripped) <= width

        if width < 100:
            assert "Tümü(" in plain[1]
            assert "A(" in plain[1]
            assert "Q(" in plain[1]


def test_tui_sets_escdelay_and_handles_curses_resize(tmp_path: Path, monkeypatch):
    work = tmp_path / "tui_curses"
    work.mkdir()
    eng = QtpEngine(work_dir=work)
    monkeypatch.delenv("ESCDELAY", raising=False)

    fake_stdin = mock.Mock()
    fake_stdin.isatty.return_value = True

    class FakeScreen:
        def __init__(self):
            self.calls = 0

        def keypad(self, _flag: bool) -> None:
            pass

        def getmaxyx(self) -> tuple[int, int]:
            return (24, 80)

        def erase(self) -> None:
            pass

        def addnstr(self, _row: int, _col: int, txt: str, _n: int) -> None:
            assert display_width(txt) <= 79

        def refresh(self) -> None:
            pass

        def get_wch(self):
            self.calls += 1
            if self.calls == 1:
                return 410
            return "q"

    fake_curses = mock.Mock()
    fake_curses.KEY_RESIZE = 410
    fake_curses.KEY_ENTER = 10
    fake_curses.KEY_UP = 259
    fake_curses.KEY_DOWN = 258
    fake_curses.KEY_PPAGE = 339
    fake_curses.KEY_NPAGE = 338
    fake_curses.KEY_F1 = 265
    fake_curses.KEY_BACKSPACE = 263

    def _fake_wrapper(loop_fn):
        assert os.environ.get("ESCDELAY") == "25"
        loop_fn(FakeScreen())

    fake_curses.wrapper.side_effect = _fake_wrapper

    with mock.patch("qtp_app.tui.app.sys.platform", "linux"), \
         mock.patch("qtp_app.tui.app.sys.stdin", fake_stdin), \
         mock.patch.dict("sys.modules", {"curses": fake_curses}):
        rc = run_tui(eng)
    assert rc == 0
