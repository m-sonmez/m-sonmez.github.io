#!/usr/bin/env python3
"""
QuickTextPaste & data.json Modern Yönetim Uygulaması (qtp_manager.py)
- Çift yönlü QuickTextPaste.ini <-> data.json içe/dışa aktarma (UTF-16 LE / UTF-8 / CP1254)
- Tüm [Program] ayarlarını ve ek INI bölümlerini kayıpsız koruma
- Çoklu seçme, çoklu düzenleme, çoklu içe/dışa aktarma, çoklu silme ve Geri Al (Undo)
- QuickTextPaste kurulum/başlatma/anlık INI uygulama + Web Full-Stack Panel köprüsü
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import qtp_core
from qtp_core import (
    build_qtp_ini,
    export_word_document,
    normalize_tr,
    parse_qtp_ini,
    read_text_auto,
    sanitize_label_part,
)


class BulkEditDialog(tk.Toplevel):
    def __init__(self, parent, selected_count: int, existing_groups: list[str]):
        super().__init__(parent)
        self.title(f"Toplu Düzenle ({selected_count} Seçili Kayıt)")
        self.geometry("500x430")
        self.resizable(False, False)
        self.configure(bg="#0f172a")
        self.transient(parent)
        self.grab_set()
        self.result = None

        pad = {"padx": 14, "pady": 6}
        tk.Label(
            self,
            text=f"Seçili {selected_count} kayıt üzerinde uygulanacak işlemleri işaretleyin:",
            bg="#0f172a", fg="#e2e8f0", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=14, pady=(14, 6))

        self.use_group = tk.BooleanVar()
        f1 = tk.Frame(self, bg="#1e293b", bd=0)
        f1.pack(fill="x", **pad)
        tk.Checkbutton(
            f1, text="Grubu Değiştir:", variable=self.use_group,
            bg="#1e293b", fg="#f8fafc", selectcolor="#334155", activebackground="#1e293b"
        ).pack(side="left", padx=8, pady=8)
        self.group_cb = ttk.Combobox(f1, values=existing_groups, width=32)
        self.group_cb.pack(side="right", padx=8, pady=8)

        self.use_keys = tk.BooleanVar()
        f2 = tk.Frame(self, bg="#1e293b")
        f2.pack(fill="x", **pad)
        tk.Checkbutton(
            f2, text="Kısayolu Değiştir:", variable=self.use_keys,
            bg="#1e293b", fg="#f8fafc", selectcolor="#334155", activebackground="#1e293b"
        ).pack(side="left", padx=8, pady=8)
        self.keys_ent = ttk.Entry(f2, width=35)
        self.keys_ent.insert(0, "L-Win+Z")
        self.keys_ent.pack(side="right", padx=8, pady=8)

        self.use_replace = tk.BooleanVar()
        f3 = tk.Frame(self, bg="#1e293b")
        f3.pack(fill="x", **pad)
        tk.Checkbutton(
            f3, text="Metinde Bul / Değiştir:", variable=self.use_replace,
            bg="#1e293b", fg="#f8fafc", selectcolor="#334155", activebackground="#1e293b"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        tk.Label(f3, text="Bul:", bg="#1e293b", fg="#94a3b8").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        self.find_ent = ttk.Entry(f3, width=38)
        self.find_ent.grid(row=1, column=1, sticky="e", padx=8, pady=4)
        tk.Label(f3, text="Değiştir:", bg="#1e293b", fg="#94a3b8").grid(row=2, column=0, sticky="w", padx=12, pady=(4, 8))
        self.repl_ent = ttk.Entry(f3, width=38)
        self.repl_ent.grid(row=2, column=1, sticky="e", padx=8, pady=(4, 8))

        self.use_affix = tk.BooleanVar()
        f4 = tk.Frame(self, bg="#1e293b")
        f4.pack(fill="x", **pad)
        tk.Checkbutton(
            f4, text="Metin Başına / Sonuna Ekle:", variable=self.use_affix,
            bg="#1e293b", fg="#f8fafc", selectcolor="#334155", activebackground="#1e293b"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        tk.Label(f4, text="Önek:", bg="#1e293b", fg="#94a3b8").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        self.prefix_ent = ttk.Entry(f4, width=38)
        self.prefix_ent.grid(row=1, column=1, sticky="e", padx=8, pady=4)
        tk.Label(f4, text="Sonek:", bg="#1e293b", fg="#94a3b8").grid(row=2, column=0, sticky="w", padx=12, pady=(4, 8))
        self.suffix_ent = ttk.Entry(f4, width=38)
        self.suffix_ent.grid(row=2, column=1, sticky="e", padx=8, pady=(4, 8))

        btn_bar = tk.Frame(self, bg="#0f172a")
        btn_bar.pack(fill="x", padx=14, pady=12)
        ttk.Button(btn_bar, text="İptal", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btn_bar, text="✅ Tüm Seçililere Uygula", style="Accent.TButton", command=self._apply).pack(side="right", padx=4)

    def _apply(self):
        if not any((self.use_group.get(), self.use_keys.get(), self.use_replace.get(), self.use_affix.get())):
            messagebox.showwarning("Uyarı", "En az bir düzenleme seçeneğini işaretleyin.", parent=self)
            return
        self.result = {
            "group": self.group_cb.get().strip() if self.use_group.get() else None,
            "keys": self.keys_ent.get().strip() if self.use_keys.get() else None,
            "replace": (self.find_ent.get(), self.repl_ent.get()) if self.use_replace.get() else None,
            "affix": (self.prefix_ent.get(), self.suffix_ent.get()) if self.use_affix.get() else None,
        }
        self.destroy()


class QTPManagerApp(tk.Tk):
    BG = "#0f172a"
    SURFACE = "#1e293b"
    SURFACE_ALT = "#263348"
    FG = "#f1f5f9"
    MUTED = "#94a3b8"
    ACCENT = "#4f46e5"
    ACCENT_HOVER = "#6366f1"
    DANGER = "#dc2626"
    SUCCESS = "#059669"

    def __init__(self):
        super().__init__()
        self.title("QuickTextPaste & Hazır Cevaplar Yöneticisi")
        self.geometry("1340x810")
        self.minsize(1060, 660)
        self.configure(bg=self.BG)

        cwd_dir = Path(".").resolve()
        parent_dir = Path(__file__).resolve().parent.parent
        if not (cwd_dir / "QuickTextPaste.ini").is_file() and (parent_dir / "QuickTextPaste.ini").is_file():
            self.work_dir = parent_dir
        else:
            self.work_dir = cwd_dir
        self.items: list[dict] = []
        self.program_meta: dict[str, str] = {}
        self.extra_sections: list[dict] = []
        self.filtered_indices: list[int] = []
        self.current_file: str | None = None
        self.undo_stack: list[list[dict]] = []
        self.dirty = False

        self._setup_styles()
        self._build_ui()
        self._bind_shortcuts()

        self._load_workspace_initial()
        self.after(250, self.refresh_qtp_status_async)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=self.BG, foreground=self.FG, font=("Segoe UI", 9.5))
        style.configure("Surface.TFrame", background=self.SURFACE)
        style.configure("TLabel", background=self.BG, foreground=self.FG)
        style.configure("Surface.TLabel", background=self.SURFACE, foreground=self.FG)
        style.configure("Muted.TLabel", background=self.SURFACE, foreground=self.MUTED, font=("Segoe UI", 8.5))

        style.configure(
            "TButton", background="#334155", foreground=self.FG,
            borderwidth=0, padding=(9, 5), font=("Segoe UI", 9, "bold")
        )
        style.map("TButton", background=[("active", "#475569"), ("disabled", "#1e293b")])

        style.configure("Accent.TButton", background=self.ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", self.ACCENT_HOVER)])

        style.configure("Success.TButton", background=self.SUCCESS, foreground="#ffffff")
        style.map("Success.TButton", background=[("active", "#10b981")])

        style.configure("Danger.TButton", background=self.DANGER, foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#ef4444")])

        style.configure(
            "TEntry", fieldbackground="#0f172a", foreground=self.FG,
            insertcolor=self.FG, bordercolor="#334155", lightcolor="#334155", darkcolor="#334155"
        )
        style.configure(
            "TCombobox", fieldbackground="#0f172a", foreground=self.FG,
            background="#334155", arrowcolor=self.FG
        )
        style.map("TCombobox", fieldbackground=[("readonly", "#0f172a")])

        style.configure(
            "Treeview", background="#0f172a", foreground=self.FG,
            fieldbackground="#0f172a", rowheight=30, borderwidth=0, font=("Segoe UI", 9.5)
        )
        style.configure(
            "Treeview.Heading", background=self.SURFACE, foreground="#c7d2fe",
            font=("Segoe UI", 9.5, "bold"), relief="flat", padding=(6, 6)
        )
        style.map("Treeview", background=[("selected", "#3730a3")], foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        top = tk.Frame(self, bg=self.SURFACE, height=54)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        tk.Label(
            top, text="⚡ QTP & Hazır Cevaplar Yöneticisi",
            bg=self.SURFACE, fg="#e0e7ff", font=("Segoe UI", 12, "bold")
        ).pack(side="left", padx=(14, 10))

        self.qtp_badge = tk.Label(
            top, text="⏳ QTP kontrol ediliyor...",
            bg="#334155", fg="#e2e8f0", font=("Segoe UI", 8.5, "bold"),
            padx=9, pady=4, cursor="hand2"
        )
        self.qtp_badge.pack(side="left", padx=4)
        self.qtp_badge.bind("<Button-1>", lambda _e: self.ensure_or_toggle_qtp())

        btn_specs = [
            ("📂 Dosya Aç", self.open_any_file, "TButton"),
            ("💾 Kaydet & Senkronize", self.save_synced, "Accent.TButton"),
            ("⚡ QTP Uygula", self.apply_and_reload_qtp, "Success.TButton"),
            ("📥 Çoklu İçe Aktar", self.import_multiple, "TButton"),
            ("📤 INI Dışa Aktar", lambda: self.export_ini(selected_only=False), "TButton"),
            ("📋 QTP Pano", lambda: self.copy_qtp_clipboard(selected_only=False), "TButton"),
            ("💾 Yedekler", self.open_backup_menu, "TButton"),
            ("📝 Word", lambda: self.export_docx(selected_only=False), "TButton"),
            ("🌐 Web Panel", self.open_web_panel, "TButton"),
        ]
        for label, cmd, st in reversed(btn_specs):
            ttk.Button(top, text=label, command=cmd, style=st).pack(side="right", padx=3, pady=10)

        flt = tk.Frame(self, bg=self.BG)
        flt.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(flt, text="🔍 Ara:", bg=self.BG, fg=self.MUTED).pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_tree())
        self.search_ent = ttk.Entry(flt, textvariable=self.search_var, width=32)
        self.search_ent.pack(side="left", padx=(0, 10))

        tk.Label(flt, text="Grup:", bg=self.BG, fg=self.MUTED).pack(side="left", padx=(0, 4))
        self.filter_group_var = tk.StringVar(value="Tümü")
        self.filter_group_cb = ttk.Combobox(flt, textvariable=self.filter_group_var, state="readonly", width=26)
        self.filter_group_cb.pack(side="left", padx=(0, 10))
        self.filter_group_cb.bind("<<ComboboxSelected>>", lambda *_: self.refresh_tree())

        tk.Label(flt, text="Kısayol:", bg=self.BG, fg=self.MUTED).pack(side="left", padx=(0, 4))
        self.filter_key_var = tk.StringVar(value="Tümü")
        self.filter_key_cb = ttk.Combobox(flt, textvariable=self.filter_key_var, state="readonly", width=13)
        self.filter_key_cb.pack(side="left", padx=(0, 10))
        self.filter_key_cb.bind("<<ComboboxSelected>>", lambda *_: self.refresh_tree())

        ttk.Button(flt, text="Temizle", command=self.clear_filters).pack(side="left", padx=(0, 6))
        ttk.Button(flt, text="🔄 INI'den Yenile", command=self.sync_from_disk_ini).pack(side="left", padx=(0, 6))
        ttk.Button(flt, text="📁 Grup Yeniden Adlandır", command=self.rename_group_dialog).pack(side="left")

        self.stats_lbl = tk.Label(flt, text="Toplam: 0 | Seçili: 0", bg=self.BG, fg="#a5b4fc", font=("Segoe UI", 9.5, "bold"))
        self.stats_lbl.pack(side="right")

        paned = tk.PanedWindow(self, orient="horizontal", bg=self.BG, sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12, pady=4)

        left = tk.Frame(paned, bg=self.SURFACE)
        paned.add(left, minsize=580)

        lbar = tk.Frame(left, bg=self.SURFACE)
        lbar.pack(fill="x", padx=8, pady=8)

        ttk.Button(lbar, text="➕ Yeni", command=self.add_item, style="Accent.TButton").pack(side="left", padx=2)
        ttk.Button(lbar, text="📑 Çoğalt", command=self.duplicate_selected).pack(side="left", padx=2)
        ttk.Button(lbar, text="✏️ Toplu Düzenle", command=self.bulk_edit_selected).pack(side="left", padx=2)
        ttk.Button(lbar, text="📤 Seçileni Dışa Aktar", command=self.export_selected_menu).pack(side="left", padx=2)
        ttk.Button(lbar, text="🗑️ Sil", command=self.delete_selected, style="Danger.TButton").pack(side="left", padx=2)
        ttk.Button(lbar, text="↩️ Geri Al", command=self.undo).pack(side="right", padx=2)
        ttk.Button(lbar, text="⬇️", width=3, command=lambda: self.move_selected(1)).pack(side="right", padx=2)
        ttk.Button(lbar, text="⬆️", width=3, command=lambda: self.move_selected(-1)).pack(side="right", padx=2)

        tree_wrap = tk.Frame(left, bg=self.SURFACE)
        tree_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("idx", "keys", "group", "label", "preview")
        self.tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("idx", text="#")
        self.tree.heading("keys", text="Kısayol")
        self.tree.heading("group", text="Grup")
        self.tree.heading("label", text="Başlık")
        self.tree.heading("preview", text="Metin Önizleme")

        self.tree.column("idx", width=40, anchor="center", stretch=False)
        self.tree.column("keys", width=95, anchor="center", stretch=False)
        self.tree.column("group", width=185, anchor="w")
        self.tree.column("label", width=175, anchor="w")
        self.tree.column("preview", width=280, anchor="w")

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        right = tk.Frame(paned, bg=self.SURFACE)
        paned.add(right, minsize=400)

        self.editor_title = tk.Label(
            right, text="📝 Kayıt Düzenleyici",
            bg=self.SURFACE, fg="#e0e7ff", font=("Segoe UI", 11, "bold")
        )
        self.editor_title.pack(anchor="w", padx=14, pady=(12, 4))

        self.multi_hint = tk.Label(
            right, text="Düzenlemek için listeden bir kayıt seçin.",
            bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8.5), wraplength=390, justify="left"
        )
        self.multi_hint.pack(anchor="w", padx=14, pady=(0, 8))

        form = tk.Frame(right, bg=self.SURFACE)
        form.pack(fill="both", expand=True, padx=14, pady=4)

        tk.Label(form, text="Kısayol (keys):", bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        hk_row = tk.Frame(form, bg=self.SURFACE)
        hk_row.pack(fill="x", pady=(2, 8))
        self.ed_keys = ttk.Entry(hk_row)
        self.ed_keys.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.mod_cb = ttk.Combobox(
            hk_row, state="readonly", width=10,
            values=["L-Win", "R-Win", "L-Ctrl", "R-Ctrl", "L-Alt", "R-Alt", "Ctrl+Alt", "Ctrl+Shift", "Alt+Shift", "Win+Alt"]
        )
        self.mod_cb.set("L-Win")
        self.mod_cb.pack(side="left", padx=2)
        self.key_cb = ttk.Combobox(
            hk_row, state="readonly", width=5,
            values=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") + [f"F{i}" for i in range(1, 13)]
        )
        self.key_cb.set("Z")
        self.key_cb.pack(side="left", padx=2)
        ttk.Button(hk_row, text="Ata", width=5, command=self._apply_hotkey_builder).pack(side="left", padx=(2, 0))

        tk.Label(form, text="Grup (group — alt menü için '/' kullanabilirsiniz):", bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        self.ed_group = ttk.Combobox(form)
        self.ed_group.pack(fill="x", pady=(2, 8))

        tk.Label(form, text="Kısa Başlık (QTP menü etiketi — opsiyonel):", bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        self.ed_label = ttk.Entry(form)
        self.ed_label.pack(fill="x", pady=(2, 8))

        tk.Label(form, text="Metin (text) — Çok satırlı destekli:", bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        chips = tk.Frame(form, bg=self.SURFACE)
        chips.pack(fill="x", pady=(2, 4))
        for tok in ["%LDF%", "%LTF%", "%pptxt%", "%send_enter%", "%send_tab%", "%TAB%", "%sleep_100%", "🍀", "🙏", "🌷", "🛵", "😊", "✔️", "💵"]:
            b = tk.Button(
                chips, text=tok, bg="#334155", fg="#f8fafc", relief="flat",
                font=("Segoe UI", 8), padx=4, pady=1, cursor="hand2",
                command=lambda t=tok: (self.ed_text.insert("insert", t), self._update_char_count())
            )
            b.pack(side="left", padx=1, pady=1)

        txt_wrap = tk.Frame(form, bg="#0f172a")
        txt_wrap.pack(fill="both", expand=True, pady=(2, 4))
        self.ed_text = tk.Text(
            txt_wrap, wrap="word", bg="#0f172a", fg=self.FG, insertbackground=self.FG,
            relief="flat", padx=8, pady=8, font=("Segoe UI", 10), height=10
        )
        tsb = ttk.Scrollbar(txt_wrap, orient="vertical", command=self.ed_text.yview)
        self.ed_text.configure(yscrollcommand=tsb.set)
        self.ed_text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        self.ed_text.bind("<KeyRelease>", lambda _e: self._update_char_count())

        self.char_count_lbl = tk.Label(form, text="0 / 4000 karakter", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 8))
        self.char_count_lbl.pack(anchor="e", pady=(0, 4))

        ed_btns = tk.Frame(right, bg=self.SURFACE)
        ed_btns.pack(fill="x", padx=14, pady=(4, 14))
        self.btn_apply_edit = ttk.Button(ed_btns, text="✅ Değişikliği Uygula", style="Accent.TButton", command=self.apply_single_edit)
        self.btn_apply_edit.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(ed_btns, text="📋 Metni Kopyala", command=self.copy_editor_text).pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar(value="Hazır • Ctrl+A: Tümünü Seç | Ctrl+S: Kaydet & Senkronize Et | Ctrl+Z: Geri Al | Ctrl+F: Ara")
        status = tk.Label(self, textvariable=self.status_var, bg="#020617", fg=self.MUTED, anchor="w", padx=12, pady=4, font=("Segoe UI", 8.5))
        status.pack(fill="x", side="bottom")

    def _bind_shortcuts(self):
        self.bind("<Control-s>", lambda e: self.save_synced())
        self.bind("<Control-z>", lambda e: self.undo() if self.focus_get() != self.ed_text else None)
        self.bind("<Control-f>", lambda e: (self.search_ent.focus_set(), self.search_ent.select_range(0, "end")))
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])
        self.tree.bind("<Delete>", lambda e: self.delete_selected())

    def refresh_qtp_status_async(self):
        def _worker():
            st = qtp_core.get_qtp_status(self.work_dir)
            self.after(0, lambda: self._apply_qtp_status_ui(st))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(8000, self.refresh_qtp_status_async)

    def _apply_qtp_status_ui(self, st: dict):
        if not st.get("is_windows"):
            self.qtp_badge.config(text=f"ℹ️ Platform: {st.get('platform')}", bg="#334155", fg="#cbd5e1")
            return
        if st.get("running"):
            pids = ", ".join(map(str, st.get("pids") or []))
            self.qtp_badge.config(text=f"🟢 QTP Çalışıyor (PID {pids})", bg="#065f46", fg="#d1fae5")
        elif st.get("installed"):
            self.qtp_badge.config(text="🟡 QTP Kurulu (Kapalı - Başlat)", bg="#92400e", fg="#fef3c7")
        else:
            self.qtp_badge.config(text="🔴 QTP Kurulu Değil (Kur)", bg="#991b1b", fg="#fee2e2")

    def ensure_or_toggle_qtp(self):
        st = qtp_core.get_qtp_status(self.work_dir)
        if not st.get("is_windows"):
            messagebox.showinfo("QuickTextPaste", "QuickTextPaste yalnızca Windows üzerinde çalışır. INI/JSON düzenleme tüm platformlarda aktiftir.")
            return
        if st.get("running"):
            if messagebox.askyesno("QuickTextPaste Çalışıyor", "QuickTextPaste şu anda çalışıyor.\nGüncel QuickTextPaste.ini ile yeniden başlatılsın mı?"):
                qtp_core.stop_quicktextpaste()
                qtp_core.start_quicktextpaste(self.work_dir, background=True, ensure_installed=True)
                self.refresh_qtp_status_async()
                self._set_status("QuickTextPaste yeniden başlatıldı.")
            return

        if not st.get("installed"):
            if not messagebox.askyesno(
                "QuickTextPaste Kurulumu",
                f"QuickTextPaste bulunamadı.\nResmi SoftwareOK adresinden otomatik indirilip kurulsun ve başlatılsın mı?\n\n{st['download_url']}"
            ):
                return
            self._set_status("QuickTextPaste indiriliyor...")
            self.update_idletasks()
            try:
                qtp_core.install_quicktextpaste(self.work_dir)
            except Exception as exc:
                messagebox.showerror("Kurulum Hatası", f"QuickTextPaste indirilemedi:\n{exc}")
                return

        res = qtp_core.start_quicktextpaste(self.work_dir, background=True, ensure_installed=False)
        self.refresh_qtp_status_async()
        if res.get("ok"):
            self._set_status("QuickTextPaste başlatıldı ve sistem tepsisinde çalışıyor.")
        else:
            messagebox.showerror("Başlatma Hatası", res.get("error", "QuickTextPaste başlatılamadı."))

    def apply_and_reload_qtp(self):
        if not self.items:
            messagebox.showinfo("Bilgi", "Uygulanacak kayıt bulunmuyor.")
            return
        st = qtp_core.get_qtp_status(self.work_dir)
        if st.get("is_windows") and not st.get("installed"):
            if messagebox.askyesno("QuickTextPaste Kurulu Değil", "QuickTextPaste bulunamadı. Otomatik indirip kurarak uygulamak ister misiniz?"):
                try:
                    qtp_core.install_quicktextpaste(self.work_dir)
                except Exception as exc:
                    messagebox.showerror("Kurulum Hatası", str(exc))
                    return
        res = qtp_core.save_state(
            self.work_dir,
            items=self.items,
            program=self.program_meta,
            extra_sections=self.extra_sections,
            create_backup_flag=True,
            backup_reason="gui_apply",
            reload_qtp=True,
            start_qtp_if_stopped=True,
        )
        self.dirty = False
        self.refresh_qtp_status_async()
        msg = f"{res['count']} kayıt data.json + QuickTextPaste.ini olarak kaydedildi"
        if res.get("qtp_restarted"):
            msg += " ve QuickTextPaste yeniden başlatıldı!"
        self._set_status(msg)
        messagebox.showinfo("QuickTextPaste Güncellendi", msg)

    def open_web_panel(self):
        url = "http://127.0.0.1:8765/"
        server_alive = False
        try:
            with urllib.request.urlopen(url + "api/health", timeout=0.6) as resp:
                server_alive = resp.status == 200
        except Exception:
            server_alive = False

        if not server_alive:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
            srv_script = Path(__file__).resolve().parent / "qtp_server.py"
            if not srv_script.is_file():
                srv_script = self.work_dir / "qtp_server.py"
            subprocess.Popen(
                [sys.executable, str(srv_script), "--work-dir", str(self.work_dir), "--ensure-qtp"],
                cwd=str(self.work_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags if os.name == "nt" else 0,
                start_new_session=(os.name != "nt"),
            )
            self.after(600, lambda: webbrowser.open(url))
            self._set_status(f"Full-Stack Web Panel başlatılıyor: {url}")
        else:
            webbrowser.open(url)
            self._set_status(f"Web Panel tarayıcıda açıldı: {url}")

    def _update_char_count(self):
        n = len(self.ed_text.get("1.0", "end-1c"))
        color = "#f87171" if n > 4000 else ("#fbbf24" if n > 3200 else self.MUTED)
        self.char_count_lbl.config(text=f"{n} / 4000 karakter", fg=color)

    def _push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.items))
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)
        self.dirty = True

    def undo(self):
        if not self.undo_stack:
            self._set_status("Geri alınacak işlem yok.")
            return
        self.items = self.undo_stack.pop()
        self.refresh_filters_and_tree()
        self._set_status("Son işlem geri alındı.")

    def _set_status(self, msg: str):
        file_info = f" [{Path(self.current_file).name}]" if self.current_file else ""
        star = "*" if self.dirty else ""
        self.title(f"QuickTextPaste & Hazır Cevaplar Yöneticisi{file_info}{star}")
        self.status_var.set(msg)

    def _existing_groups(self) -> list[str]:
        seen = []
        for it in self.items:
            g = it.get("group") or "Genel"
            if g not in seen:
                seen.append(g)
        return seen

    def refresh_filters_and_tree(self):
        groups = self._existing_groups()
        self.filter_group_cb["values"] = ["Tümü"] + groups
        self.ed_group["values"] = groups
        if self.filter_group_var.get() not in self.filter_group_cb["values"]:
            self.filter_group_var.set("Tümü")

        keys = []
        for it in self.items:
            k = it.get("keys", "")
            if k and k not in keys:
                keys.append(k)
        self.filter_key_cb["values"] = ["Tümü"] + keys
        if self.filter_key_var.get() not in self.filter_key_cb["values"]:
            self.filter_key_var.set("Tümü")

        self.refresh_tree()

    def clear_filters(self):
        self.search_var.set("")
        self.filter_group_var.set("Tümü")
        self.filter_key_var.set("Tümü")
        self.refresh_tree()

    def refresh_tree(self, select_indices: list[int] | None = None):
        self.tree.delete(*self.tree.get_children())
        self.filtered_indices.clear()

        q = normalize_tr(self.search_var.get().strip())
        terms = [t for t in q.split() if t]
        fg = self.filter_group_var.get()
        fk = self.filter_key_var.get()

        for idx, item in enumerate(self.items):
            grp = item.get("group") or "Genel"
            keys = item.get("keys") or ""
            lbl = item.get("label") or ""
            txt = item.get("text") or ""

            if fg != "Tümü" and grp != fg:
                continue
            if fk != "Tümü" and keys != fk:
                continue
            if terms:
                hay = normalize_tr(f"{keys} {grp} {lbl} {txt}")
                if not all(t in hay for t in terms):
                    continue

            self.filtered_indices.append(idx)
            preview = txt.replace("\n", " ↵ ")
            if len(preview) > 90:
                preview = preview[:90] + "..."
            self.tree.insert("", "end", iid=str(idx), values=(idx + 1, keys, grp, lbl, preview))

        if select_indices:
            valid = [str(i) for i in select_indices if self.tree.exists(str(i))]
            if valid:
                self.tree.selection_set(valid)
                self.tree.see(valid[0])
        self._update_selection_info()

    def _selected_item_indices(self) -> list[int]:
        return [int(iid) for iid in self.tree.selection()]

    def _update_selection_info(self):
        sel = self._selected_item_indices()
        self.stats_lbl.config(
            text=f"Toplam: {len(self.items)} | Görünen: {len(self.filtered_indices)} | Seçili: {len(sel)}"
        )

    def on_tree_select(self, _event=None):
        sel = self._selected_item_indices()
        self._update_selection_info()

        if len(sel) == 1:
            idx = sel[0]
            item = self.items[idx]
            self.editor_title.config(text=f"📝 Kayıt Düzenleyici (#{idx + 1})")
            self.multi_hint.config(text="Değişiklik yaptıktan sonra 'Değişikliği Uygula' butonuna tıklayın.")
            self.btn_apply_edit.state(["!disabled"])
            self.ed_keys.delete(0, "end")
            self.ed_keys.insert(0, item.get("keys", ""))
            self.ed_group.set(item.get("group", ""))
            self.ed_label.delete(0, "end")
            self.ed_label.insert(0, item.get("label", ""))
            self.ed_text.delete("1.0", "end")
            self.ed_text.insert("1.0", item.get("text", ""))
            self._update_char_count()
        elif len(sel) > 1:
            self.editor_title.config(text=f"📦 {len(sel)} Kayıt Seçili")
            self.multi_hint.config(
                text="Çoklu seçim aktif! Üstteki 'Toplu Düzenle', 'Seçileni Dışa Aktar' veya 'Sil' "
                     "butonlarıyla tüm seçili kayıtlara toplu işlem uygulayabilirsiniz."
            )
            self.btn_apply_edit.state(["disabled"])
        else:
            self.editor_title.config(text="📝 Kayıt Düzenleyici")
            self.multi_hint.config(text="Düzenlemek için listeden bir kayıt seçin.")
            self.btn_apply_edit.state(["disabled"])

    def _apply_hotkey_builder(self):
        combo = f"{self.mod_cb.get()}+{self.key_cb.get()}"
        self.ed_keys.delete(0, "end")
        self.ed_keys.insert(0, combo)

    def add_item(self):
        self._push_undo()
        default_grp = self.filter_group_var.get()
        if default_grp == "Tümü":
            default_grp = self._existing_groups()[0] if self.items else "Genel"
        new_item = {"keys": "L-Win+Z", "group": default_grp, "label": "Yeni Hazır Cevap", "text": ""}
        self.items.append(new_item)
        new_idx = len(self.items) - 1
        self.refresh_filters_and_tree()
        self.refresh_tree(select_indices=[new_idx])
        self.on_tree_select()
        self.ed_text.focus_set()
        self._set_status(f"Yeni kayıt eklendi (#{new_idx + 1}).")

    def apply_single_edit(self):
        sel = self._selected_item_indices()
        if len(sel) != 1:
            return
        idx = sel[0]
        text_val = self.ed_text.get("1.0", "end-1c")
        if not text_val.strip():
            if not messagebox.askyesno("Boş Metin", "Metin alanı boş. Yine de kaydedilsin mi?"):
                return
        self._push_undo()
        entry = {
            **{k: v for k, v in self.items[idx].items() if k in ("id", "favorite", "copyCount")},
            "keys": self.ed_keys.get().strip(),
            "group": self.ed_group.get().strip() or "Genel",
            "text": text_val,
        }
        lbl = self.ed_label.get().strip()
        if lbl:
            entry["label"] = lbl
        self.items[idx] = entry
        self.refresh_filters_and_tree()
        self.refresh_tree(select_indices=[idx])
        self._set_status(f"Kayıt #{idx + 1} güncellendi.")

    def duplicate_selected(self):
        sel = self._selected_item_indices()
        if not sel:
            return
        self._push_undo()
        new_indices = []
        offset = 0
        for idx in sorted(sel):
            clone = copy.deepcopy(self.items[idx + offset])
            clone.pop("id", None)
            if clone.get("label"):
                clone["label"] = f"{clone['label']} (Kopya)"
            self.items.insert(idx + offset + 1, clone)
            new_indices.append(idx + offset + 1)
            offset += 1
        self.refresh_filters_and_tree()
        self.refresh_tree(select_indices=new_indices)
        self._set_status(f"{len(sel)} kayıt çoğaltıldı.")

    def bulk_edit_selected(self):
        sel = self._selected_item_indices()
        if not sel:
            messagebox.showinfo("Bilgi", "Toplu düzenlemek için en az bir kayıt seçin.")
            return
        dlg = BulkEditDialog(self, len(sel), self._existing_groups())
        self.wait_window(dlg)
        if not dlg.result:
            return

        self._push_undo()
        res = dlg.result
        for idx in sel:
            it = self.items[idx]
            if res["group"]:
                it["group"] = res["group"]
            if res["keys"] is not None:
                it["keys"] = res["keys"]
            if res["replace"]:
                find_s, repl_s = res["replace"]
                if find_s:
                    it["text"] = it.get("text", "").replace(find_s, repl_s)
            if res["affix"]:
                pref, suff = res["affix"]
                it["text"] = f"{pref}{it.get('text', '')}{suff}"

        self.refresh_filters_and_tree()
        self.refresh_tree(select_indices=sel)
        self._set_status(f"{len(sel)} kayıt toplu olarak düzenlendi.")

    def rename_group_dialog(self):
        groups = self._existing_groups()
        if not groups:
            return
        cur_grp = self.filter_group_var.get()
        if cur_grp == "Tümü":
            cur_grp = groups[0]
        old_name = simpledialog.askstring("Grup Yeniden Adlandır", "Eski grup adı:", initialvalue=cur_grp, parent=self)
        if not old_name:
            return
        new_name = simpledialog.askstring("Grup Yeniden Adlandır", f"'{old_name}' için yeni grup adı:", initialvalue=old_name, parent=self)
        if not new_name or new_name.strip() == old_name:
            return
        self._push_undo()
        changed = 0
        for it in self.items:
            if (it.get("group") or "Genel") == old_name:
                it["group"] = new_name.strip()
                changed += 1
        self.refresh_filters_and_tree()
        self._set_status(f"'{old_name}' → '{new_name.strip()}' ({changed} kayıt güncellendi).")

    def delete_selected(self):
        sel = self._selected_item_indices()
        if not sel:
            return
        if not messagebox.askyesno("Toplu Silme Onayı", f"Seçili {len(sel)} kayıt silinsin mi?"):
            return
        self._push_undo()
        for idx in sorted(sel, reverse=True):
            self.items.pop(idx)
        self.refresh_filters_and_tree()
        self._set_status(f"{len(sel)} kayıt silindi. (Geri almak için Ctrl+Z)")

    def move_selected(self, direction: int):
        sel = sorted(self._selected_item_indices())
        if not sel:
            return
        if direction < 0 and sel[0] == 0:
            return
        if direction > 0 and sel[-1] == len(self.items) - 1:
            return
        self._push_undo()
        order = sel if direction < 0 else list(reversed(sel))
        new_sel = []
        for idx in order:
            target = idx + direction
            self.items[idx], self.items[target] = self.items[target], self.items[idx]
            new_sel.append(target)
        self.refresh_tree(select_indices=sorted(new_sel))

    def copy_editor_text(self):
        txt = self.ed_text.get("1.0", "end-1c")
        if txt:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self._set_status("Kayıt metni panoya kopyalandı.")

    def _load_workspace_initial(self):
        try:
            state = qtp_core.load_state(self.work_dir)
            if state["items"]:
                self.items = state["items"]
                self.program_meta = state.get("program") or {}
                self.extra_sections = state.get("extraSections") or []
                self.current_file = str(self.work_dir / ("QuickTextPaste.ini" if state["source"] == "QuickTextPaste.ini" else "data.json"))
                self.dirty = False
                self.refresh_filters_and_tree()
                self._set_status(f"Yüklendi: {state['source']} ({len(self.items)} kayıt)")
        except Exception as exc:
            self._set_status(f"Başlangıç yükleme uyarısı: {exc}")

    def sync_from_disk_ini(self):
        ini_path = self.work_dir / "QuickTextPaste.ini"
        if not ini_path.is_file():
            messagebox.showinfo("Bilgi", f"Çalışma klasöründe QuickTextPaste.ini bulunamadı:\n{ini_path}")
            return
        try:
            parsed = qtp_core.parse_qtp_ini_full(read_text_auto(ini_path))
            self._push_undo()
            self.items = parsed["items"]
            self.program_meta = parsed["program"]
            self.extra_sections = parsed["extra_sections"]
            self.dirty = False
            self.refresh_filters_and_tree()
            self._set_status(f"QuickTextPaste.ini diskten yenilendi ({len(self.items)} kayıt).")
        except Exception as exc:
            messagebox.showerror("Okuma Hatası", str(exc))

    def open_any_file(self):
        path = filedialog.askopenfilename(
            title="QuickTextPaste.ini, data.json veya Tam Yedek Aç",
            filetypes=[
                ("Desteklenen Dosyalar (*.ini, *.json)", "*.ini *.json"),
                ("QuickTextPaste INI", "*.ini"),
                ("JSON Dosyası", "*.json"),
                ("Tüm Dosyalar", "*.*"),
            ]
        )
        if not path:
            return
        try:
            parsed = qtp_core.parse_any_content(read_text_auto(path), filename=path)
            self._push_undo()
            self.items = parsed["items"]
            if parsed.get("program"):
                self.program_meta = parsed["program"]
            if parsed.get("extra_sections"):
                self.extra_sections = parsed["extra_sections"]
            self.current_file = path
            self.dirty = False
            self.refresh_filters_and_tree()
            self._set_status(f"Yüklendi: {path} ({len(self.items)} kayıt)")
        except Exception as exc:
            messagebox.showerror("Okuma Hatası", f"Dosya yüklenemedi:\n{exc}")

    def save_synced(self):
        """Hem data.json hem QuickTextPaste.ini dosyalarını senkronize olarak kaydeder."""
        try:
            res = qtp_core.save_state(
                self.work_dir,
                items=self.items,
                program=self.program_meta,
                extra_sections=self.extra_sections,
                create_backup_flag=True,
                backup_reason="gui_save",
                reload_qtp=False,
            )
            self.dirty = False
            self._set_status(f"Senkronize kaydedildi: data.json + QuickTextPaste.ini ({res['count']} kayıt)")
        except Exception as exc:
            messagebox.showerror("Kayıt Hatası", f"Kaydedilemedi:\n{exc}")

    def save_json(self, target_items: list[dict] | None = None, force_dialog: bool = False):
        items_to_save = qtp_core.strip_for_data_json(self.items if target_items is None else target_items)
        path = filedialog.asksaveasfilename(
            title="JSON Olarak Kaydet",
            defaultextension=".json",
            initialfile="data.json",
            filetypes=[("JSON Dosyası", "*.json")]
        )
        if not path:
            return
        try:
            qtp_core.atomic_write_text(path, json.dumps(items_to_save, ensure_ascii=False, indent=2) + "\n")
            self._set_status(f"JSON kaydedildi: {path} ({len(items_to_save)} kayıt)")
        except Exception as exc:
            messagebox.showerror("Kayıt Hatası", f"JSON yazılamadı:\n{exc}")

    def import_multiple(self):
        """Çoklu .ini ve .json (tam yedek dahil) dosyasını aynı anda içe aktarır."""
        paths = filedialog.askopenfilenames(
            title="Çoklu İçe Aktar (QuickTextPaste.ini ve/veya data.json)",
            filetypes=[
                ("Desteklenen Dosyalar (*.ini, *.json)", "*.ini *.json"),
                ("QuickTextPaste INI", "*.ini"),
                ("JSON Dosyası", "*.json"),
            ]
        )
        if not paths:
            return

        imported: list[dict] = []
        errors: list[str] = []
        merged_program: dict[str, str] = {}
        merged_extra: list[dict] = []

        for p in paths:
            try:
                parsed = qtp_core.parse_any_content(read_text_auto(p), filename=p)
                imported.extend(parsed["items"])
                if parsed.get("program"):
                    merged_program.update(parsed["program"])
                if parsed.get("extra_sections"):
                    merged_extra.extend(parsed["extra_sections"])
            except Exception as exc:
                errors.append(f"{os.path.basename(p)}: {exc}")

        if not imported:
            messagebox.showerror("İçe Aktarma Hatası", "Hiçbir geçerli kayıt okunamadı.\n" + "\n".join(errors))
            return

        replace_all = False
        skip_dups = True
        if self.items:
            dlg = tk.Toplevel(self)
            dlg.title("Çoklu İçe Aktarma Seçenekleri")
            dlg.geometry("440x240")
            dlg.resizable(False, False)
            dlg.configure(bg=self.BG)
            dlg.transient(self)
            dlg.grab_set()

            mode_var = tk.StringVar(value="merge")
            dup_var = tk.BooleanVar(value=True)
            confirmed = {"ok": False}

            tk.Label(
                dlg,
                text=f"{len(paths)} dosyadan toplam {len(imported)} kayıt okundu.",
                bg=self.BG, fg="#e0e7ff", font=("Segoe UI", 10, "bold")
            ).pack(anchor="w", padx=16, pady=(14, 8))

            box = tk.Frame(dlg, bg=self.SURFACE)
            box.pack(fill="x", padx=16, pady=4)

            tk.Radiobutton(
                box, text="Mevcut listenin sonuna ekle (Birleştir)", variable=mode_var, value="merge",
                bg=self.SURFACE, fg=self.FG, selectcolor="#334155", activebackground=self.SURFACE
            ).pack(anchor="w", padx=10, pady=(8, 4))

            tk.Radiobutton(
                box, text="Mevcut listenin yerine koy (Tümünü değiştir)", variable=mode_var, value="replace",
                bg=self.SURFACE, fg=self.FG, selectcolor="#334155", activebackground=self.SURFACE
            ).pack(anchor="w", padx=10, pady=(0, 8))

            tk.Checkbutton(
                dlg, text="Aynı metne sahip kopya kayıtları atla", variable=dup_var,
                bg=self.BG, fg=self.FG, selectcolor="#334155", activebackground=self.BG
            ).pack(anchor="w", padx=16, pady=(6, 10))

            def _confirm():
                confirmed["ok"] = True
                dlg.destroy()

            btns = tk.Frame(dlg, bg=self.BG)
            btns.pack(fill="x", padx=16, pady=(0, 12))
            ttk.Button(btns, text="İptal", command=dlg.destroy).pack(side="right", padx=4)
            ttk.Button(btns, text="✅ İçe Aktar", style="Accent.TButton", command=_confirm).pack(side="right", padx=4)

            self.wait_window(dlg)
            if not confirmed["ok"]:
                return

            replace_all = mode_var.get() == "replace"
            skip_dups = dup_var.get()

        self._push_undo()
        if replace_all:
            self.items = []
        if merged_program:
            self.program_meta.update(merged_program)
        if merged_extra:
            self.extra_sections = merged_extra

        existing_texts = {it.get("text", "").strip() for it in self.items}
        added = 0
        skipped = 0
        for item in imported:
            norm_txt = item.get("text", "").strip()
            if skip_dups and norm_txt in existing_texts:
                skipped += 1
                continue
            self.items.append(item)
            existing_texts.add(norm_txt)
            added += 1

        self.refresh_filters_and_tree()
        msg = f"{len(paths)} dosyadan {added} kayıt içe aktarıldı"
        if skipped:
            msg += f" ({skipped} tekrar atlandı)"
        if errors:
            msg += f" | Hatalı dosya: {len(errors)}"
            messagebox.showwarning("Kısmi Uyarı", "Bazı dosyalar okunamadı:\n" + "\n".join(errors))
        self._set_status(msg + ".")

    def _get_export_items(self, selected_only: bool) -> list[dict] | None:
        if selected_only:
            sel = sorted(self._selected_item_indices())
            if not sel:
                messagebox.showinfo("Bilgi", "Dışa aktarmak için listeden en az bir kayıt seçin.")
                return None
            return [self.items[i] for i in sel]
        if not self.items:
            messagebox.showinfo("Bilgi", "Dışa aktarılacak kayıt bulunmuyor.")
            return None
        return list(self.items)

    def export_ini(self, selected_only: bool = False):
        """QuickTextPaste.ini dışa aktarma (UTF-16 LE BOM / UTF-8 BOM + Türkçe dil desteği)."""
        target_items = self._get_export_items(selected_only)
        if not target_items:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"QuickTextPaste.ini Dışa Aktar ({len(target_items)} Kayıt)")
        dlg.geometry("460x275")
        dlg.resizable(False, False)
        dlg.configure(bg=self.BG)
        dlg.transient(self)
        dlg.grab_set()

        enc_var = tk.StringVar(value="utf-16-le-bom")
        tree_var = tk.BooleanVar(value=str(self.program_meta.get("m_show_tree", "1")) != "0")
        tr_prefs_var = tk.BooleanVar(value=True)
        confirmed = {"ok": False}

        tk.Label(
            dlg, text="Dosya Kodlaması ve QuickTextPaste Ayarları:",
            bg=self.BG, fg="#e0e7ff", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=16, pady=(14, 8))

        box = tk.Frame(dlg, bg=self.SURFACE)
        box.pack(fill="x", padx=16, pady=4)

        tk.Radiobutton(
            box, text="UTF-16 LE (BOM) — Windows Unicode Önerilen (Türkçe + Emoji)",
            variable=enc_var, value="utf-16-le-bom",
            bg=self.SURFACE, fg=self.FG, selectcolor="#334155", activebackground=self.SURFACE
        ).pack(anchor="w", padx=10, pady=(8, 4))

        tk.Radiobutton(
            box, text="UTF-8 (BOM) — Modern Metin Düzenleyiciler",
            variable=enc_var, value="utf-8-bom",
            bg=self.SURFACE, fg=self.FG, selectcolor="#334155", activebackground=self.SURFACE
        ).pack(anchor="w", padx=10, pady=(0, 8))

        tk.Checkbutton(
            dlg, text="Ağaç görünümünü etkinleştir (m_show_tree=1)", variable=tree_var,
            bg=self.BG, fg=self.FG, selectcolor="#334155", activebackground=self.BG
        ).pack(anchor="w", padx=16, pady=(8, 2))

        tk.Checkbutton(
            dlg, text="Türkçe arayüz (lng=21) ve sistem tepsisinde başlat (start_tray=1) ekle",
            variable=tr_prefs_var,
            bg=self.BG, fg=self.FG, selectcolor="#334155", activebackground=self.BG
        ).pack(anchor="w", padx=16, pady=(2, 12))

        def _ok():
            confirmed["ok"] = True
            dlg.destroy()

        btns = tk.Frame(dlg, bg=self.BG)
        btns.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Button(btns, text="İptal", command=dlg.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="📤 Kaydet...", style="Accent.TButton", command=_ok).pack(side="right", padx=4)

        self.wait_window(dlg)
        if not confirmed["ok"]:
            return

        path = filedialog.asksaveasfilename(
            title="QuickTextPaste.ini Olarak Kaydet",
            defaultextension=".ini",
            initialfile="QuickTextPaste.ini",
            filetypes=[("INI Dosyası", "*.ini"), ("Tüm Dosyalar", "*.*")]
        )
        if not path:
            return

        ini_text = build_qtp_ini(
            target_items,
            m_show_tree=1 if tree_var.get() else 0,
            include_program=True,
            program=self.program_meta,
            extra_sections=self.extra_sections,
            tr_prefs=tr_prefs_var.get(),
        )
        try:
            qtp_core.atomic_write_bytes(path, qtp_core.encode_qtp_ini(ini_text, encoding=enc_var.get()))
            self._set_status(f"QuickTextPaste.ini dışa aktarıldı: {path} ({len(target_items)} kayıt)")
            messagebox.showinfo(
                "Başarılı",
                f"{len(target_items)} kayıt QuickTextPaste.ini olarak kaydedildi:\n{path}\n\n"
                "Değişikliklerin hemen aktif olması için üstteki '⚡ QTP Uygula' butonunu da kullanabilirsiniz."
            )
        except Exception as exc:
            messagebox.showerror("Yazma Hatası", f"INI dosyası kaydedilemedi:\n{exc}")

    def copy_qtp_clipboard(self, selected_only: bool = False):
        target_items = self._get_export_items(selected_only)
        if not target_items:
            return
        ini_text = build_qtp_ini(
            target_items,
            m_show_tree=1,
            include_program=True,
            program=self.program_meta,
            extra_sections=self.extra_sections,
            tr_prefs=True,
        )
        self.clipboard_clear()
        self.clipboard_append(ini_text)
        self.update()
        self._set_status(f"{len(target_items)} kayıt QTP formatında panoya kopyalandı.")
        messagebox.showinfo(
            "Panoya Kopyalandı",
            f"{len(target_items)} kayıt QuickTextPaste formatında panoya kopyalandı.\n\n"
            "QuickTextPaste içinden:\n"
            "Seçenekler → Yedekleme → Panodan İçe Aktar\n"
            "(Options → Backup → Import from clipboard) yolunu kullanabilirsiniz."
        )

    def open_backup_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=self.SURFACE, fg=self.FG, activebackground=self.ACCENT)
        menu.add_command(label="📸 Anlık Yerel Disk Yedeği Al", command=self.create_disk_backup)
        menu.add_command(label="💾 Tam Yedek Dışa Aktar (qtp-tam-yedek.json)", command=self.export_full_backup)
        menu.add_separator()
        backups = qtp_core.list_backups(self.work_dir)
        if not backups:
            menu.add_command(label="(Henüz disk yedeği yok)", state="disabled")
        else:
            for b in backups[:10]:
                bid = b.get("id", "")
                cnt = b.get("count", 0)
                menu.add_command(
                    label=f"↩️ Geri Yükle: {bid} ({cnt} kayıt)",
                    command=lambda _id=bid: self.restore_disk_backup(_id)
                )
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def create_disk_backup(self):
        meta = qtp_core.create_backup(self.work_dir, reason="manual_gui")
        if meta:
            self._set_status(f"Yedek alındı: {meta['id']} ({meta['count']} kayıt)")
            messagebox.showinfo("Yedek Alındı", f"Yedek oluşturuldu:\nbackups/{meta['id']}")

    def restore_disk_backup(self, backup_id: str):
        if not messagebox.askyesno("Yedek Geri Yükleme", f"'{backup_id}' yedeği geri yüklensin mi?"):
            return
        try:
            res = qtp_core.restore_backup(self.work_dir, backup_id, reload_qtp=True)
            st = res["state"]
            self._push_undo()
            self.items = st["items"]
            self.program_meta = st.get("program") or {}
            self.extra_sections = st.get("extraSections") or []
            self.dirty = False
            self.refresh_filters_and_tree()
            self.refresh_qtp_status_async()
            self._set_status(f"Yedek geri yüklendi: {backup_id} ({len(self.items)} kayıt)")
        except Exception as exc:
            messagebox.showerror("Hata", str(exc))

    def export_full_backup(self):
        stamp = _dt.datetime.now().strftime("%Y-%m-%d")
        path = filedialog.asksaveasfilename(
            title="Tam Yedek Olarak Kaydet (Web PWA & Python Uyumlu)",
            defaultextension=".json",
            initialfile=f"qtp-tam-yedek-{stamp}.json",
            filetypes=[("JSON Dosyası", "*.json")]
        )
        if not path:
            return
        payload = {
            "type": "qtp-pwa-backup",
            "version": 2,
            "exportedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "settings": {"qtpPrefs": self.program_meta},
            "program": self.program_meta,
            "extraSections": self.extra_sections,
            "items": self.items,
        }
        qtp_core.atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        self._set_status(f"Tam yedek kaydedildi: {path}")

    def export_docx(self, selected_only: bool = False):
        target_items = self._get_export_items(selected_only)
        if not target_items:
            return
        path = filedialog.asksaveasfilename(
            title="Word Belgesi Olarak Dışa Aktar",
            defaultextension=".docx",
            initialfile="Hazır Cevaplar.docx",
            filetypes=[("Word Belgesi", "*.docx"), ("Word Uyumlu Belge", "*.doc")]
        )
        if not path:
            return
        try:
            _, info_msg = export_word_document(target_items, path)
            self._set_status(f"Word belgesi oluşturuldu ({len(target_items)} kayıt).")
            messagebox.showinfo("Word Dışa Aktarma", info_msg)
        except Exception as exc:
            messagebox.showerror("Hata", f"Word belgesi oluşturulamadı:\n{exc}")

    def export_selected_menu(self):
        sel = sorted(self._selected_item_indices())
        if not sel:
            messagebox.showinfo("Bilgi", "Dışa aktarmak için listeden en az bir kayıt seçin.")
            return
        count = len(sel)
        selected_items = [self.items[i] for i in sel]

        menu = tk.Menu(self, tearoff=0, bg=self.SURFACE, fg=self.FG, activebackground=self.ACCENT)
        menu.add_command(
            label=f"📄 Seçili {count} Kaydı JSON Olarak Kaydet (.json)",
            command=lambda: self.save_json(target_items=selected_items, force_dialog=True)
        )
        menu.add_command(
            label=f"⚙️ Seçili {count} Kaydı QuickTextPaste.ini Olarak Kaydet (.ini)",
            command=lambda: self.export_ini(selected_only=True)
        )
        menu.add_command(
            label=f"📋 Seçili {count} Kaydı QTP Panoya Kopyala",
            command=lambda: self.copy_qtp_clipboard(selected_only=True)
        )
        menu.add_separator()
        menu.add_command(
            label=f"📝 Seçili {count} Kaydı Word (.docx) Olarak Dışa Aktar",
            command=lambda: self.export_docx(selected_only=True)
        )
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def on_close(self):
        if self.dirty:
            ans = messagebox.askyesnocancel(
                "Kaydedilmemiş Değişiklikler",
                "Kaydedilmemiş değişiklikler var. Çıkmadan önce data.json ve QuickTextPaste.ini olarak kaydedilsin mi?"
            )
            if ans is None:
                return
            if ans:
                self.save_synced()
                if self.dirty:
                    return
        self.destroy()


if __name__ == "__main__":
    app = QTPManagerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
