# Badge Simulator

`badge_simulator.py` lets you run Octodoom locally by reproducing the `badgeware`
API on top of Pygame. Use it to iterate quickly without touching real hardware.

## Prerequisites
- Python 3.10 or newer (3.13 recommended).
- Pygame (`pip install pygame`).

## Setup

### Option 1: Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pygame
```

### Option 2: System Python

```bash
pip3 install pygame
```

## Quick Start

```bash
python3 simulator/badge_simulator.py badge/apps/octodoom
```

The simulator automatically:
- Uses `badge/` (relative to `simulator/`) as the system root — no flags needed for this repo's layout
- Looks for `__init__.py` when you specify a directory
- Sets the window title and icon based on the app
- Cleans up `__pycache__` directories when you exit

## Command Line Options

- `--scale` enlarges the 160×120 framebuffer so the window is easier to see (default is 4).
- `-C DIR` forces the simulator to treat `DIR` as `/system`. Not needed here since `badge/` is already the default — override it if you've moved things around.
- `--screenshots DIR` specifies a directory to save screenshots when you press F12. Screenshots are saved at native badge resolution (160×120) in PNG format.
- `--clean` removes all temporary files (cached downloads, saved state) before starting.
- `--perf` shows live performance metrics (FPS, CPU, and memory usage) in the terminal. Requires `psutil` (`pip install psutil`).

## Controls
- `A` / `Z` → Button A (turn left)
- `B` / `X` / `Space` → Button B (fire / confirm)
- `C` / arrow keys → Button C (turn right) — arrows also work as an alternate turn scheme
- `UP` / `DOWN` arrows → move forward / back
- `H` / `Esc` → Home (quit to the intro/menu screen)
- `F12` → Take screenshot (when `--screenshots` is configured)
- Close the window or press `Ctrl+C` in the terminal to stop the simulator.

## Examples

Run at a bigger window size:
```bash
python3 simulator/badge_simulator.py badge/apps/octodoom --scale 6
```

Capture screenshots as you play:
```bash
python3 simulator/badge_simulator.py badge/apps/octodoom --screenshots ./screenshots
```

Show live performance metrics:
```bash
python3 simulator/badge_simulator.py badge/apps/octodoom --perf
```

## Simulator Accuracy

**What's accurate:** display resolution (160×120), button mappings, 60 FPS target, the full drawing API (shapes, text, images), app lifecycle (`init`/`update`/`on_exit`), and state persistence between sessions.

**What's different:** desktop Python has far more memory and CPU headroom than the badge's actual RP2350 @ 200MHz — treat frame time and memory numbers from `--perf` as a lower bound, not a guarantee, of how it'll run on real hardware.
