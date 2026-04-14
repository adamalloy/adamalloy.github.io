#!/usr/bin/env python3
"""
Media File Renamer for Premiere Pro
Renames media files to a structured naming convention:
    PROJ01_SC01_A_001.mp4
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".mxf", ".avi", ".r3d", ".braw",
    ".mkv", ".m4v", ".mts", ".m2ts", ".wmv", ".dng",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".dpx",
    ".wav", ".aif", ".aiff", ".mp3", ".aac",
}


def sanitize(value: str) -> str:
    """Strip whitespace and replace spaces with underscores."""
    return value.strip().replace(" ", "_")


def build_new_name(project: str, scene: str, angle: str, clip_num: int, ext: str) -> str:
    proj = sanitize(project).upper()
    sc = sanitize(scene).upper()
    ang = sanitize(angle).upper()
    return f"{proj}_{sc}_{ang}_{clip_num:03d}{ext.lower()}"


class MediaRenamerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Media File Renamer")
        self.resizable(True, True)
        self.minsize(820, 560)

        self._folder_path = tk.StringVar()
        self._project = tk.StringVar(value="PROJ01")
        self._scene = tk.StringVar(value="SC01")
        self._angle = tk.StringVar(value="A")
        self._start_num = tk.StringVar(value="1")

        self._files: list[Path] = []
        self._preview: list[tuple[str, str]] = []  # (old_name, new_name)

        self._build_ui()
        self._bind_trace()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── top bar (fields) ─────────────────────────────────────────
        top = ttk.Frame(self, padding=(12, 10, 12, 6))
        top.pack(fill="x")

        fields = [
            ("Project Code", self._project, 10),
            ("Scene", self._scene, 8),
            ("Camera Angle", self._angle, 6),
            ("Start #", self._start_num, 5),
        ]
        for col, (label, var, width) in enumerate(fields):
            ttk.Label(top, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 4))
            e = ttk.Entry(top, textvariable=var, width=width)
            e.grid(row=0, column=col * 2 + 1, sticky="w", padx=(0, 16))

        # preview label (right-aligned)
        self._preview_label = ttk.Label(top, text="", foreground="#555555")
        self._preview_label.grid(row=0, column=len(fields) * 2, sticky="e")
        top.columnconfigure(len(fields) * 2, weight=1)

        # ── folder row ───────────────────────────────────────────────
        folder_row = ttk.Frame(self, padding=(12, 0, 12, 8))
        folder_row.pack(fill="x")

        ttk.Label(folder_row, text="Folder:").pack(side="left")
        ttk.Entry(folder_row, textvariable=self._folder_path, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(folder_row, text="Browse…", command=self._browse).pack(side="left")

        # ── separator ────────────────────────────────────────────────
        ttk.Separator(self).pack(fill="x")

        # ── preview table ────────────────────────────────────────────
        table_frame = ttk.Frame(self, padding=(12, 8, 12, 4))
        table_frame.pack(fill="both", expand=True)

        cols = ("original", "renamed")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="none")
        self._tree.heading("original", text="Original Filename")
        self._tree.heading("renamed", text="New Filename")
        self._tree.column("original", width=380, minwidth=200)
        self._tree.column("renamed", width=380, minwidth=200)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # tag for conflicts
        self._tree.tag_configure("conflict", foreground="#cc3300")
        self._tree.tag_configure("ok", foreground="#007700")

        # ── status bar + rename button ────────────────────────────────
        bottom = ttk.Frame(self, padding=(12, 6, 12, 10))
        bottom.pack(fill="x")

        self._status = ttk.Label(bottom, text="Select a folder to begin.", anchor="w")
        self._status.pack(side="left", fill="x", expand=True)

        self._rename_btn = ttk.Button(
            bottom, text="Rename Files", command=self._apply_rename, state="disabled"
        )
        self._rename_btn.pack(side="right")

    # ------------------------------------------------------------------
    # Logic
    # ------------------------------------------------------------------

    def _bind_trace(self):
        for var in (self._project, self._scene, self._angle, self._start_num, self._folder_path):
            var.trace_add("write", lambda *_: self._refresh_preview())

    def _browse(self):
        path = filedialog.askdirectory(title="Select folder of media files")
        if path:
            self._folder_path.set(path)

    def _load_files(self, folder: str) -> list[Path]:
        p = Path(folder)
        files = sorted(
            [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS],
            key=lambda f: f.name.lower(),
        )
        return files

    def _validate_inputs(self) -> str | None:
        """Return an error string, or None if inputs are valid."""
        if not self._folder_path.get():
            return "No folder selected."
        if not sanitize(self._project.get()):
            return "Project Code cannot be empty."
        if not sanitize(self._scene.get()):
            return "Scene cannot be empty."
        if not sanitize(self._angle.get()):
            return "Camera Angle cannot be empty."
        try:
            n = int(self._start_num.get())
            if n < 1:
                raise ValueError
        except ValueError:
            return "Start # must be a positive integer."
        return None

    def _refresh_preview(self):
        for row in self._tree.get_children():
            self._tree.delete(row)

        self._preview = []
        self._rename_btn.config(state="disabled")

        err = self._validate_inputs()
        if err:
            self._status.config(text=err)
            self._preview_label.config(text="")
            return

        folder = self._folder_path.get()
        self._files = self._load_files(folder)

        if not self._files:
            self._status.config(text="No media files found in the selected folder.")
            self._preview_label.config(text="")
            return

        start = int(self._start_num.get())
        new_names: list[str] = []
        for i, f in enumerate(self._files):
            new_name = build_new_name(
                self._project.get(),
                self._scene.get(),
                self._angle.get(),
                start + i,
                f.suffix,
            )
            new_names.append(new_name)
            self._preview.append((f.name, new_name))

        # detect duplicate new names
        seen: dict[str, int] = {}
        for idx, name in enumerate(new_names):
            seen[name] = seen.get(name, 0) + 1
        conflicts = {name for name, count in seen.items() if count > 1}

        has_conflict = False
        for old, new in self._preview:
            tag = "conflict" if new in conflicts else "ok"
            if tag == "conflict":
                has_conflict = True
            self._tree.insert("", "end", values=(old, new), tags=(tag,))

        count = len(self._files)
        self._preview_label.config(text=f"{count} file{'s' if count != 1 else ''} found")

        if has_conflict:
            self._status.config(text="Warning: duplicate new filenames detected (shown in red).")
        else:
            sample = new_names[0] if new_names else ""
            self._status.config(text=f"Ready to rename {count} file(s).  e.g. {sample}")
            self._rename_btn.config(state="normal")

    def _apply_rename(self):
        if not self._preview or not self._files:
            return

        folder = Path(self._folder_path.get())
        errors: list[str] = []
        renamed = 0

        # Two-phase rename: first to temp names, then to final names.
        # This avoids collisions when files are being shuffled (e.g. 001->002).
        temp_paths: list[tuple[Path, Path]] = []
        try:
            for f, (_, new_name) in zip(self._files, self._preview):
                temp = folder / (f.name + ".__tmp__")
                f.rename(temp)
                temp_paths.append((temp, folder / new_name))
        except OSError as exc:
            # Roll back temps already done
            for tmp, _ in temp_paths:
                if tmp.exists():
                    orig = folder / tmp.name.replace(".__tmp__", "")
                    try:
                        tmp.rename(orig)
                    except OSError:
                        pass
            messagebox.showerror("Error", f"Rename failed during temp phase:\n{exc}")
            return

        for tmp, final in temp_paths:
            try:
                tmp.rename(final)
                renamed += 1
            except OSError as exc:
                errors.append(f"{tmp.name} → {final.name}: {exc}")

        if errors:
            messagebox.showwarning(
                "Partial Rename",
                f"Renamed {renamed} file(s) with {len(errors)} error(s):\n\n"
                + "\n".join(errors[:10]),
            )
        else:
            messagebox.showinfo("Done", f"Successfully renamed {renamed} file(s).")

        # Refresh so the table reflects the new state on disk
        self._refresh_preview()


def main():
    app = MediaRenamerApp()
    # Centre on screen
    app.update_idletasks()
    w, h = 860, 600
    sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
    app.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    app.mainloop()


if __name__ == "__main__":
    main()
