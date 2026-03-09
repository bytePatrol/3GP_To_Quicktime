<p align="center">
  <img src="logo.png" width="140" alt="3GP Converter">
</p>

<h1 align="center">3GP Converter</h1>

<p align="center">
  <strong>Batch-convert old <code>.3gp</code> and <code>.3g2</code> mobile videos to QuickTime-compatible MP4</strong><br>
  Smart encoding &bull; Original timestamps preserved &bull; Zero quality loss when possible
</p>

<p align="center">
  <img src="https://img.shields.io/badge/macOS-12%2B-black?style=flat-square&logo=apple" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/ffmpeg-required-green?style=flat-square" />
  <img src="https://img.shields.io/github/license/bytePatrol/3GP_To_Quicktime?style=flat-square" />
  <img src="https://img.shields.io/github/v/release/bytePatrol/3GP_To_Quicktime?style=flat-square&color=F59E0B" />
</p>

<br>

<p align="center">
  <img src="screenshots/main.png" width="720" alt="3GP Converter — main window" />
</p>

---

## Why?

Millions of videos from the early smartphone era (2004–2012) were recorded in `.3gp` — a format that modern macOS, Photos, and most media apps can no longer open natively. **3GP Converter** brings those memories back to life in seconds, producing QuickTime-ready `.mp4` files that play everywhere.

---

## Features

### Intelligent Conversion Engine

Each file is analyzed individually. The converter picks the fastest, highest-quality path available:

| Source Resolution | Strategy | Result |
|:-|:-|:-|
| **480p or higher** | Stream copy (`-c:v copy -c:a copy`) | Instant, bit-for-bit identical quality |
| **Below 480p** | Re-encode with upscale (`libx264 -crf 22 -vf scale=-2:480`) | Clean 480p output with H.264 + AAC |
| **Stream copy fails** | Automatic fallback to full re-encode | Always produces a working file |

### Timestamp Preservation

Converted files keep the **exact original dates** — so your 2006 vacation videos still sort correctly in Photos, Finder, and any media library.

- **Modification time** — carried over via `touch -r`
- **macOS creation date** — restored with `SetFile -d` (preserves `st_birthtime`)
- **Container metadata** — original `creation_time` is logged for reference

### Batch Processing

Select a folder and every `.3gp` / `.3g2` file inside is queued automatically. Files that already have a matching `.mp4` are detected and skipped, so re-running is always safe. Originals are **never modified or deleted**.

### Real-Time Dashboard

Four live counters and a progress bar track the job as it runs:

| Counter | Meaning |
|:--------|:--------|
| **Total** | Files discovered in the folder |
| **Converted** | Successfully processed |
| **Skipped** | Output `.mp4` already existed |
| **Failed** | Errors during conversion |

### Colour-Coded Log

A terminal-style log scrolls in real time with colour-coded output:

- **White** — file headers and progress markers
- **Green** — successful operations
- **Amber** — skipped files and warnings
- **Red** — errors and failures

### Dark-Themed Native UI

Built with tkinter and styled with a modern dark zinc palette. Feels right at home on macOS — no Electron, no web views, no bloat.

---

## Requirements

| Dependency | Install |
|:-----------|:--------|
| **macOS 12 Monterey** or later | — |
| [**Homebrew**](https://brew.sh) | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| **ffmpeg** | `brew install ffmpeg` |
| **Xcode Command Line Tools** | `xcode-select --install` |

> **Note:** Xcode CLT provides `SetFile`, which is used to restore macOS creation dates. The converter works without it, but timestamps won't be fully preserved.

---

## Installation

### Option A — Download the App (Recommended)

1. Go to [**Releases**](https://github.com/bytePatrol/3GP_To_Quicktime/releases/latest)
2. Download **`3GP.Converter.dmg`**
3. Open the DMG and drag **3GP Converter** into your Applications folder
4. Launch from Spotlight or Launchpad

> **First launch:** macOS may show a Gatekeeper warning because the app is not notarised. Right-click the app → **Open** to bypass it.

### Option B — Run from Source

```bash
git clone https://github.com/bytePatrol/3GP_To_Quicktime.git
cd 3GP_To_Quicktime

brew install ffmpeg
xcode-select --install

python3 convert_3gp.py
```

### Option C — Build Your Own .app

```bash
pip3 install py2app
python3 setup.py py2app
open dist/
```

---

## Usage

1. **Launch** 3GP Converter
2. Click **Browse…** and select the folder containing your `.3gp` / `.3g2` files
3. Click **Scan & Convert**
4. Watch the live log and counters — converted `.mp4` files appear alongside the originals

---

## How It Works

```
For each .3gp / .3g2 file in the selected folder:
  │
  ├─ .mp4 already exists? → Skip
  │
  ├─ ffprobe: read video height
  │     │
  │     ├─ ≥ 480p → stream copy (fast, lossless)
  │     │     ├─ success → preserve timestamps ✓
  │     │     └─ failure → fall through ↓
  │     │
  │     └─ < 480p or unknown → re-encode + upscale to 480p
  │           └─ preserve timestamps ✓
  │
  └─ Restore original dates (touch + SetFile)
```

---

## Configuration

Constants at the top of [`convert_3gp.py`](convert_3gp.py) can be edited:

```python
FFMPEG  = "/opt/homebrew/bin/ffmpeg"   # Path to ffmpeg
FFPROBE = "/opt/homebrew/bin/ffprobe"  # Path to ffprobe
SETFILE = "/usr/bin/SetFile"           # Path to SetFile (Xcode CLT)

COPY_TIMEOUT   = 300   # Stream-copy timeout (seconds)
ENCODE_TIMEOUT = 600   # Re-encode timeout (seconds)
```

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
