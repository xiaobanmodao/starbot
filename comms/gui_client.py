from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from core.session_controller import SessionController


class StarbotGuiClient(tk.Tk):
    """Local desktop chat client for Starbot (GUI shell only, core logic unchanged)."""

    def __init__(self, controller: SessionController | None = None):
        super().__init__()
        self.controller = controller or SessionController()
        self._busy = False
        self._closed = False
        self._chat_images: list[ImageTk.PhotoImage] = []
        self._build_window()
        self._build_style()
        self._build_layout()
        self.after(80, self._pump_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _build_window(self):
        self.title("Starbot Client")
        self.geometry("1180x760")
        self.minsize(940, 620)

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#f4f7fb"
        panel = "#ffffff"
        ink = "#142033"
        muted = "#66738a"
        border = "#d8e0ea"
        accent = "#1f6feb"

        self._colors = {
            "bg": bg,
            "panel": panel,
            "ink": ink,
            "muted": muted,
            "border": border,
            "accent": accent,
            "user_bg": "#e9f2ff",
            "assistant_bg": "#f7fbff",
            "system_bg": "#f6f7f9",
            "event_bg": "#fbfcfe",
        }

        self.configure(bg=bg)

        style.configure("App.TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel, borderwidth=1, relief="solid")
        style.configure("TLabel", background=bg, foreground=ink, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=bg, foreground=ink, font=("Segoe UI Semibold", 15))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10))
        style.map(
            "Primary.TButton",
            foreground=[("disabled", "#9aa4b2")],
        )

        # Text widgets are classic tk widgets; style them manually.
        self.option_add("*Text.Font", ("Consolas", 10))
        self.option_add("*Text.Background", panel)
        self.option_add("*Text.Foreground", ink)
        self.option_add("*Text.BorderWidth", 0)
        self.option_add("*Text.HighlightThickness", 0)

    def _build_layout(self):
        root = ttk.Frame(self, style="App.TFrame", padding=14)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Starbot Local Client", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Discord mode is still preserved and available",
            style="Muted.TLabel",
        ).pack(side="left", padx=(12, 0))

        toolbar = ttk.Frame(root, style="App.TFrame")
        toolbar.pack(fill="x", pady=(10, 10))
        self.btn_new = ttk.Button(toolbar, text="New Session", command=self._on_new_session)
        self.btn_new.pack(side="left")
        self.btn_stop = ttk.Button(toolbar, text="Stop", command=self._on_stop)
        self.btn_stop.pack(side="left", padx=(8, 0))
        self.btn_setup = ttk.Button(toolbar, text="Setup Wizard", command=self._on_setup)
        self.btn_setup.pack(side="left", padx=(8, 0))
        self.btn_clear = ttk.Button(toolbar, text="Clear View", command=self._on_clear_view)
        self.btn_clear.pack(side="left", padx=(8, 0))
        self._mode_label = ttk.Label(toolbar, text=self._model_label_text(), style="Muted.TLabel")
        self._mode_label.pack(side="right")

        paned = ttk.Panedwindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left_panel = ttk.Frame(paned, style="Panel.TFrame", padding=8)
        right_panel = ttk.Frame(paned, style="Panel.TFrame", padding=8)
        paned.add(left_panel, weight=4)
        paned.add(right_panel, weight=2)

        # Chat panel
        ttk.Label(left_panel, text="Conversation", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        chat_wrap = ttk.Frame(left_panel, style="Panel.TFrame")
        chat_wrap.pack(fill="both", expand=True)
        self.chat_text = tk.Text(chat_wrap, wrap="word")
        self.chat_text.pack(side="left", fill="both", expand=True)
        chat_scroll = ttk.Scrollbar(chat_wrap, orient="vertical", command=self.chat_text.yview)
        chat_scroll.pack(side="right", fill="y")
        self.chat_text.configure(yscrollcommand=chat_scroll.set, state="disabled")
        self._configure_chat_tags()

        # Event panel
        ttk.Label(right_panel, text="Run Log", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        event_wrap = ttk.Frame(right_panel, style="Panel.TFrame")
        event_wrap.pack(fill="both", expand=True)
        self.event_text = tk.Text(
            event_wrap,
            wrap="word",
            background=self._colors["event_bg"],
            foreground=self._colors["ink"],
        )
        self.event_text.pack(side="left", fill="both", expand=True)
        event_scroll = ttk.Scrollbar(event_wrap, orient="vertical", command=self.event_text.yview)
        event_scroll.pack(side="right", fill="y")
        self.event_text.configure(yscrollcommand=event_scroll.set, state="disabled")
        self._configure_event_tags()

        # Input row
        input_panel = ttk.Frame(root, style="Panel.TFrame", padding=10)
        input_panel.pack(fill="x", pady=(10, 0))
        ttk.Label(input_panel, text="Message", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.input_text = tk.Text(input_panel, height=4, wrap="word")
        self.input_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.input_text.bind("<Control-Return>", self._on_send_shortcut)
        self.input_text.bind("<Command-Return>", self._on_send_shortcut)
        input_scroll = ttk.Scrollbar(input_panel, orient="vertical", command=self.input_text.yview)
        input_scroll.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self.input_text.configure(yscrollcommand=input_scroll.set)

        send_col = ttk.Frame(input_panel, style="Panel.TFrame")
        send_col.grid(row=1, column=2, sticky="nsw", padx=(10, 0), pady=(6, 0))
        self.btn_send = ttk.Button(send_col, text="Send (Ctrl+Enter)", style="Primary.TButton", command=self._on_send)
        self.btn_send.pack(fill="x")
        ttk.Label(send_col, text="The GUI client reuses the same Brain + tools.", style="Muted.TLabel", wraplength=210).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Label(send_col, text="Temporary status/tool logs stay on the right panel.", style="Muted.TLabel", wraplength=210).pack(
            anchor="w", pady=(6, 0)
        )

        input_panel.columnconfigure(0, weight=1)
        input_panel.rowconfigure(1, weight=1)

        # Status bar
        status_bar = ttk.Frame(root, style="App.TFrame")
        status_bar.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="Ready")
        self.session_var = tk.StringVar(value="Session: not started")
        ttk.Label(status_bar, textvariable=self.status_var).pack(side="left")
        ttk.Label(status_bar, textvariable=self.session_var, style="Muted.TLabel").pack(side="right")

        self._append_system_note(
            "Local GUI client initialized. Discord reply mode remains available and is not removed."
        )

    def _configure_chat_tags(self):
        c = self.chat_text
        c.tag_configure("meta", foreground=self._colors["muted"], font=("Segoe UI", 9))
        c.tag_configure(
            "user_hdr", foreground="#0f3d91", font=("Segoe UI Semibold", 10)
        )
        c.tag_configure(
            "assistant_hdr", foreground="#0b5a33", font=("Segoe UI Semibold", 10)
        )
        c.tag_configure("system_hdr", foreground="#49576d", font=("Segoe UI Semibold", 10))
        c.tag_configure("user_body", background=self._colors["user_bg"])
        c.tag_configure("assistant_body", background=self._colors["assistant_bg"])
        c.tag_configure("system_body", background=self._colors["system_bg"])

    def _configure_event_tags(self):
        e = self.event_text
        e.tag_configure("info", foreground=self._colors["ink"])
        e.tag_configure("muted", foreground=self._colors["muted"])
        e.tag_configure("warn", foreground="#b26a00")
        e.tag_configure("error", foreground="#b42318")
        e.tag_configure("ok", foreground="#067647")

    def _model_label_text(self) -> str:
        try:
            from config import config

            return f"Model: {config.LLM_MODEL}"
        except Exception:
            return "Model: (unavailable)"

    # ------------------------------------------------------------------ actions

    def _set_busy(self, value: bool):
        self._busy = bool(value)
        self.btn_send.configure(state=("disabled" if self._busy else "normal"))
        self.btn_new.configure(state=("disabled" if self._busy else "normal"))
        self.btn_setup.configure(state=("disabled" if self._busy else "normal"))
        self.btn_stop.configure(state=("normal" if self._busy else "disabled"))

    def _on_send_shortcut(self, _evt):
        self._on_send()
        return "break"

    def _on_send(self):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            return
        if self._busy:
            self._append_event("Busy; wait for current task to finish or press Stop.", level="warn")
            return
        ok = self.controller.send_message(text)
        if not ok:
            self._append_event("Failed to queue message.", level="error")
            return
        self.input_text.delete("1.0", "end")

    def _on_stop(self):
        self.controller.cancel()

    def _on_new_session(self):
        if self._busy:
            messagebox.showwarning("Busy", "Stop the current task before resetting the session.")
            return
        if self.controller.reset_session():
            self.session_var.set("Session: reset")
            self._append_system_note("Session reset. New messages start a fresh context.")

    def _on_clear_view(self):
        for widget in (self.chat_text, self.event_text):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")
        self._append_system_note("View cleared. Session context is unchanged.")

    def _on_setup(self):
        if self._busy:
            messagebox.showwarning("Busy", "Stop the current task before opening the setup wizard.")
            return
        root = Path(__file__).resolve().parent.parent
        script = root / "config_wizard.py"
        flags = 0
        kwargs = {}
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            kwargs["creationflags"] = flags
        try:
            subprocess.Popen([sys.executable, str(script)], cwd=str(root), **kwargs)
            self._append_event("Opened config wizard in a separate process.", level="info")
        except Exception as e:
            self._append_event(f"Failed to open config wizard: {e}", level="error")

    def _on_close(self):
        self._closed = True
        if self._busy:
            if not messagebox.askyesno("Exit", "A task is still running. Cancel and exit?"):
                self._closed = False
                return
            self.controller.cancel()
        self.destroy()

    # ------------------------------------------------------------------ event handling

    def _pump_events(self):
        if self._closed:
            return
        try:
            for event in self.controller.drain_events():
                self._handle_event(event)
        finally:
            try:
                if not self._closed and self.winfo_exists():
                    self.after(80, self._pump_events)
            except tk.TclError:
                return

    def _handle_event(self, event: dict):
        et = event.get("type")
        if et == "busy":
            self._set_busy(bool(event.get("value")))
            return
        if et == "status":
            self.status_var.set(str(event.get("text", "")))
            self._append_event(str(event.get("text", "")), level="muted")
            return
        if et == "session_created":
            self.session_var.set("Session: active")
            return
        if et == "session_reset":
            self.session_var.set("Session: reset")
            return
        if et == "user":
            self._append_chat("user", str(event.get("text", "")))
            return
        if et == "assistant":
            self._append_chat("assistant", str(event.get("text", "")))
            return
        if et == "tool_call":
            names = event.get("names") or []
            self._append_event(f"Tool call: {', '.join(names)}", level="info")
            return
        if et == "tool_result":
            ok = bool(event.get("ok", True))
            done = bool(event.get("done", False))
            summary = str(event.get("summary", "") or "")
            prefix = "done" if done else "step"
            tag = "ok" if ok else "error"
            self._append_event(f"{prefix}: {summary}", level=tag)
            image = event.get("image") or {}
            if isinstance(image, dict) and image.get("base64"):
                self._append_chat_image(image, caption=summary)
            return
        if et == "cancelled":
            self._append_event("Task cancelled.", level="warn")
            return
        if et == "error":
            self._append_event(str(event.get("message", "Unknown error")), level="error")
            return
        if et == "done":
            return

    def _append_system_note(self, text: str):
        self._append_chat("system", text)

    def _append_chat(self, role: str, text: str):
        text = (text or "").rstrip()
        if not text:
            return
        hdr_tag = {
            "user": "user_hdr",
            "assistant": "assistant_hdr",
            "system": "system_hdr",
        }.get(role, "system_hdr")
        body_tag = {
            "user": "user_body",
            "assistant": "assistant_body",
            "system": "system_body",
        }.get(role, "system_body")
        label = {
            "user": "You",
            "assistant": "Starbot",
            "system": "System",
        }.get(role, role.title())

        w = self.chat_text
        w.configure(state="normal")
        w.insert("end", f"{label}\n", (hdr_tag,))
        w.insert("end", f"{text}\n\n", (body_tag,))
        w.configure(state="disabled")
        w.see("end")

    def _append_chat_image(self, image_payload: dict, caption: str = ""):
        """Append image message into chat pane from base64 payload."""
        b64 = str(image_payload.get("base64", "") or "").strip()
        if not b64:
            return
        try:
            raw = base64.b64decode(b64)
            pil = Image.open(io.BytesIO(raw)).convert("RGB")
            max_w = 560
            max_h = 340
            w, h = pil.size
            scale = min(max_w / max(1, w), max_h / max(1, h), 1.0)
            if scale < 1.0:
                pil = pil.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil)
            self._chat_images.append(photo)

            wdg = self.chat_text
            wdg.configure(state="normal")
            wdg.insert("end", "Starbot\n", ("assistant_hdr",))
            wdg.image_create("end", image=photo)
            if caption:
                wdg.insert("end", f"\n{caption}\n\n", ("assistant_body",))
            else:
                wdg.insert("end", "\n\n", ("assistant_body",))
            wdg.configure(state="disabled")
            wdg.see("end")
        except Exception as e:
            self._append_event(f"Image render failed: {e}", level="warn")

    def _append_event(self, text: str, *, level: str = "info"):
        t = self.event_text
        t.configure(state="normal")
        t.insert("end", f"{text}\n", (level,))
        t.configure(state="disabled")
        t.see("end")


def launch_gui():
    app = StarbotGuiClient()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
