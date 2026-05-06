# Media Folder Cleanup

A Python utility for tidying up media libraries after files have been deleted by a media player.

When a media player (Plex, Kodi, etc.) deletes a video file it often leaves the parent folder behind, along with leftover files such as `.nfo`, `.jpg`, `.srt`, and `.nzb`. This tool scans a root media directory, identifies those orphaned folders, and optionally removes them.

---

## Features

- GUI mode with live-updating console output (tkinter)
- CLI mode for scripting or headless use
- Colour-coded results — green for folders with media, orange for orphaned folders
- Summary showing total size of remaining media and leftover junk
- Optional CSV export for sorting and analysing in Excel
- Cross-platform — works on Windows and Linux
- Safe by default — always confirms before deleting anything

---

## Screenshots

![Media Folder Cleanup GUI](https://raw.githubusercontent.com/Justblair/Media-Folder-Cleanup/main/screenshot.png)
---

## Requirements

- Python 3.10 or later
- No third-party packages required
- `tkinter` is included with most Python installations (GUI mode only)

---

## Installation

```bash
git clone https://github.com/Justblair/Media-Folder-Cleanup.git
cd media-cleanup
```

No virtual environment or `pip install` needed.

---

## Usage

### GUI mode

Run with no arguments to open the GUI:

```bash
python media_cleanup.py
```

1. Click **Browse…** and select your root media folder
2. Tick **Create CSV report** if you want a spreadsheet of the results
3. Click **Scan**
4. Review the output — orphaned folders are highlighted in orange
5. When prompted, choose whether to delete the orphaned folders

### CLI mode

```bash
# Scan only (dry run)
python media_cleanup.py /path/to/media

# Scan and delete (asks for confirmation)
python media_cleanup.py /path/to/media --delete
```

---

## CSV Export

When **Create CSV report** is ticked, a file is saved into the scanned folder:

```
media_cleanup_20260506_143022.csv
```

| Column | Description |
|---|---|
| Folder Name | Name of the subfolder |
| Status | `Has Media` or `No Media` |
| Size (Bytes) | Raw byte count — sort by this column in Excel |
| Size (Readable) | Human-friendly size (KB, MB, GB) |
| Full Path | Absolute path to the folder |

---

## Supported Media Formats

`.mp4` `.avi` `.mkv` `.mov` `.wmv` `.m4v` `.ts` `.mpg` `.mpeg` `.flv` `.webm` `.divx` `.xvid` `.iso` `.vob` `.m2ts` `.rmvb` `.ogv`

Additional extensions can be added to the `MEDIA_EXTENSIONS` set at the top of `media_cleanup.py`.

---

## Folder Structure Assumed

```
/media/
├── Film Title (Year)/
│   └── film.mkv
├── TV Show Name/
│   ├── Season 01/
│   │   └── episode.mp4
│   └── poster.jpg
└── Orphaned Show/          ← no video files remain
    ├── show.nfo
    └── poster.jpg
```

The tool scans immediate subfolders of the root. Each subfolder is checked recursively for any media file, so nested season folders are handled correctly.

---

## License

MIT
