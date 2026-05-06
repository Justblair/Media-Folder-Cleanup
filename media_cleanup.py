#!/usr/bin/env python3
"""
Media folder cleanup tool.

Scans subfolders of a root directory and identifies folders that no longer
contain any media files (leftovers after a media player deletes the video).

Run with no arguments for the GUI, or supply a path for CLI mode:
    python media_cleanup.py
    python media_cleanup.py /path/to/media
    python media_cleanup.py /path/to/media --delete
"""

import argparse
import csv
import queue
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path

MEDIA_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4v",
    ".ts", ".mpg", ".mpeg", ".flv", ".webm", ".divx",
    ".xvid", ".iso", ".vob", ".m2ts", ".rmvb", ".ogv",
}

# ---------------------------------------------------------------------------
# Core logic (shared by CLI and GUI)
# ---------------------------------------------------------------------------

def has_media_files(folder: Path) -> bool:
    for entry in folder.rglob("*"):
        if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
            return True
    return False


def folder_size(folder: Path) -> int:
    total = 0
    for entry in folder.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                pass
    return total


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def write_csv(root: Path, results: list[tuple[Path, bool, int]]) -> Path:
    """Write scan results to a CSV file alongside the scanned folder."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = root / f"media_cleanup_{timestamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Folder Name", "Status", "Size (Bytes)", "Size (Readable)", "Full Path"])
        for folder, has_media, size in results:
            status = "Has Media" if has_media else "No Media"
            writer.writerow([folder.name, status, size, human_size(size), str(folder)])
    return csv_path


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    class App:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Media Folder Cleanup")
            self.root.minsize(680, 480)

            self._folder = tk.StringVar()
            self._create_csv = tk.BooleanVar(value=False)
            self._scanning = False
            self._results: list[tuple[Path, bool, int]] = []
            self._queue: queue.Queue = queue.Queue()

            self._build_ui()

        def _build_ui(self) -> None:
            pad = {"padx": 10, "pady": 5}

            # --- Folder row ---
            folder_frame = ttk.LabelFrame(self.root, text="Media Folder", padding=8)
            folder_frame.pack(fill="x", **pad)

            self._entry = ttk.Entry(folder_frame, textvariable=self._folder)
            self._entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

            ttk.Button(folder_frame, text="Browse…", command=self._browse).pack(side="left")

            # --- Options row ---
            opts_frame = ttk.Frame(self.root)
            opts_frame.pack(fill="x", padx=10, pady=(0, 4))

            ttk.Checkbutton(
                opts_frame, text="Create CSV report after scan", variable=self._create_csv
            ).pack(side="left")

            # --- Scan button ---
            self._btn_scan = ttk.Button(self.root, text="Scan", command=self._start_scan, width=16)
            self._btn_scan.pack(pady=(2, 6))

            # --- Console ---
            console_frame = ttk.LabelFrame(self.root, text="Output", padding=4)
            console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

            self._console = scrolledtext.ScrolledText(
                console_frame, state="disabled", height=20,
                font=("Courier New", 9), wrap="none",
            )
            self._console.pack(fill="both", expand=True)

            # colour tags
            self._console.tag_config("ok",       foreground="#2a9d2a")
            self._console.tag_config("nomedia",   foreground="#cc4400")
            self._console.tag_config("heading",   foreground="#1a6fcc")
            self._console.tag_config("separator", foreground="#888888")
            self._console.tag_config("csv",       foreground="#7a4db5")

            # --- Status bar ---
            self._status = tk.StringVar(value="Ready.")
            ttk.Label(self.root, textvariable=self._status, anchor="w", relief="sunken").pack(
                fill="x", padx=10, pady=(0, 8), ipady=2
            )

        # ------------------------------------------------------------------

        def _browse(self) -> None:
            folder = filedialog.askdirectory(title="Select root media folder")
            if folder:
                self._folder.set(folder)

        def _log(self, text: str, tag: str = "") -> None:
            self._console.configure(state="normal")
            if tag:
                self._console.insert("end", text + "\n", tag)
            else:
                self._console.insert("end", text + "\n")
            self._console.see("end")
            self._console.configure(state="disabled")

        def _clear_console(self) -> None:
            self._console.configure(state="normal")
            self._console.delete("1.0", "end")
            self._console.configure(state="disabled")

        # ------------------------------------------------------------------

        def _start_scan(self) -> None:
            folder_str = self._folder.get().strip()
            if not folder_str:
                from tkinter import messagebox
                messagebox.showwarning("No folder", "Please select a folder first.")
                return
            root = Path(folder_str)
            if not root.is_dir():
                from tkinter import messagebox
                messagebox.showerror("Invalid folder", f"Not a directory:\n{root}")
                return

            self._clear_console()
            self._results = []
            self._btn_scan.configure(state="disabled")
            self._status.set("Scanning…")

            thread = threading.Thread(target=self._scan_worker, args=(root,), daemon=True)
            thread.start()
            self.root.after(50, self._poll_queue)

        def _scan_worker(self, root: Path) -> None:
            q = self._queue
            subfolders = sorted(f for f in root.iterdir() if f.is_dir())
            total = len(subfolders)

            q.put(("log", f"Scanning: {root}", "heading"))
            q.put(("log", f"Subfolders found: {total}\n", ""))

            total_media_bytes = 0
            total_leftover_bytes = 0
            results: list[tuple[Path, bool, int]] = []

            for i, folder in enumerate(subfolders, 1):
                q.put(("status", f"Checking {i}/{total}: {folder.name}"))
                has_media = has_media_files(folder)
                size = folder_size(folder)
                results.append((folder, has_media, size))

                if has_media:
                    total_media_bytes += size
                    q.put(("log", f"  [ok]        {folder.name:<50}  {human_size(size):>10}", "ok"))
                else:
                    total_leftover_bytes += size
                    q.put(("log", f"  [no media]  {folder.name:<50}  {human_size(size):>10}", "nomedia"))

            orphaned = [r for r in results if not r[1]]

            q.put(("log", "", ""))
            q.put(("log", "=" * 65, "separator"))
            q.put(("log", f"  Folders checked       : {total}", ""))
            q.put(("log", f"  Remaining media       : {total - len(orphaned)} folder(s)  —  {human_size(total_media_bytes)}", "ok"))
            q.put(("log", f"  Folders with no media : {len(orphaned)} folder(s)  —  {human_size(total_leftover_bytes)} leftover", "nomedia"))
            q.put(("log", "=" * 65, "separator"))

            q.put(("done", results))

        def _poll_queue(self) -> None:
            try:
                while True:
                    msg = self._queue.get_nowait()
                    kind = msg[0]

                    if kind == "log":
                        _, text, tag = msg
                        self._log(text, tag)

                    elif kind == "status":
                        self._status.set(msg[1])

                    elif kind == "done":
                        self._results = msg[1]
                        self._on_scan_complete()
                        return  # stop polling

            except queue.Empty:
                pass

            self.root.after(50, self._poll_queue)

        def _on_scan_complete(self) -> None:
            self._btn_scan.configure(state="normal")
            self._status.set("Scan complete.")

            orphaned = [(p, s) for p, has_media, s in self._results if not has_media]

            if self._create_csv.get():
                root = Path(self._folder.get())
                csv_path = write_csv(root, self._results)
                self._log(f"\nCSV saved: {csv_path}", "csv")

            if not orphaned:
                self._status.set("Scan complete — nothing to clean up.")
                return

            from tkinter import messagebox
            answer = messagebox.askyesno(
                "Delete folders?",
                f"{len(orphaned)} folder(s) contain no media files.\n\n"
                "Permanently delete them?",
            )
            if not answer:
                self._status.set("Scan complete — no folders deleted.")
                return

            self._status.set("Deleting…")
            self._log("", "")
            removed = 0
            errors = 0
            for folder, _ in orphaned:
                try:
                    shutil.rmtree(folder)
                    self._log(f"  Deleted: {folder.name}", "nomedia")
                    removed += 1
                except OSError as exc:
                    self._log(f"  Error deleting {folder.name}: {exc}")
                    errors += 1

            summary = f"Deleted {removed} folder(s)."
            if errors:
                summary += f"  ({errors} error(s))"
            self._log(f"\n{summary}")
            self._status.set(summary)

    root_win = tk.Tk()
    App(root_win)
    root_win.mainloop()


# ---------------------------------------------------------------------------
# CLI (unchanged behaviour)
# ---------------------------------------------------------------------------

def run_cli(folder_str: str, delete: bool) -> None:
    root = Path(folder_str)
    if not root.exists():
        sys.exit(f"Error: path does not exist: {root}")
    if not root.is_dir():
        sys.exit(f"Error: not a directory: {root}")

    subfolders = sorted(f for f in root.iterdir() if f.is_dir())
    total = len(subfolders)

    print(f"\nScanning: {root}")
    print(f"Subfolders found: {total}\n")

    results: list[tuple[Path, bool, int]] = []
    total_media_bytes = 0
    total_leftover_bytes = 0

    for folder in subfolders:
        has_media = has_media_files(folder)
        size = folder_size(folder)
        results.append((folder, has_media, size))
        if has_media:
            total_media_bytes += size
            print(f"  [ok]        {folder.name:<50}  {human_size(size):>10}")
        else:
            total_leftover_bytes += size
            print(f"  [no media]  {folder.name:<50}  {human_size(size):>10}")

    orphaned = [(p, s) for p, has_media, s in results if not has_media]

    print()
    print("=" * 65)
    print(f"  Folders checked       : {total}")
    print(f"  Remaining media       : {total - len(orphaned)} folder(s)  —  {human_size(total_media_bytes)}")
    print(f"  Folders with no media : {len(orphaned)} folder(s)  —  {human_size(total_leftover_bytes)} leftover")
    print("=" * 65)

    if not orphaned:
        print("\nNothing to clean up.")
        return

    if not delete:
        print("\nDry run — no changes made. Use --delete to remove folders.")
        return

    answer = input(f"\nPermanently delete {len(orphaned)} folder(s)? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    removed = errors = 0
    for folder, _ in orphaned:
        try:
            shutil.rmtree(folder)
            print(f"  Deleted: {folder.name}")
            removed += 1
        except OSError as exc:
            print(f"  Error deleting {folder.name}: {exc}")
            errors += 1

    print(f"\nDeleted {removed} folder(s)." + (f"  ({errors} error(s))" if errors else ""))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find and optionally remove media subfolders that contain no media files."
    )
    parser.add_argument("folder", nargs="?", help="Root folder to scan (omit for GUI).")
    parser.add_argument("--delete", action="store_true", help="Delete empty media folders.")
    args = parser.parse_args()

    if args.folder:
        run_cli(args.folder, args.delete)
    else:
        run_gui()


if __name__ == "__main__":
    main()
