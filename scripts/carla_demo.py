"""
CARLA 3D demo of the rear-end conflicts in the technical report.

Up to four lanes side by side on a straight CARLA highway. In every lane a lead
car brakes at t = 0 exactly as in Eq. (1); the follower in each lane starts
braking at its own response time (10th-percentile, mean and 90th-percentile
NIEON-type driver from Eqs. 4-10, and the generic ADS, Eq. 13) and brakes as in
Eq. (11). Speeds come from the report's kinematic model; CARLA's physics engine
moves the cars, detects contact with a collision sensor and takes over after
impact. Each follower carries a front radar.

Output: one MP4 (1920x1080) with a drone view, a chase camera and a dashcam of
the focus lane, a telemetry table and a live gap chart.

Requirements: CARLA 0.9.15 server running (CarlaUE4.exe), and in Python:
    pip install carla==0.9.15 numpy pillow imageio[ffmpeg]

Usage examples:
    python scripts/carla_demo.py                       # S02, four drivers
    python scripts/carla_demo.py --scenario S09 --focus mean --weather WetCloudySunset
    python scripts/carla_demo.py --speed 80 --headway 1.0 --decel 8 --drivers p10 mean p90 ads
    python scripts/carla_demo.py --drivers rt:1.2 rt:2.0 ads --slow 0.5
    python scripts/carla_demo.py --dry-run             # model only, no CARLA needed
"""
import argparse, math, os, queue, sys, time
from statistics import NormalDist

# ----------------------------------------------------------------------------
# Report model (same equations and parameters as src/cfuq)
# ----------------------------------------------------------------------------
DT = 0.005
W, D_EYE, LOOM = 1.8, 2.0, 0.05          # m, m, rad/s
RT_M, RT_K, CV = 0.63, 0.47, 0.40        # Engstrom et al. (2024) fit; CV nominal
NIEON_AMAX, NIEON_JERK = 7.5, 20.0       # m/s^2, m/s^3 (nominal of assumed ranges)
ADS_LAT, ADS_AMAX, ADS_JERK = 0.55, 8.0, 30.0
LEAD_JERK = 12.5
SCEN = {"S01": (43.2, 0.49, 6.13), "S02": (96.48, 0.92, 6.55), "S03": (57.96, 0.45, 8.84), "S04": (110.16, 1.20, 8.02),
        "S05": (45.72, 1.46, 8.37), "S06": (72.0, 1.40, 7.17), "S07": (51.84, 1.34, 6.87), "S08": (55.8, 0.73, 9.50),
        "S09": (91.44, 1.16, 7.70), "S10": (64.08, 0.83, 7.93), "S11": (106.2, 0.64, 9.05), "S12": (68.4, 1.00, 8.51),
        "S13": (100.08, 0.59, 6.27), "S14": (78.84, 1.54, 7.42), "S15": (83.52, 0.32, 5.94), "S16": (86.76, 1.07, 5.70)}


def dec(t, t0, j, a):
    return min(max((t - t0) * j, 0.0), a)


def ramp_up_time(v0, h, aL, jL):
    """Eq. (6): time until looming (follower at constant speed) reaches 0.05 rad/s."""
    x, vL, t = h * v0, v0, 0.0
    while t < 12:
        d = max(x, 0.01) + D_EYE
        if W * (v0 - vL) / (d * d + W * W / 4) >= LOOM:
            return t
        if x <= 0:
            return math.inf
        vn = max(vL - dec(t, 0, jL, aL) * DT, 0.0)
        x += (0.5 * (vL + vn) - v0) * DT; vL = vn; t += DT
    return math.inf


def response_time(rut, pct=None, cv=CV):
    """Eqs. (7) and (10): mean driver if pct is None, else the given percentile."""
    mu = RT_M + RT_K * (rut if math.isfinite(rut) else 10.0)
    if pct is None:
        return mu
    s = math.sqrt(math.log(1 + cv * cv)); z = NormalDist().inv_cdf(pct / 100)
    return mu * math.exp(s * z - 0.5 * s * s)


def speed_profile(v0, rt, amax, jerk, aL, jL, t_end):
    """Commanded speeds of lead and follower (follower brakes freely; contact is left to CARLA).
    Also returns the model's own predicted contact (t, closing speed) for the telemetry."""
    n = int(t_end / DT) + 2
    vL, vS, x = [v0] * n, [v0] * n, h_glob * v0
    aS = [0.0] * n; aLl = [0.0] * n; contact = None
    for i in range(1, n):
        t = (i - 1) * DT
        aLl[i - 1] = dec(t, 0, jL, aL) if vL[i - 1] > 0 else 0.0
        aS[i - 1] = dec(t, rt, jerk, amax) if vS[i - 1] > 0 else 0.0
        vL[i] = max(vL[i - 1] - dec(t, 0, jL, aL) * DT, 0.0)
        vS[i] = max(vS[i - 1] - dec(t, rt, jerk, amax) * DT, 0.0)
        xn = x + (0.5 * (vL[i - 1] + vL[i]) - 0.5 * (vS[i - 1] + vS[i])) * DT
        if contact is None and xn <= 0:
            f = x / max(x - xn, 1e-12)
            contact = (t + f * DT, (vS[i - 1] + f * (vS[i] - vS[i - 1])) - (vL[i - 1] + f * (vL[i] - vL[i - 1])))
        x = xn
    return vL, vS, aLl, aS, contact


def at(arr, t):
    return arr[min(len(arr) - 1, max(0, int(round(t / DT))))]


# ----------------------------------------------------------------------------
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--scenario", default="S02", choices=sorted(SCEN))
ap.add_argument("--speed", type=float, help="km/h (overrides scenario)")
ap.add_argument("--headway", type=float, help="s (overrides scenario)")
ap.add_argument("--decel", type=float, help="lead deceleration m/s^2 (overrides scenario)")
ap.add_argument("--lead-jerk", type=float, default=LEAD_JERK)
ap.add_argument("--drivers", nargs="+", default=["p10", "mean", "p90", "ads"],
                help="up to 4 of: mean, pNN (percentile driver, e.g. p10), rt:X (manual response time in s), ads")
ap.add_argument("--focus", default="mean", help="which driver the chase and dash cameras follow")
ap.add_argument("--town", default="Town04", help="Town04 (highway loop, in the main package) or Town06 (needs AdditionalMaps)")
ap.add_argument("--weather", default="ClearNoon", help="any carla.WeatherParameters preset, e.g. WetCloudySunset, HardRainNoon")
ap.add_argument("--slow", type=float, default=0.5, help="playback speed of the video (0.5 = half speed)")
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--host", default="localhost"); ap.add_argument("--port", type=int, default=2000)
ap.add_argument("--out", default=None)
ap.add_argument("--dry-run", action="store_true", help="print the model results without CARLA")
A = ap.parse_args()

v_kph, h_glob, aL = SCEN[A.scenario]
v_kph = A.speed or v_kph; h_glob = A.headway or h_glob; aL = A.decel or aL
v0 = v_kph / 3.6; jL = A.lead_jerk
rut = ramp_up_time(v0, h_glob, aL, jL)

COLORS = {"ads": "235,104,52", "mean": "42,120,214", "low": "111,168,242", "high": "23,74,143"}
lanes = []
for d in A.drivers[:4]:
    if d == "ads":
        lanes.append(dict(key=d, name="Generic ADS", rt=ADS_LAT, amax=ADS_AMAX, jerk=ADS_JERK, color=COLORS["ads"]))
    elif d == "mean":
        lanes.append(dict(key=d, name="Mean driver", rt=response_time(rut), amax=NIEON_AMAX, jerk=NIEON_JERK, color=COLORS["mean"]))
    elif d.startswith("p"):
        p = float(d[1:])
        lanes.append(dict(key=d, name=f"{p:g}th-pct driver", rt=response_time(rut, p), amax=NIEON_AMAX, jerk=NIEON_JERK,
                          color=COLORS["low"] if p < 50 else COLORS["high"]))
    elif d.startswith("rt:"):
        r = float(d[3:])
        lanes.append(dict(key=d, name=f"Driver RT {r:.2f} s", rt=r, amax=NIEON_AMAX, jerk=NIEON_JERK, color=COLORS["mean"]))
    else:
        sys.exit(f"unknown driver '{d}'")
T_END = 12.0
for L in lanes:
    L["vL"], L["vS"], L["aL"], L["aS"], L["model_contact"] = speed_profile(v0, L["rt"], L["amax"], L["jerk"], aL, jL, T_END)

print(f"Scenario {A.scenario}: {v_kph:.0f} km/h, headway {h_glob:.2f} s (gap {h_glob*v0:.1f} m), lead {aL:.2f} m/s^2; RUT {rut:.2f} s")
for L in lanes:
    c = L["model_contact"]
    print(f"  {L['name']:<18} RT {L['rt']:.2f} s  model: " + (f"impact at {c[0]:.2f} s, {c[1]*3.6:.1f} km/h" if c else "avoided"))
if A.dry_run:
    sys.exit(0)

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import carla

# ----------------------------------------------------------------------------
# CARLA setup
# ----------------------------------------------------------------------------
client = carla.Client(A.host, A.port); client.set_timeout(60.0)
world = client.get_world()
if not world.get_map().name.endswith(A.town):
    print("loading", A.town, "..."); world = client.load_world(A.town)
cmap = world.get_map()
orig = world.get_settings()
dt_tick = A.slow / A.fps                    # simulated seconds per video frame
st = world.get_settings(); st.synchronous_mode = True; st.fixed_delta_seconds = dt_tick
st.substepping = True; st.max_substep_delta_time = 0.01; st.max_substeps = 10
world.apply_settings(st)
world.set_weather(getattr(carla.WeatherParameters, A.weather))
tm = client.get_trafficmanager(); tm.set_synchronous_mode(True)
bp = world.get_blueprint_library()
actors = []
world_time = [-1.0]


def same_dir_neighbors(wp, n):
    """Return up to n adjacent driving lanes in the same direction, starting with wp."""
    out = [wp]
    for side in ("get_right_lane", "get_left_lane"):
        w = wp
        while len(out) < n:
            w = getattr(w, side)()
            if w is None or w.lane_type != carla.LaneType.Driving or w.lane_id * wp.lane_id <= 0:
                break
            out.append(w)
    return out


# distance the cars travel: 1 s warm-up, then the lead's stopping distance; the follower starts behind
AHEAD = int(40 + v0 * 1.0 + v0 * v0 / (2 * aL) + v0 * aL / jL + 30)
BEHIND = int(max(30, h_glob * v0 + 20 - 40))


def straightness(wp, ahead=AHEAD, behind=BEHIND):
    yaw0 = wp.transform.rotation.yaw
    pts = [w for d in range(10, ahead, 10) for w in wp.next(d)[:1]] + [w for d in range(10, behind, 10) for w in wp.previous(d)[:1]]
    if len(pts) < (ahead + behind) // 10 - 3:
        return 999
    return max(abs((w.transform.rotation.yaw - yaw0 + 180) % 360 - 180) for w in pts)


print("searching the map for a straight multi-lane stretch ...")
cands = []
for sp in cmap.get_spawn_points():
    w0 = cmap.get_waypoint(sp.location, lane_type=carla.LaneType.Driving)
    for k in range(0, 8):                       # also try points further along the road
        wp = w0 if k == 0 else (w0.next(25 * k) or [None])[0]
        if wp is None:
            break
        nb = same_dir_neighbors(wp, len(lanes))
        cands.append((-min(len(nb), len(lanes)), straightness(wp), wp, nb))
cands = [c for c in cands if c[1] <= 6]
if not cands:
    sys.exit(f"No straight stretch of {AHEAD + BEHIND} m found in {A.town}; try a lower --speed or another --town.")
cands.sort(key=lambda c: (c[0], c[1]))
_, curv, base, lane_wps = cands[0]
if len(lane_wps) < len(lanes):
    keep = [L for L in lanes if L["key"] == A.focus][:1]
    keep += [L for L in lanes if L not in keep][: len(lane_wps) - len(keep)]
    print(f"only {len(lane_wps)} lanes here; showing: " + ", ".join(L["name"] for L in keep))
    lanes = [L for L in lanes if L in keep]
best = (curv,)
print(f"road found: {len(lane_wps)} lanes, max heading change {best[0]:.1f} deg over {AHEAD + BEHIND} m")

lead_bp = bp.find("vehicle.lincoln.mkz_2020") if bp.filter("vehicle.lincoln.mkz_2020") else bp.filter("vehicle.*")[0]
fol_bp = bp.find("vehicle.tesla.model3")


def spawn(blueprint, tf, color=None):
    if color and blueprint.has_attribute("color"):
        blueprint.set_attribute("color", color)
    tf.location.z += 0.4
    a = world.try_spawn_actor(blueprint, tf)
    if a is None:
        raise RuntimeError("spawn failed; restart the CARLA server and retry")
    actors.append(a); return a


try:
    for L, wp in zip(lanes, lane_wps):
        lead = spawn(lead_bp, wp.next(40)[0].transform, "220,224,230")
        L["lead"] = lead
        world.tick()
        ext_l = lead.bounding_box.extent.x
        L["ext_l"] = ext_l
        fol_wp = wp.next(40)[0].previous(h_glob * v0 + ext_l + 2.4)[0]
        fol = spawn(fol_bp, fol_wp.transform, L["color"])
        L["fol"] = fol; L["ext_f"] = fol.bounding_box.extent.x
        L["hit"] = None; L["radar"] = None
        col = world.spawn_actor(bp.find("sensor.other.collision"), carla.Transform(), attach_to=fol); actors.append(col)
        col.listen(lambda e, L=L: L.__setitem__("hit", L["hit"] or (world_time[0], e.normal_impulse.length())))
        rb = bp.find("sensor.other.radar")
        for k, v in (("horizontal_fov", "8"), ("vertical_fov", "4"), ("range", "100"), ("points_per_second", "3000")):
            rb.set_attribute(k, v)
        rad = world.spawn_actor(rb, carla.Transform(carla.Location(x=L["ext_f"] + 0.1, z=0.7)), attach_to=fol); actors.append(rad)
        rad.listen(lambda m, L=L: L.__setitem__("radar", min((d.depth for d in m), default=None)))

    focus = next((L for L in lanes if L["key"] == A.focus), lanes[len(lanes) // 2])
    cams = {}
    def cam(name, w, h, fov, tf, parent=None):
        b = bp.find("sensor.camera.rgb")
        b.set_attribute("image_size_x", str(w)); b.set_attribute("image_size_y", str(h)); b.set_attribute("fov", str(fov))
        c = world.spawn_actor(b, tf, attach_to=parent) if parent else world.spawn_actor(b, tf)
        q = queue.Queue(); c.listen(q.put); actors.append(c); cams[name] = q; return c
    drone = cam("drone", 1280, 720, 70, carla.Transform(carla.Location(z=50)))
    cam("chase", 640, 360, 90, carla.Transform(carla.Location(x=-7.0, z=2.8), carla.Rotation(pitch=-10)), focus["fol"])
    cam("dash", 640, 360, 90, carla.Transform(carla.Location(x=1.4, z=1.45), carla.Rotation(pitch=-3)), focus["fol"])

    fwd = base.transform.get_forward_vector()
    right = base.transform.get_right_vector()
    def setv(a, v):
        a.set_target_velocity(carla.Vector3D(fwd.x * v, fwd.y * v, 0.0))

    # warm-up: bring everything to speed with the gaps preserved
    for _ in range(int(1.0 / dt_tick)):
        for L in lanes:
            setv(L["lead"], v0); setv(L["fol"], v0)
        world.tick()
        spectator = world.get_spectator()
        spectator.set_transform(carla.Transform(focus["fol"].get_location() - fwd * 14 + carla.Location(z=22), carla.Rotation(pitch=-38, yaw=base.transform.rotation.yaw)))
        for q in cams.values():
            while not q.empty():
                q.get()
    for L in lanes:          # ignore any contact while the cars settled on the road
        L["hit"] = None

    try:
        font = ImageFont.truetype("arial.ttf", 22); fsm = ImageFont.truetype("arial.ttf", 18); fbig = ImageFont.truetype("arialbd.ttf", 26)
    except OSError:
        font = fsm = fbig = ImageFont.load_default()
    out = A.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"carla_{A.scenario}.mp4")
    writer = imageio.get_writer(out, fps=A.fps, codec="libx264", quality=8, macro_block_size=8)
    hist = {id(L): [] for L in lanes}
    t, t_stop = 0.0, None
    LIGHT_BRAKE = carla.VehicleLightState(carla.VehicleLightState.Brake | carla.VehicleLightState.Position)
    LIGHT_OFF = carla.VehicleLightState(carla.VehicleLightState.Position)

    print("recording ...")
    while True:
        world_time[0] = t
        for L in lanes:
            if L["hit"] is None:
                vl, vs = at(L["vL"], t), at(L["vS"], t)
                setv(L["lead"], vl); setv(L["fol"], vs)
                L["lead"].set_light_state(LIGHT_BRAKE if at(L["aL"], t) > 0.3 else LIGHT_OFF)
                L["fol"].set_light_state(LIGHT_BRAKE if at(L["aS"], t) > 0.3 else LIGHT_OFF)
                if vs <= 0:
                    L["fol"].apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
                if vl <= 0:
                    L["lead"].apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))
            else:   # after impact, CARLA's physics takes over; both drivers brake fully
                for a in (L["lead"], L["fol"]):
                    a.apply_control(carla.VehicleControl(brake=1.0)); a.set_light_state(LIGHT_BRAKE)
        # drone camera: behind and above the group, looking down the road
        mid = focus["fol"].get_location()
        lane_mid = sum((L["fol"].get_location() for L in lanes[1:]), lanes[0]["fol"].get_location())
        lane_mid = carla.Location(lane_mid.x / len(lanes), lane_mid.y / len(lanes), mid.z)
        cl = lane_mid - fwd * 14 + carla.Location(z=22)
        drone.set_transform(carla.Transform(cl, carla.Rotation(pitch=-38, yaw=base.transform.rotation.yaw)))
        world.get_spectator().set_transform(carla.Transform(cl, carla.Rotation(pitch=-38, yaw=base.transform.rotation.yaw)))
        frame = world.tick()
        imgs = {}
        for k, q in cams.items():
            while True:
                im = q.get(timeout=10.0)
                if im.frame >= frame:
                    break
            imgs[k] = Image.fromarray(np.frombuffer(im.raw_data, np.uint8).reshape(im.height, im.width, 4)[:, :, 2::-1].copy())

        # telemetry
        rows = []
        for L in lanes:
            lf, ff = L["lead"].get_transform(), L["fol"].get_transform()
            dvec = lf.location - ff.location
            gap = dvec.x * fwd.x + dvec.y * fwd.y - L["ext_l"] - L["ext_f"]
            vs = L["fol"].get_velocity().length(); vlv = L["lead"].get_velocity().length()
            hist[id(L)].append((t, max(gap, 0.0)))
            if L["hit"]:
                status = f"IMPACT ({L['model_contact'][1]*3.6:.0f} km/h per model)" if L["model_contact"] else "IMPACT"
            elif vs < 0.05 and t > L["rt"]:
                status = f"stopped {gap:.1f} m short"
            elif t < L["rt"]:
                status = "not braking yet"
            else:
                status = f"braking {at(L['aS'], t):.1f} m/s²"
            rows.append((L, vs * 3.6, gap, L["radar"], status))

        canvas = Image.new("RGB", (1920, 1080), (18, 22, 28))
        canvas.paste(imgs["drone"], (0, 0)); canvas.paste(imgs["chase"], (1280, 0)); canvas.paste(imgs["dash"], (1280, 360))
        dr = ImageDraw.Draw(canvas)
        for (x, y, s) in ((10, 8, f"Drone view · {A.scenario} · {v_kph:.0f} km/h · gap {h_glob*v0:.1f} m · lead {aL:.2f} m/s²"),
                          (1290, 8, f"Chase camera · {focus['name']}"), (1290, 368, f"Dashcam · {focus['name']}")):
            dr.rectangle((x - 6, y - 4, x + dr.textlength(s, font=fsm) + 6, y + 22), fill=(18, 22, 28)); dr.text((x, y), s, font=fsm, fill=(232, 236, 241))
        dr.text((1890, 690), f"t = {t:5.2f} s  ({A.slow:g}× speed)", font=fbig, fill=(232, 236, 241), anchor="rd")
        # table
        y = 740
        dr.text((20, y), "Lane", font=fsm, fill=(154, 165, 179)); dr.text((300, y), "Resp. time", font=fsm, fill=(154, 165, 179))
        dr.text((440, y), "Speed", font=fsm, fill=(154, 165, 179)); dr.text((560, y), "Gap (true)", font=fsm, fill=(154, 165, 179))
        dr.text((700, y), "Radar", font=fsm, fill=(154, 165, 179)); dr.text((820, y), "Status", font=fsm, fill=(154, 165, 179))
        for k, (L, spd, gap, rad, status) in enumerate(rows):
            yy = y + 36 + k * 40; col = tuple(int(c) for c in L["color"].split(","))
            dr.rectangle((20, yy + 4, 34, yy + 18), fill=col)
            dr.text((44, yy), L["name"], font=font, fill=(232, 236, 241)); dr.text((300, yy), f"{L['rt']:.2f} s", font=font, fill=(232, 236, 241))
            dr.text((440, yy), f"{spd:5.1f}", font=font, fill=(232, 236, 241)); dr.text((560, yy), f"{max(gap,0):5.1f} m", font=font, fill=(232, 236, 241))
            dr.text((700, yy), f"{rad:5.1f} m" if rad else "  –", font=font, fill=(232, 236, 241))
            dr.text((820, yy), status, font=font, fill=(255, 138, 128) if "IMPACT" in status else (126, 226, 168) if "stopped" in status else (232, 236, 241))
        dr.text((20, 1050), f"Ramp-up time {rut:.2f} s · speeds from the report's model (Eqs. 1–11); contact by CARLA's collision sensor; radar = front radar range.",
                font=fsm, fill=(154, 165, 179))
        # gap chart
        X0, Y0, X1, Y1 = 1300, 760, 1900, 1040; gmax = h_glob * v0 * 1.15; tmax = 6.0
        dr.text((1300, 728), "Gap (m) over time", font=fsm, fill=(154, 165, 179))
        dr.rectangle((X0, Y0, X1, Y1), outline=(46, 55, 66))
        for L in lanes:
            pts = [(X0 + (X1 - X0) * min(tt, tmax) / tmax, Y1 - (Y1 - Y0) * g / gmax) for tt, g in hist[id(L)]]
            if len(pts) > 1:
                dr.line(pts, fill=tuple(int(c) for c in L["color"].split(",")), width=3)
        writer.append_data(np.asarray(canvas))

        done = all(L["hit"] or (L["fol"].get_velocity().length() < 0.05 and t > L["rt"]) for L in lanes)
        if done and t_stop is None:
            t_stop = t
        if (t_stop is not None and t > t_stop + 1.5) or t > 9.0:
            break
        t += dt_tick
    writer.close()
    print("wrote", os.path.abspath(out))
    for L in lanes:
        print(f"  {L['name']:<18} CARLA: " + (f"collision at {L['hit'][0]:.2f} s" if L["hit"] else "no collision"))
finally:
    world.apply_settings(orig)
    tm.set_synchronous_mode(False)
    for a in actors:
        try:
            if a.type_id.startswith("sensor"):
                a.stop()
            a.destroy()
        except RuntimeError:
            pass
