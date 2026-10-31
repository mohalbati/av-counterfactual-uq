"""Figures for the simulator section of the report (results/simulators/).
    python scripts/simulator_figures.py
Needs ffmpeg on the PATH (to grab stills from results/video_S02.mp4)."""
import os, subprocess
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "results", "simulators"); os.makedirs(OUT, exist_ok=True)
INK, MUT, BLUE, ORANGE, GREY = "#14213D", "#5B6472", "#2A78D6", "#EB6834", "#D5DAE0"

# 1. stills from the MP4
vid = os.path.join(ROOT, "results", "video_S02.mp4")
frames = []
for t in (4, 9, 14):
    f = os.path.join(OUT, f"_frame{t}.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", vid, "-frames:v", "1", f], check=True)
    frames.append(Image.open(f).convert("RGB").resize((960, 540)))
sheet = Image.new("RGB", (960 * 3 + 40, 540), "white")
for i, im in enumerate(frames):
    sheet.paste(im, (i * 980, 0))
sheet.save(os.path.join(OUT, "video_frames.png"))
for t in (4, 9, 14):
    os.remove(os.path.join(OUT, f"_frame{t}.png"))


def box(ax, x, y, w, h, title, body, fc="#FFFFFF", ec=GREY, tc=INK, bs=9.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.4))
    ax.text(x + 0.12, y + h - 0.2, title, fontsize=11.5, weight="bold", color=tc, va="top")
    ax.text(x + 0.12, y + h - 0.58, body, fontsize=bs, color=MUT if tc == INK else tc, va="top", linespacing=1.45)


def arrow(ax, x0, y0, x1, y1, label=None):
    ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.4))
    if label:
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.12, label, fontsize=8.8, color=MUT, ha="center")


# 2. how the three tools share one model
fig, ax = plt.subplots(figsize=(13, 4.6)); ax.set_xlim(0, 13); ax.set_ylim(0, 4.6); ax.axis("off")
box(ax, 0.2, 1.3, 3.0, 2.2, "Report model (Python)", "src/cfuq: Eqs. 1–18\nnominal parameters, Table 4\nscenarios S01–S16", fc="#EEF3FB", ec=BLUE)
box(ax, 4.4, 3.0, 3.9, 1.45, "Browser simulator", "rear-end-sim.html · JavaScript port\nsliders, animation, 10,000-run check", ec=BLUE)
box(ax, 4.4, 1.5, 3.9, 1.3, "2D video", "make_video.py · matplotlib + ffmpeg\n4 lanes, half speed, MP4", ec=BLUE)
box(ax, 4.4, 0.1, 3.9, 1.25, "CARLA 3D demo", "carla_demo.py · CARLA 0.9.15\ncameras, radar, collision sensor", ec=ORANGE)
box(ax, 9.4, 3.0, 3.4, 1.45, "Explore and teach", "any inputs, live; shareable link\nchecks against Table 6", ec=GREY)
box(ax, 9.4, 1.5, 3.4, 1.3, "Present", "slides, talks, README\nsame numbers as the report", ec=GREY)
box(ax, 9.4, 0.1, 3.4, 1.25, "Demonstrate realism", "3D scene, sensor views\nphysics engine after impact", ec=GREY)
for y in (3.7, 2.15, 0.72):
    arrow(ax, 3.2, 2.4, 4.4, y)
    arrow(ax, 8.3, y, 9.4, y)
ax.text(1.7, 1.05, "same equations and parameters\nin all three tools", fontsize=9, color=MUT, ha="center", va="top")
fig.savefig(os.path.join(OUT, "three_tools.png"), dpi=170, bbox_inches="tight", facecolor="white"); plt.close(fig)

# 3. CARLA pipeline (one simulation tick)
fig, ax = plt.subplots(figsize=(14.5, 3.9)); ax.set_xlim(0, 14.5); ax.set_ylim(-0.5, 3.9); ax.axis("off")
steps = [("1  Model", "speed profiles from\nEqs. 1–11 (5 ms steps)\nfor every lane"),
         ("2  Commands", "set_target_velocity()\nbrake lights on when\ndeceleration > 0.3 m/s²"),
         ("3  CARLA server", "synchronous tick\nΔt = slow ÷ fps\nphysics substeps ≤ 10 ms"),
         ("4  Sensors", "3 RGB cameras, front\nradar, collision sensor\non each follower"),
         ("5  Compositor", "drone + chase + dash\ntelemetry table, gap chart\n→ 1920×1080 frame"),
         ("6  MP4", "imageio-ffmpeg, H.264\nresults/carla_S02.mp4")]
w = 2.2
for i, (t, b) in enumerate(steps):
    x = 0.15 + i * 2.42
    box(ax, x, 0.9, w, 2.1, t, b, ec=ORANGE if i in (2, 3) else BLUE, bs=9.0)
    if i:
        arrow(ax, x - 0.2, 1.95, x, 1.95)
ax.annotate("", (0.15 + w / 2, 0.85), (0.15 + 3 * 2.42 + w / 2, 0.85),
            arrowprops=dict(arrowstyle="-|>", color=MUT, lw=1.2, connectionstyle="arc3,rad=-0.12", ls="--"))
ax.text(4.0, -0.4, "after contact: stop commanding that lane; CARLA's physics moves the cars, both brake fully",
        fontsize=9.4, color=MUT, ha="center")
fig.savefig(os.path.join(OUT, "carla_pipeline.png"), dpi=170, bbox_inches="tight", facecolor="white"); plt.close(fig)

# 4. CARLA output frame layout
fig, ax = plt.subplots(figsize=(9.6, 5.4)); ax.set_xlim(0, 1920); ax.set_ylim(1080, 0); ax.axis("off")
def panel(x, y, w, h, t, s, fc):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec="white", lw=3))
    ax.text(x + w / 2, y + h / 2 - 18, t, ha="center", va="center", fontsize=13, weight="bold", color="white")
    ax.text(x + w / 2, y + h / 2 + 26, s, ha="center", va="center", fontsize=9.5, color="#E8ECF1")
panel(0, 0, 1280, 720, "Drone camera (1280×720)", "behind and above all lanes, follows the group", "#2A3B55")
panel(1280, 0, 640, 360, "Chase camera", "7 m behind the focus car", "#34486A")
panel(1280, 360, 640, 360, "Dashcam", "on the focus car's hood", "#34486A")
panel(0, 720, 1280, 360, "Telemetry table", "lane · response time · speed · true gap · radar · status", "#1B2129")
panel(1280, 720, 640, 360, "Gap chart", "gap vs time, one line per lane", "#1B2129")
fig.savefig(os.path.join(OUT, "carla_layout.png"), dpi=150, bbox_inches="tight", facecolor="white"); plt.close(fig)
print("wrote", sorted(os.listdir(OUT)))
