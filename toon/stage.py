"""Sets (layered paper at different depths) and the camera that looks at them."""
import math

from .paper import cut, oval, poly, rrect
from .puppet import CHEST, HEAD_MID

# framing -> (zoom, height above feet to aim at, lead room toward where the subject faces)
FRAMINGS = {"medium": (1.9, CHEST + 15, 40), "close": (3.0, HEAD_MID - 4, 28), "two": (1.45, CHEST, 0)}


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def cam_target(key, cast, W, H):
    """Resolve {framing, subject} to (centre x, centre y, zoom), kept inside the set."""
    framing = key.get("framing", "wide")
    if framing == "wide":
        return (W / 2, H / 2, 1.0)
    z, up, lead = FRAMINGS[framing]
    on = key["subject"]
    if isinstance(on, list):
        xs = [cast[n]["x"] for n in on]
        cx, cy = sum(xs) / len(xs), cast[on[0]]["ground"] - up
    else:
        st = cast[on]
        cx = st["x"] + (lead if st["facing"] == "right" else -lead)
        cy = st["ground"] - up * st.get("scale", 1.0)
    z = key.get("zoom", z)
    cx = min(max(cx, W / 2 / z), W - W / 2 / z)
    cy = min(max(cy, H / 2 / z), H - H / 2 / z)
    return (cx, cy, z)


def cam_at(camera, f, cast, W, H):
    """Camera at shot-local frame f. `camera` is one key (locked off) or a list of keys (a move)."""
    keys = camera if isinstance(camera, list) else [dict(camera, frame=0)]
    keys = sorted(keys, key=lambda k: k.get("frame", 0))
    prev = keys[0]
    for nxt in keys[1:]:
        if f >= nxt["frame"]:
            prev = nxt
            continue
        a, b = cam_target(prev, cast, W, H), cam_target(nxt, cast, W, H)
        k = smooth((f - prev.get("frame", 0)) / (nxt["frame"] - prev.get("frame", 0)))
        return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k,
                math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * k))
    return cam_target(prev, cast, W, H)


def layer_xform(c, cam, depth, W, H):
    """Far layers (depth < 1) slide and grow less than the character plane: parallax."""
    cx, cy, z = cam
    zl = 1 + (z - 1) * (0.55 + 0.45 * depth)
    c.translate(W / 2, H / 2)
    c.scale(zl, zl)
    c.translate(-(W / 2 + (cx - W / 2) * depth), -(H / 2 + (cy - H / 2) * depth))


def to_screen(cam, x, y, W, H):
    cx, cy, z = cam
    return ((x - cx) * z + W / 2, (y - cy) * z + H / 2)


def draw_shape(c, sh, key):
    kw = dict(key=key, shadow=sh.get("shadow", True), rough=sh.get("rough", 1.2))
    if "rect" in sh:
        cut(c, rrect(*sh["rect"], sh.get("r", 0)), sh["fill"], **kw)
    elif "oval" in sh:
        cut(c, oval(*sh["oval"]), sh["fill"], **kw)
    elif "poly" in sh:
        cut(c, poly(sh["poly"]), sh["fill"], **kw)
    elif "tiles" in sh:  # checker strip: [x, y, w, h, tile size]
        x0, y0, w, h, n = sh["tiles"]
        for j in range(int(h // n) + 1):
            for i in range(int(w // n) + 1):
                if (i + j) % 2 == 0:
                    cut(c, rrect(x0 + i * n, y0 + j * n, n, n), sh["fill"], key=f"{key}{i}.{j}", shadow=False, rough=0.8)


def draw_layers(c, layers, cam, W, H, lo, hi, set_id):
    for li, layer in enumerate(layers):
        if not (lo <= layer["depth"] < hi):
            continue
        c.save()
        layer_xform(c, cam, layer["depth"], W, H)
        for si, sh in enumerate(layer["shapes"]):
            draw_shape(c, sh, f"{set_id}{li}.{si}")
        c.restore()
