#!/usr/bin/env python3
"""3GP to QuickTime Converter — batch-convert .3gp/.3g2 files to MP4."""

import os
import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
SETFILE = "/usr/bin/SetFile"
EXTENSIONS = {".3gp", ".3g2"}
COPY_TIMEOUT = 300   # 5 minutes
ENCODE_TIMEOUT = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Conversion helpers  (unchanged logic)
# ---------------------------------------------------------------------------
def get_video_height(src, q):
    """Return the video height in pixels, or None on failure."""
    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=height",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(src),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return int(result.stdout.strip())
    except Exception as exc:
        q.put({"type": "log", "text": f"  ffprobe failed ({exc}), will re-encode"})
        return None


def preserve_timestamps(src, dst, q):
    """Copy modification time and macOS creation date from src to dst."""
    try:
        subprocess.run(["touch", "-r", str(src), str(dst)],
                       capture_output=True, timeout=10)
    except Exception as exc:
        q.put({"type": "log", "text": f"  Warning: touch failed ({exc})"})

    try:
        stat = os.stat(str(src))
        birthtime = datetime.fromtimestamp(stat.st_birthtime)
        date_str = birthtime.strftime("%m/%d/%Y %H:%M:%S")
        subprocess.run([SETFILE, "-d", date_str, str(dst)],
                       capture_output=True, timeout=10)
    except Exception as exc:
        q.put({"type": "log", "text": f"  Warning: SetFile failed ({exc})"})

    try:
        result = subprocess.run(
            [
                FFPROBE, "-v", "quiet",
                "-show_entries", "format_tags=creation_time",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(src),
            ],
            capture_output=True, text=True, timeout=30,
        )
        creation_time = result.stdout.strip()
        if creation_time:
            q.put({"type": "log",
                   "text": f"  Container creation_time: {creation_time}"})
    except Exception:
        pass


def convert_file(src, dst, q):
    """Probe, convert, and preserve timestamps. Return True on success."""
    height = get_video_height(src, q)
    needs_upscale = height is None or height < 480
    success = False

    if not needs_upscale:
        q.put({"type": "log",
               "text": f"  Resolution {height}p ≥ 480p — trying stream copy…"})
        try:
            result = subprocess.run(
                [
                    FFMPEG, "-y", "-i", str(src),
                    "-c:v", "copy", "-c:a", "copy",
                    "-map_metadata", "0",
                    "-movflags", "+faststart",
                    str(dst),
                ],
                capture_output=True, text=True, timeout=COPY_TIMEOUT,
            )
            if result.returncode == 0:
                q.put({"type": "log", "text": "  Stream copy succeeded"})
                success = True
            else:
                q.put({"type": "log",
                       "text": "  Stream copy failed — falling back to re-encode"})
                if dst.exists():
                    dst.unlink()
        except subprocess.TimeoutExpired:
            q.put({"type": "log", "text": "  Stream copy timed out"})
            if dst.exists():
                dst.unlink()
        except Exception as exc:
            q.put({"type": "log", "text": f"  Stream copy error: {exc}"})
            if dst.exists():
                dst.unlink()

    if not success:
        cmd = [FFMPEG, "-y", "-i", str(src),
               "-c:v", "libx264", "-preset", "fast", "-crf", "22"]
        if needs_upscale:
            q.put({"type": "log",
                   "text": f"  Resolution {height or '?'}p < 480p — "
                           "re-encoding with upscale to 480p…"})
            cmd += ["-vf", "scale=-2:480"]
        else:
            q.put({"type": "log", "text": "  Re-encoding without scale…"})

        cmd += ["-c:a", "aac", "-b:a", "128k",
                "-map_metadata", "0", "-movflags", "+faststart", str(dst)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=ENCODE_TIMEOUT,
            )
            if result.returncode == 0:
                q.put({"type": "log", "text": "  Re-encode succeeded"})
                success = True
            else:
                stderr_lines = result.stderr.strip().splitlines()
                tail = "\n".join(stderr_lines[-3:]) if stderr_lines else "(no output)"
                q.put({"type": "log", "text": f"  Re-encode FAILED:\n{tail}"})
                if dst.exists():
                    dst.unlink()
        except subprocess.TimeoutExpired:
            q.put({"type": "log", "text": "  Re-encode timed out (10 min)"})
            if dst.exists():
                dst.unlink()
        except Exception as exc:
            q.put({"type": "log", "text": f"  Re-encode error: {exc}"})
            if dst.exists():
                dst.unlink()

    if success:
        preserve_timestamps(src, dst, q)

    return success


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
def conversion_worker(folder, q):
    """Scan *folder* for 3GP files, convert each, post updates to *q*."""
    folder = Path(folder)
    files = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    )

    total = len(files)
    q.put({"type": "status", "total": total, "processed": 0,
           "skipped": 0, "failed": 0})

    if total == 0:
        q.put({"type": "log", "text": "No .3gp / .3g2 files found in folder."})
        q.put({"type": "done"})
        return

    q.put({"type": "log", "text": f"Found {total} file(s) to process.\n"})

    processed = skipped = failed = 0

    for i, src in enumerate(files, 1):
        dst = src.with_suffix(".mp4")
        q.put({"type": "log", "text": f"[{i}/{total}]  {src.name}"})

        if dst.exists():
            q.put({"type": "log", "text": "  Skipped — output already exists\n"})
            skipped += 1
            q.put({"type": "status", "total": total, "processed": processed,
                   "skipped": skipped, "failed": failed})
            continue

        ok = convert_file(src, dst, q)
        if ok:
            processed += 1
        else:
            failed += 1

        q.put({"type": "log", "text": ""})
        q.put({"type": "status", "total": total, "processed": processed,
               "skipped": skipped, "failed": failed})

    q.put({"type": "log",
           "text": f"\n  Done — {processed} converted · "
                   f"{skipped} skipped · {failed} failed"})
    q.put({"type": "done"})


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class ConverterApp:

    # ── Palette ──────────────────────────────────────────────────────────────
    BG      = "#18181B"   # zinc-900
    BG2     = "#27272A"   # zinc-800
    BG3     = "#3F3F46"   # zinc-700
    FG      = "#FAFAFA"   # zinc-50
    FG2     = "#A1A1AA"   # zinc-400
    FG3     = "#71717A"   # zinc-500
    ACCENT  = "#F59E0B"   # amber-500
    ACCENT2 = "#FCD34D"   # amber-300 (hover/highlight)
    GREEN   = "#4ADE80"   # green-400
    RED     = "#F87171"   # red-400
    BLUE    = "#60A5FA"   # blue-400
    BORDER  = "#3F3F46"   # zinc-700

    FONT_MONO  = ("Menlo", 11)
    FONT_BODY  = ("Helvetica Neue", 12)
    FONT_LABEL = ("Helvetica Neue", 10)
    FONT_TITLE = ("Helvetica Neue", 18, "bold")
    FONT_SUB   = ("Helvetica Neue", 11)
    FONT_STAT  = ("Helvetica Neue", 22, "bold")
    FONT_CAP   = ("Helvetica Neue", 9)

    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self._setup_window()
        self._build_ui()

    # ── Window setup ─────────────────────────────────────────────────────────
    def _setup_window(self):
        self.root.title("3GP Converter")
        self.root.configure(bg=self.BG)
        self.root.geometry("740x620")
        self.root.minsize(640, 520)
        # macOS: hide the default title bar text (cosmetic)
        try:
            self.root.tk.call("::tk::unsupported::MacWindowStyle",
                              "style", self.root._w, "document", "closeBox")
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_folder_row()
        self._build_divider()
        self._build_stats_row()
        self._build_divider()
        self._build_log_section()
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=self.BG2,
                       highlightbackground=self.BORDER, highlightthickness=1)
        hdr.pack(fill=tk.X)

        inner = tk.Frame(hdr, bg=self.BG2)
        inner.pack(fill=tk.X, padx=24, pady=18)

        # Left: icon + title
        left = tk.Frame(inner, bg=self.BG2)
        left.pack(side=tk.LEFT)

        icon_lbl = tk.Label(left, bg=self.BG2)
        icon_lbl.pack(side=tk.LEFT, padx=(0, 12))
        self._load_header_icon(icon_lbl)

        text_col = tk.Frame(left, bg=self.BG2)
        text_col.pack(side=tk.LEFT)
        tk.Label(text_col, text="3GP Converter", font=self.FONT_TITLE,
                 fg=self.FG, bg=self.BG2).pack(anchor=tk.W)
        tk.Label(text_col, text="Batch convert .3gp · .3g2  →  QuickTime MP4",
                 font=self.FONT_SUB, fg=self.FG2, bg=self.BG2).pack(anchor=tk.W)

        # Right: status pill
        right = tk.Frame(inner, bg=self.BG2)
        right.pack(side=tk.RIGHT)
        self.status_pill = tk.Label(
            right, text="  ● Idle  ", font=self.FONT_LABEL,
            fg=self.FG3, bg=self.BG3,
            padx=10, pady=4,
        )
        self.status_pill.pack()

    def _load_header_icon(self, label):
        """Load logo_header.png from the bundle resources directory."""
        here = Path(__file__).parent
        img_path = here / "logo_header.png"
        if img_path.exists():
            try:
                img = tk.PhotoImage(file=str(img_path))
                label.config(image=img, width=44, height=44)
                label._img = img  # keep reference
            except Exception:
                pass

    def _build_folder_row(self):
        row = tk.Frame(self.root, bg=self.BG)
        row.pack(fill=tk.X, padx=24, pady=(18, 0))

        tk.Label(row, text="FOLDER", font=self.FONT_CAP,
                 fg=self.FG3, bg=self.BG).pack(anchor=tk.W, pady=(0, 6))

        entry_row = tk.Frame(row, bg=self.BG)
        entry_row.pack(fill=tk.X)

        # Custom entry container
        entry_wrap = tk.Frame(entry_row, bg=self.BORDER,
                              highlightbackground=self.BORDER,
                              highlightthickness=1)
        entry_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        inner_wrap = tk.Frame(entry_wrap, bg=self.BG2)
        inner_wrap.pack(fill=tk.X, padx=1, pady=1)

        self.folder_var = tk.StringVar()
        self.folder_entry = tk.Entry(
            inner_wrap,
            textvariable=self.folder_var,
            font=self.FONT_BODY,
            fg=self.FG, bg=self.BG2,
            insertbackground=self.ACCENT,
            relief=tk.FLAT, bd=0,
        )
        self.folder_entry.pack(fill=tk.X, padx=10, pady=8)

        # Browse button
        self.browse_btn = self._make_button(
            entry_row, "Browse…", self.browse_folder,
            bg=self.ACCENT, fg=self.BG, active_bg=self.ACCENT2,
        )
        self.browse_btn.pack(side=tk.LEFT)

        # Convert button (prominent, below)
        btn_row = tk.Frame(self.root, bg=self.BG)
        btn_row.pack(fill=tk.X, padx=24, pady=14)

        self.convert_btn = self._make_button(
            btn_row, "Scan & Convert", self.start_conversion,
            bg=self.ACCENT, fg=self.BG, active_bg=self.ACCENT2,
            font=("Helvetica Neue", 13, "bold"), padx=24, pady=9,
        )
        self.convert_btn.pack(side=tk.LEFT)

        # Progress bar (hidden until conversion starts)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = tk.Canvas(
            btn_row, height=6, bg=self.BG3,
            highlightthickness=0,
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True,
                               padx=(16, 0), pady=(0, 0))
        self.progress_bar.bind("<Configure>", self._redraw_progress)
        self._progress_pct = 0.0

    def _make_button(self, parent, text, command, bg, fg,
                     active_bg=None, font=None, padx=14, pady=7):
        if font is None:
            font = self.FONT_BODY
        if active_bg is None:
            active_bg = bg
        btn = tk.Button(
            parent, text=text, command=command,
            font=font, fg=fg, bg=bg,
            activeforeground=fg, activebackground=active_bg,
            relief=tk.FLAT, bd=0,
            highlightthickness=0,
            highlightbackground=bg,  # forces macOS to honour bg colour
            padx=padx, pady=pady,
            cursor="hand2",
        )
        return btn

    def _build_divider(self):
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill=tk.X)

    def _build_stats_row(self):
        row = tk.Frame(self.root, bg=self.BG)
        row.pack(fill=tk.X, padx=24, pady=14)

        stats = [
            ("Total",     "total_val",     self.FG,       "FILES"),
            ("Converted", "processed_val", self.GREEN,    "OK"),
            ("Skipped",   "skipped_val",   self.ACCENT,   "—"),
            ("Failed",    "failed_val",    self.RED,       "ERR"),
        ]

        for i, (label, attr, color, badge) in enumerate(stats):
            card = tk.Frame(row, bg=self.BG2,
                            highlightbackground=self.BORDER,
                            highlightthickness=1)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                      padx=(0 if i == 0 else 8, 0))

            inner = tk.Frame(card, bg=self.BG2)
            inner.pack(padx=16, pady=10, anchor=tk.W)

            num_var = tk.StringVar(value="0")
            setattr(self, attr, num_var)

            tk.Label(inner, textvariable=num_var,
                     font=self.FONT_STAT, fg=color, bg=self.BG2,
                     ).pack(anchor=tk.W)
            tk.Label(inner, text=label.upper(),
                     font=self.FONT_CAP, fg=self.FG3, bg=self.BG2,
                     ).pack(anchor=tk.W)

    def _build_log_section(self):
        section = tk.Frame(self.root, bg=self.BG)
        section.pack(fill=tk.BOTH, expand=True, padx=24, pady=(14, 0))

        tk.Label(section, text="LOG", font=self.FONT_CAP,
                 fg=self.FG3, bg=self.BG).pack(anchor=tk.W, pady=(0, 6))

        log_wrap = tk.Frame(section, bg=self.BORDER,
                            highlightbackground=self.BORDER,
                            highlightthickness=1)
        log_wrap.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(log_wrap, bg=self.BG2)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Scrollbar
        vsb = tk.Scrollbar(inner, bg=self.BG3, troughcolor=self.BG2,
                           width=10, relief=tk.FLAT)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_area = tk.Text(
            inner,
            font=self.FONT_MONO,
            fg=self.FG2,
            bg=self.BG2,
            insertbackground=self.ACCENT,
            selectbackground=self.BG3,
            relief=tk.FLAT, bd=0,
            padx=14, pady=10,
            state=tk.DISABLED,
            wrap=tk.WORD,
            yscrollcommand=vsb.set,
            cursor="arrow",
        )
        self.log_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self.log_area.yview)

        # Tag styles for log coloring
        self.log_area.tag_configure("header",
                                    foreground=self.FG, font=("Menlo", 11, "bold"))
        self.log_area.tag_configure("ok", foreground=self.GREEN)
        self.log_area.tag_configure("warn", foreground=self.ACCENT)
        self.log_area.tag_configure("err", foreground=self.RED)
        self.log_area.tag_configure("muted", foreground=self.FG3)

    def _build_footer(self):
        foot = tk.Frame(self.root, bg=self.BG)
        foot.pack(fill=tk.X, padx=24, pady=10)
        tk.Label(foot,
                 text="ffmpeg · stream-copy when ≥480p · upscale when <480p · timestamps preserved",
                 font=self.FONT_CAP, fg=self.FG3, bg=self.BG,
                 ).pack(side=tk.LEFT)

    # ── Progress bar ─────────────────────────────────────────────────────────
    def _redraw_progress(self, event=None):
        w = self.progress_bar.winfo_width()
        h = self.progress_bar.winfo_height()
        self.progress_bar.delete("all")
        # Track
        self.progress_bar.create_rectangle(0, 0, w, h, fill=self.BG3, outline="")
        # Fill
        fill_w = int(w * self._progress_pct)
        if fill_w > 0:
            self.progress_bar.create_rectangle(0, 0, fill_w, h,
                                               fill=self.ACCENT, outline="")

    def set_progress(self, pct):
        self._progress_pct = max(0.0, min(1.0, pct))
        self._redraw_progress()

    # ── Actions ───────────────────────────────────────────────────────────────
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_var.set(path)

    def start_conversion(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self._log("Error: please select a valid folder.\n", tag="err")
            return

        self._clear_log()
        self._update_status(0, 0, 0, 0)
        self.set_progress(0)
        self.convert_btn.config(state=tk.DISABLED,
                                bg=self.BG3, fg=self.FG2)
        self.browse_btn.config(state=tk.DISABLED)
        self._set_pill("  ● Working…  ", self.ACCENT, self.BG)

        t = threading.Thread(target=conversion_worker,
                             args=(folder, self.q), daemon=True)
        t.start()
        self._total_files = 0
        self.poll_queue()

    def poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg["type"] == "log":
                    self._log_smart(msg["text"])
                elif msg["type"] == "status":
                    total = msg["total"]
                    done = msg["processed"] + msg["skipped"] + msg["failed"]
                    self._update_status(msg["processed"], msg["skipped"],
                                       msg["failed"], total)
                    if total > 0:
                        self.set_progress(done / total)
                elif msg["type"] == "done":
                    self.set_progress(1.0)
                    self._set_pill("  ● Done  ", self.GREEN, self.BG)
                    self.convert_btn.config(state=tk.NORMAL,
                                            bg=self.ACCENT, fg=self.BG)
                    self.browse_btn.config(state=tk.NORMAL)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _set_pill(self, text, fg, bg_=None):
        self.status_pill.config(text=text, fg=fg,
                                bg=bg_ or self.BG3)

    def _log_smart(self, text):
        """Route text to the appropriate color tag."""
        low = text.lower()
        if text.startswith("["):
            tag = "header"
        elif "succeeded" in low or "done" in low:
            tag = "ok"
        elif "failed" in low or "error" in low or "timed out" in low:
            tag = "err"
        elif "skipped" in low or "warning" in low or "warn" in low:
            tag = "warn"
        elif text.startswith("  ") and not text.strip():
            tag = "muted"
        else:
            tag = None
        self._log(text, tag=tag)

    def _log(self, text, tag=None):
        self.log_area.config(state=tk.NORMAL)
        if tag:
            self.log_area.insert(tk.END, text + "\n", tag)
        else:
            self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete("1.0", tk.END)
        self.log_area.config(state=tk.DISABLED)

    def _update_status(self, processed, skipped, failed, total):
        self.processed_val.set(str(processed))
        self.skipped_val.set(str(skipped))
        self.failed_val.set(str(failed))
        self.total_val.set(str(total))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
