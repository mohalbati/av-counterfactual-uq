# CARLA 3D demo: setup on Windows 11 (ASUS ROG Strix G16, RTX 4060 Laptop)

The script `scripts/carla_demo.py` recreates the report's rear-end conflicts in the CARLA driving simulator. It places up to four lanes side by side on a straight highway (Town04), each with a lead car that brakes at t = 0 and a follower that responds at a different response time. It records a drone view, a chase camera and a dashcam, with a front radar and a collision sensor on every follower, and saves an MP4 to `results/`.

## Your hardware (checked from dxdiag, 30 Oct 2026)

| | This laptop | CARLA 0.9.15 needs |
|---|---|---|
| GPU | NVIDIA GeForce RTX 4060 Laptop, 8 GB | RTX 2070 or better, 8 GB recommended |
| CPU / RAM | i7-13650HX / 16 GB | fine |
| Free disk | 518 GB | about 20 GB |
| OS | Windows 11 Home | Windows 10/11 |

Use CARLA **0.9.15** (Unreal Engine 4). CARLA 1.0 (Unreal Engine 5) needs 16 GB of video memory.

## One-time setup (about 30 minutes, mostly download)

1. **Make CARLA use the NVIDIA card.** The laptop also has Intel graphics. Plug in the charger, then open Windows Settings → System → Display → Graphics, add `CarlaUE4\Binaries\Win64\CarlaUE4-Win64-Shipping.exe` (after step 2) and set it to **High performance (NVIDIA)**. In Armoury Crate, use *Performance* or *Turbo* mode.
2. **Download CARLA 0.9.15 for Windows** from the release page, https://github.com/carla-simulator/carla/releases/tag/0.9.15 (`CARLA_0.9.15.zip`, about 10 GB packed). Extract it to `C:\CARLA_0.9.15` (the simulator is then at `C:\CARLA_0.9.15\WindowsNoEditor\CarlaUE4.exe`). The script uses Town04, which is in the main package.
3. **Install the Microsoft Visual C++ Redistributable (x64)** if Windows does not have it yet.
4. **Install Python 3.10** (64-bit, e.g. 3.10.11) from python.org. CARLA 0.9.15 only has Windows packages for Python 3.7–3.10, so 3.11 or newer will not work. Python versions can sit side by side; `py -3.10` picks 3.10.
5. **Install the Python packages** in a Command Prompt:
   ```
   py -3.10 -m pip install carla==0.9.15 numpy pillow imageio[ffmpeg]
   ```
   If `carla` fails to install, use the wheel that ships with CARLA instead:
   `py -3.10 -m pip install C:\CARLA_0.9.15\PythonAPI\carla\dist\carla-0.9.15-cp310-cp310-win_amd64.whl` (use the file name that is in that folder).

## Each time you make a video

1. Start the simulator and wait until the city view appears (first start takes a minute or two):
   ```
   C:\CARLA_0.9.15\WindowsNoEditor\CarlaUE4.exe -quality-level=Epic
   ```
   If it stutters, use `-quality-level=Low`. Allow it through the Windows firewall (ports 2000–2001, local only).
2. In a second Command Prompt, go to the repository folder and run:
   ```
   py -3.10 scripts\carla_demo.py
   ```
   The CARLA window follows the cars live while the MP4 is written to `results\carla_S02.mp4`.

`RUN_CARLA_DEMO.bat` in the repository folder does both steps (double-click it).

## Options

| Command | What it does |
|---|---|
| `--scenario S09` | any of S01–S16 from the report |
| `--speed 80 --headway 1.0 --decel 8` | your own numbers (km/h, s, m/s²) |
| `--drivers p10 mean p90 ads` | up to four lanes: `mean`, `pNN` percentile driver, `rt:X` manual response time in s, `ads` |
| `--town Town05` | another map (Town04 is the default) |
| `--focus ads` | which lane the chase and dash cameras follow |
| `--weather WetCloudySunset` | any CARLA weather preset, e.g. `HardRainNoon`, `ClearSunset` |
| `--slow 0.25` | playback speed of the video |
| `--dry-run` | print the model results only, without CARLA |

## How the demo relates to the report

- Lead braking, ramp-up time, response times and braking profiles come from the report's model (Eqs. 1–11), with the same nominal parameters.
- CARLA's physics engine moves the cars at the commanded speeds, so its gaps can differ from the model by a few tenths of a metre.
- Contact is detected by CARLA's collision sensor. After impact the script stops commanding the cars and CARLA's physics takes over, so post-crash motion in the video is CARLA's, not the report's.
- The ADS lane is the report's generic illustrative ADS, not Waymo's system.

## If something goes wrong

- **"time-out of 60000ms while waiting for the simulator"**: the simulator is not running or not fully loaded. Wait for the city view, then run the script again.
- **"No straight multi-lane stretch found"**: use a lower `--speed` or fewer `--drivers`.
- **Very slow or out of video memory**: start CARLA with `-quality-level=Low`, close other GPU programs, and check that step 1 of the setup was done.
- **Script stopped halfway**: restart CarlaUE4.exe, because a crashed run can leave the simulator in synchronous mode.
