"""A place: the room a scene happens in, drawn behind (and a little in front of) the entities.

A place is a file in the show's `places/` folder: a wall colour, a floor colour, and pieces
standing along the same line of slots the entities use. A piece is a kind (door, window, sofa,
lamp, plant, picture, table, shelf, rug), where it stands (`at`, a slot), and optionally how
wide it is (`wide`, in slots), a `color`, and `depth: front` to stand it between the entities
and the camera.

Every piece is built from shapes with a role (body, dark, light, line). A style decides what
each role looks like, so the same room can be drawn three ways (`style: {place: ...}`):

    wash    one hue: the room is tone and light, and the entities are the only colour (the default)
    paper   muted cut paper, each piece its own quiet colour, with a soft shadow
    line    ink outlines on bare paper
    none    no place is drawn

Layers sit at different depths, so they slide against each other when the camera moves.
"""
import skia

from .view import ground, slot_x

WALL_DEPTH, BACK_DEPTH, FRONT_DEPTH = 0.3, 0.15, -0.2
FLOOR_UP = 46                                 # how far behind the entities' feet the wall meets the floor, in pixels
ON_WALL = ("door", "window", "picture", "shelf")
COLORS = dict(door="#cdbb9d", window="#b9c2c4", picture="#b7a58c", sofa="#9fb0aa", lamp="#b9a98c", plant="#8fa58a", table="#b49f84",
              shelf="#b49f84", rug="#c9b6a6")


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, k):
    """Colour a moved a fraction k of the way to colour b."""
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(rgb(a), rgb(b)))


def paint(color, a=255):
    r, g, b = rgb(color)
    return skia.Paint(AntiAlias=True, Color=skia.Color(r, g, b, int(a)))


def pen(color, w, a=255):
    p = paint(color, a)
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(w)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    p.setStrokeCap(skia.Paint.kRound_Cap)
    return p


def rect(x, y, w, h, r=0):
    p = skia.Path()
    p.addRoundRect(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    return p


def poly(*pts):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def oval(cx, cy, rx, ry, turn=0):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    if turn:
        m = skia.Matrix()
        m.setRotate(turn, cx, cy + ry)
        p.transform(m)
    return p


def shapes(kind, w):
    """A piece as [(role, path)], back to front, standing on (0, 0) with up as negative y. `w` is its width in pixels."""
    if kind == "door":
        w = w or 150
        return [("body", rect(-w / 2 - 10, -338, w + 20, 338)), ("light", rect(-w / 2, -328, w, 328)),
                ("line", rect(-w / 2 + 18, -306, w - 36, 130, 3)), ("line", rect(-w / 2 + 18, -152, w - 36, 126, 3)), ("dark", oval(w / 2 - 20, -160, 6, 6))]
    if kind == "window":
        w = w or 210
        return [("body", rect(-w / 2 - 10, -372, w + 20, 222, 4)), ("light", rect(-w / 2, -362, w, 202)),
                ("body", rect(-3, -362, 6, 202)), ("body", rect(-w / 2, -264, w, 6)), ("body", rect(-w / 2 - 20, -154, w + 40, 12, 3))]
    if kind == "picture":
        w = w or 104
        return [("body", rect(-w / 2, -330, w, 78, 2)), ("light", rect(-w / 2 + 10, -320, w - 20, 58)), ("dark", oval(-w / 6, -284, w / 5, 12))]
    if kind == "shelf":
        w = w or 190
        return [("body", rect(-w / 2, -292, w, 10, 2)), ("dark", rect(-w / 2 + 14, -338, 16, 46)), ("body", rect(-w / 2 + 32, -330, 13, 38)),
                ("dark", rect(-w / 2 + 47, -344, 18, 52)), ("light", rect(-w / 2 + 67, -326, 12, 34)), ("dark", oval(w / 2 - 34, -308, 17, 16))]
    if kind == "sofa":
        w = w or 300
        return [("dark", rect(-w / 2 + 22, -12, 12, 12)), ("dark", rect(w / 2 - 34, -12, 12, 12)), ("body", rect(-w / 2 + 12, -150, w - 24, 110, 26)),
                ("body", rect(-w / 2, -96, 44, 86, 18)), ("body", rect(w / 2 - 44, -96, 44, 86, 18)), ("body", rect(-w / 2 + 30, -70, w - 60, 60, 12)),
                ("line", poly((0, -68), (0, -14), (0, -68)))]
    if kind == "lamp":
        return [("dark", rect(-26, -8, 52, 8, 4)), ("dark", rect(-3, -250, 6, 244)), ("light", poly((-30, -306), (30, -306), (46, -244), (-46, -244)))]
    if kind == "plant":
        leaves = [("dark", oval(0, -150, 18, 52, turn)) for turn in (-52, -26, 0, 26, 52)]
        return leaves + [("body", poly((-30, -60), (30, -60), (22, 0), (-22, 0)))]
    if kind == "table":
        w = w or 150
        return [("dark", rect(-w / 2 + 12, -62, 8, 62)), ("dark", rect(w / 2 - 20, -62, 8, 62)), ("body", rect(-w / 2, -72, w, 12, 4))]
    if kind == "rug":
        w = w or 420
        return [("body", oval(0, 0, w / 2, 26)), ("line", oval(0, 0, w / 2 - 22, 17))]
    raise ValueError(f"a place has no piece of kind '{kind}'; the kinds are: door, window, picture, shelf, sofa, lamp, plant, table, rug")


class Painter:
    """One way of drawing a place. A style is which colour each role gets, and whether it is filled, outlined or shadowed."""

    def __init__(self, style, place):
        self.style = style
        self.wall, self.floor = place.get("wall", "#e7e1d3"), place.get("floor", "#d6cdbb")
        if style == "line":
            self.wall = self.floor = "#f5f3ee"
        self.ink = "#aaa497"

    def room(self, c, W, H, base):
        c.drawRect(skia.Rect.MakeLTRB(-W, -1.2 * H, 2 * W, base), paint(self.wall))
        c.drawRect(skia.Rect.MakeLTRB(-W, base, 2 * W, 1.35 * H), paint(self.floor))
        if self.style == "line":
            c.drawLine(-W, base, 2 * W, base, pen(self.ink, 2))
        else:
            c.drawRect(skia.Rect.MakeLTRB(-W, base - 12, 2 * W, base), paint(mix(self.wall, self.floor, 0.5)))    # a skirting board

    def piece(self, c, piece, on_floor=False, front=False):
        kind, color = piece["kind"], piece.get("color") or COLORS[piece["kind"]]
        under = self.floor if on_floor else self.wall
        for role, path in shapes(kind, piece.get("_w")):
            if self.style == "line":
                if role == "line":
                    c.drawPath(path, pen(self.ink, 2))
                    continue
                c.drawPath(path, paint("#ffffff" if role == "light" else self.ink if role == "dark" else self.wall))
                c.drawPath(path, pen(self.ink, 2.5))
            elif self.style == "paper":
                if role == "line":
                    c.drawPath(path, pen(mix(color, "#3a332a", 0.25), 2, 150))
                    continue
                if role == "body" and not on_floor:
                    c.save()
                    c.translate(7, 9)
                    c.drawPath(path, paint("#3a332a", 20))                   # cut paper sits a little off the wall
                    c.restore()
                c.drawPath(path, paint("#fbf8ef" if role == "light" else mix(color, "#3a332a", 0.28) if role == "dark" else color))
            else:                                                           # wash: one hue, a step darker for what is solid, lighter for what is lit
                if front:
                    c.drawPath(path, paint(mix(self.floor, "#2e2a24", 0.42 if role != "light" else 0.34)) if role != "line" else pen(self.floor, 0, 0))
                    continue
                if role == "line":
                    c.drawPath(path, pen(mix(under, "#2e2a24", 0.16), 2, 160))
                    continue
                c.drawPath(path, paint("#fffdf6" if role == "light" else mix(under, "#2e2a24", 0.20) if role == "dark" else mix(under, "#2e2a24", 0.10)))

    def light(self, c, piece, base):
        """What a lit piece throws into the room. Only the wash style paints with light."""
        if self.style != "wash":
            return
        if piece["kind"] == "window":
            w = piece.get("_w") or 210
            pool = poly((-w / 2 + 40, base + 14), (w / 2 + 40, base + 14), (w / 2 + 230, base + 150), (-w / 2 + 130, base + 150))
            p = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, base + 14), skia.Point(0, base + 150)], [skia.Color(255, 253, 246, 120), skia.Color(255, 253, 246, 0)]))
            c.drawPath(pool, p)
        if piece["kind"] == "lamp":
            p = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
                skia.Point(0, -262), 210, [skia.Color(255, 250, 232, 105), skia.Color(255, 250, 232, 0)]))
            c.drawCircle(0, -262, 210, p)


def prepare(place, W):
    """Lay a place's pieces out in pixels, sorted into the layers they are drawn in."""
    layers = dict(wall=[], back=[], floor=[], front=[])
    spacing = slot_x(1, W) - slot_x(0, W)
    for raw in place.get("pieces") or []:
        piece = dict(raw, _x=slot_x(float(raw.get("at", 0)), W), _w=float(raw["wide"]) * spacing if raw.get("wide") else None)
        shapes(piece["kind"], piece["_w"])                                 # an unknown kind is refused here, once
        layer = "front" if raw.get("depth") == "front" else "floor" if piece["kind"] == "rug" else "wall" if piece["kind"] in ON_WALL else "back"
        layers[layer].append(piece)
    return layers


def draw_behind(c, stage, cam):
    """The room and everything in it that stands behind the entities."""
    place, style = stage.look.place, stage.look.style.get("place", "wash")
    if not place or style == "none":
        return False
    if getattr(stage, "_place", None) is None:
        stage._place = prepare(place, stage.W)
    layers, painter, gy = stage._place, Painter(style, place), ground(stage.H)
    base = gy - FLOOR_UP
    for name, depth, foot in (("wall", WALL_DEPTH, base), ("back", BACK_DEPTH, base + 18), ("floor", 0.0, gy + 34)):
        c.save()
        cam.apply(c, depth)
        if name == "wall":
            painter.room(c, stage.W, stage.H, base)
        for piece in layers[name]:
            c.save()
            c.translate(piece["_x"], foot if name != "wall" else base)
            if name == "wall":
                painter.light(c, dict(piece), 0) if piece["kind"] == "window" else None
            painter.piece(c, piece, on_floor=name == "floor")
            if piece["kind"] == "lamp":
                painter.light(c, piece, 0)
            c.restore()
        c.restore()
    return True


def draw_in_front(c, stage, cam):
    """Pieces between the entities and the camera: large, dark, and quick to slide when the camera moves."""
    place, style = stage.look.place, stage.look.style.get("place", "wash")
    if not place or style == "none" or not stage._place["front"]:
        return
    painter = Painter(style, place)
    c.save()
    cam.apply(c, FRONT_DEPTH)
    for piece in stage._place["front"]:
        c.save()
        c.translate(piece["_x"], stage.H + 70)                         # low in the frame: it may cross the floor, never a face
        c.scale(1.25, 1.25)
        painter.piece(c, piece, front=True)
        c.restore()
    c.restore()
