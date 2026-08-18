"""Tkinter touchscreen dashboard.

Big, high-contrast tiles meant for a small (3.5"-7") RPi touchscreen: one
per check, color-coded by status, tap to see details. All the actual
checking happens on the Monitor's background thread; this just polls
`monitor.get_results()` on a Tk `after()` timer and redraws.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Any

from ..models import CheckResult, Status
from ..monitor import Monitor
from .formatting import format_detail_lines, format_last_checked, status_color, status_label

BG_DARK = "#121212"
CARD_BG = "#1e1e1e"
TEXT_LIGHT = "#eeeeee"
TEXT_MUTED = "#9e9e9e"


class Tile(tk.Frame):
    """One dashboard card for a single check."""

    def __init__(self, parent: tk.Widget, name: str, on_click):
        super().__init__(parent, bg=CARD_BG, highlightthickness=0, bd=0)
        self._on_click = on_click
        self.name = name

        title_font = tkfont.Font(family="Helvetica", size=14, weight="bold")
        summary_font = tkfont.Font(family="Helvetica", size=11)
        meta_font = tkfont.Font(family="Helvetica", size=9)

        self.status_dot = tk.Canvas(self, width=18, height=18, bg=CARD_BG, highlightthickness=0)
        self.status_dot.grid(row=0, column=0, padx=(12, 6), pady=(10, 0), sticky="nw")
        self._dot_id = self.status_dot.create_oval(2, 2, 16, 16, fill=status_color(Status.UNKNOWN), outline="")

        self.title_label = tk.Label(self, text=name, font=title_font, bg=CARD_BG, fg=TEXT_LIGHT, anchor="w")
        self.title_label.grid(row=0, column=1, padx=(0, 12), pady=(10, 0), sticky="w")

        self.summary_label = tk.Label(
            self, text="Checking...", font=summary_font, bg=CARD_BG, fg=TEXT_LIGHT,
            anchor="w", justify="left", wraplength=280,
        )
        self.summary_label.grid(row=1, column=0, columnspan=2, padx=12, pady=(4, 0), sticky="w")

        self.meta_label = tk.Label(self, text="", font=meta_font, bg=CARD_BG, fg=TEXT_MUTED, anchor="w")
        self.meta_label.grid(row=2, column=0, columnspan=2, padx=12, pady=(4, 10), sticky="w")

        self.grid_columnconfigure(1, weight=1)

        for widget in (self, self.title_label, self.summary_label, self.meta_label, self.status_dot):
            widget.bind("<Button-1>", lambda _e: self._on_click(self.name))

    def update_result(self, result: CheckResult) -> None:
        self.status_dot.itemconfig(self._dot_id, fill=status_color(result.status))
        self.summary_label.config(text=result.summary)
        self.meta_label.config(
            text=f"{status_label(result.status)} - updated {format_last_checked(result)}"
        )

    def mark_refreshing(self) -> None:
        """Immediate feedback for a manual refresh, before the new result
        for this check has actually come back from the background thread."""
        self.status_dot.itemconfig(self._dot_id, fill=status_color(Status.UNKNOWN))
        self.meta_label.config(text="Refreshing...")


class DetailWindow(tk.Toplevel):
    """Popup showing the full detail lines for one check."""

    def __init__(self, parent: tk.Widget, result: CheckResult):
        super().__init__(parent, bg=BG_DARK)
        self.title(result.name)
        self.geometry("460x400")
        self.configure(bg=BG_DARK)

        header = tk.Label(
            self, text=result.name, font=tkfont.Font(size=16, weight="bold"),
            bg=BG_DARK, fg=TEXT_LIGHT,
        )
        header.pack(anchor="w", padx=12, pady=(12, 4))

        text = tk.Text(self, bg=CARD_BG, fg=TEXT_LIGHT, wrap="word", relief="flat", padx=10, pady=10)
        text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        text.insert("1.0", "\n".join(format_detail_lines(result)))
        text.config(state="disabled")

        close_btn = tk.Button(self, text="Close", command=self.destroy, font=tkfont.Font(size=12))
        close_btn.pack(pady=(0, 12))


class DashboardApp(tk.Tk):
    def __init__(self, monitor: Monitor, ui_config: dict[str, Any] | None = None):
        super().__init__()
        self.monitor = monitor
        ui_config = ui_config or {}

        self.title("HomeDash")
        self.configure(bg=BG_DARK)
        if ui_config.get("fullscreen", True):
            self.attributes("-fullscreen", True)
        else:
            self.geometry("480x320")

        # Escape always exits fullscreen/kiosk mode - useful when developing
        # or if the touchscreen's a bind on a keyboard-attached Pi.
        self.bind("<Escape>", lambda _e: self._toggle_fullscreen())
        self.bind("<q>", lambda _e: self.destroy())

        self.poll_interval_ms = int(ui_config.get("poll_interval_seconds", 2) * 1000)

        self._tiles: dict[str, Tile] = {}
        self._build_layout()
        self.monitor.start()
        self.after(200, self._poll)

    def _toggle_fullscreen(self) -> None:
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

    def _build_header(self) -> None:
        # Fullscreen/kiosk mode has no window chrome, and a touchscreen has
        # no Esc key - so the on-screen close button is the only way to
        # quit on a touch-only setup.
        header = tk.Frame(self, bg=BG_DARK)
        header.pack(fill="x", padx=8, pady=8)

        title = tk.Label(
            header, text="HomeDash", font=tkfont.Font(family="Helvetica", size=16, weight="bold"),
            bg=BG_DARK, fg=TEXT_LIGHT,
        )
        title.pack(side="left")

        close_btn = tk.Button(
            header, text="✕", command=self.destroy,
            font=tkfont.Font(size=14, weight="bold"),
            bg="#c62828", fg="white", activebackground="#e53935", activeforeground="white",
            relief="flat", bd=0, width=3, height=1, cursor="hand2",
        )
        close_btn.pack(side="right")

        self.refresh_btn = tk.Button(
            header, text="↻", command=self._request_refresh,
            font=tkfont.Font(size=14, weight="bold"),
            bg="#1565c0", fg="white", activebackground="#1976d2", activeforeground="white",
            relief="flat", bd=0, width=3, height=1, cursor="hand2",
        )
        self.refresh_btn.pack(side="right", padx=(0, 8))

    def _build_layout(self) -> None:
        self._build_header()

        container = tk.Frame(self, bg=BG_DARK)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        for index, check in enumerate(self.monitor.checks):
            row, col = divmod(index, 2)
            container.grid_rowconfigure(row, weight=1)
            tile = Tile(container, check.name, on_click=self._open_detail)
            tile.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            self._tiles[check.name] = tile

    def _request_refresh(self) -> None:
        for tile in self._tiles.values():
            tile.mark_refreshing()
        self.monitor.request_refresh()

        # Brief cooldown so a flurry of taps doesn't look like nothing
        # happened - request_refresh() itself is idempotent either way.
        self.refresh_btn.config(state="disabled")
        self.after(2000, lambda: self.refresh_btn.config(state="normal"))

    def _open_detail(self, name: str) -> None:
        results = self.monitor.get_results()
        result = results.get(name)
        if result is not None:
            DetailWindow(self, result)

    def _poll(self) -> None:
        results = self.monitor.get_results()
        for name, tile in self._tiles.items():
            result = results.get(name)
            if result is not None:
                tile.update_result(result)
        self.after(self.poll_interval_ms, self._poll)

    def destroy(self) -> None:
        self.monitor.stop(timeout=1.0)
        super().destroy()
