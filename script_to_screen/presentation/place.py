"""A place: the room a scene happens in, drawn behind (and a little in front of) the entities.

A place is a file in the show's `places/` folder: a wall colour, a floor colour, and pieces
standing along the same line of slots the entities use. A piece is a kind (door, window, sofa,
lamp, plant, picture, table, shelf, rug, counter, fridge, thermostat, pedestal, vase, shards,
plate, and the pieces of the houses' homes: rack, inkpad, page, dome, post, pegboard, crate, chain, gate, hooks,
bag, ropes, crumbs, ghost, gantry, wallstub, mark, parts, and the council chamber's: crest, hammermark, lockmark,
crownmark, bench, banner, bookwall, books, inkwell, pen, desklamp, nails, hasplate, pot, tree, sapling).

A place can have one `light: {at, up, color, reach, strength, side}`: a pool of that colour on the wall and floor, a lit side and
a shadow side on everything that stands in it, and a shadow behind each. `grade: {color, amount}` tints the whole frame and
`vignette:` darkens its corners. A piece with `depth: far` is drawn hazed and behind the rest; `depth: front` is a dark shape
between us and the scene.

An `arch` is a hole in the wall: it shows the place's `sky:` colour, and `sun: <0 to 1>` on one arch puts the sun in it at that
height, so the hour is told by the sky and never by a clock.

A place can also have a raised `bench: {from, to, rise, front, color}`: whoever stands between those slots sits up behind
it, with a plate at their seat (an entity's `plate:` is what the plate says), where it stands (`at`, a slot), and optionally how wide it is (`wide`, in slots), how
far `up` it sits (pixels: a plate on a table), a `color`, and `depth: front` to stand it between
the entities and the camera. A piece given a `color` keeps it in every style, so the thing a
scene is about stands out from the room. A place can start `like:` another and change only what
differs (a kitchen at night is the kitchen with dark walls and a moonlit `window:` colour).

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
ON_WALL = ("door", "window", "picture", "shelf", "thermostat", "vault", "sign", "page", "dome", "pegboard", "chain", "hooks", "ghost", "crest", "hammermark", "lockmark", "crownmark", "banner", "bookwall", "pen", "desklamp", "nails", "hasplate", "arch", "cornice", "vine")
ON_FLOOR = ("rug", "shards", "crumbs", "mark")
COLORS = dict(door="#cdbb9d", window="#b9c2c4", picture="#b7a58c", sofa="#9fb0aa", lamp="#b9a98c", plant="#8fa58a", table="#b49f84",
              shelf="#b49f84", rug="#c9b6a6", counter="#b9b3a2", fridge="#c5cbcc", thermostat="#d8d2c4", pedestal="#c2b8a6", vase="#5b7fa6",
              shards="#5b7fa6", plate="#f4f1e8", vault="#9aa3a8", sign="#b9b3a2",
              rack="#a89784", inkpad="#4a4a52", page="#efe9dc", dome="#c7d3d6", post="#9aa3a8", pegboard="#b49f84", crate="#b49f84",
              chain="#8f969b", gate="#8f969b", hooks="#8f969b", bag="#9c5a48", ropes="#b7a58c", crumbs="#d9a3ae", ghost="#c9c5bb",
              gantry="#a8906c", wallstub="#b9b3a2", mark="#8f969b", parts="#9fb0aa", crest="#7a2e3b", hammermark="#6b5a4a", lockmark="#7f868c", crownmark="#b7a58c", bench="#b49f84", banner="#7a2e3b", bookwall="#7b5a4c", pen="#2e3440", desklamp="#c9a45a", nails="#8f969b", hasplate="#8f969b", inkwell="#27303f", books="#7b5a4c", pot="#8a5f47", tree="#5d8a55", sapling="#7fb069", arch="#3a2a2e", cornice="#3a2a2e", vine="#6aa85c")


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
    if kind == "vault":
        return [("body", rect(-96, -330, 192, 330, 6)), ("dark", oval(0, -168, 78, 78)), ("body", oval(0, -168, 64, 64)), ("dark", oval(0, -168, 14, 14)),
                ("line", poly((-52, -168), (52, -168), (-52, -168))), ("line", poly((0, -220), (0, -116), (0, -220))), ("dark", rect(70, -190, 16, 44, 4))]
    if kind == "sign":
        w = w or 150
        return [("body", rect(-w / 2, -350, w, 44, 6)), ("light", rect(-w / 2 + 12, -338, w - 24, 8, 3)), ("light", rect(-w / 2 + 12, -324, w - 60, 6, 3))]
    if kind == "counter":
        w = w or 300
        return [("body", rect(-w / 2, -96, w, 96, 4)), ("dark", rect(-w / 2 - 6, -106, w + 12, 12, 3)), ("line", rect(-w / 2 + 14, -80, w / 2 - 22, 66, 3)),
                ("line", rect(8, -80, w / 2 - 22, 66, 3))]
    if kind == "fridge":
        return [("body", rect(-62, -310, 124, 310, 10)), ("line", poly((-62, -200), (62, -200), (-62, -200))), ("dark", rect(40, -262, 7, 44, 3)),
                ("dark", rect(40, -184, 7, 70, 3))]
    if kind == "thermostat":
        return [("body", rect(-26, -286, 52, 52, 12)), ("light", oval(0, -260, 15, 15)), ("dark", oval(5, -265, 3.5, 3.5))]
    if kind == "pedestal":
        return [("body", rect(-22, -118, 44, 118)), ("dark", rect(-32, -128, 64, 12, 3)), ("dark", rect(-30, -10, 60, 10, 2))]
    if kind == "vase":
        return [("body", oval(0, -34, 26, 34)), ("body", rect(-11, -84, 22, 30, 5)), ("dark", rect(-15, -90, 30, 8, 3))]
    if kind == "shards":
        return [("body", poly((-34, 0), (-20, -14), (-10, 0))), ("dark", poly((-2, 2), (10, -18), (22, 2))), ("body", poly((30, 4), (40, -8), (52, 4))),
                ("dark", poly((-56, 6), (-48, -4), (-42, 6)))]
    if kind == "plate":
        return [("body", oval(0, -3, 34, 6)), ("line", poly((-18, -8), (22, -12), (-18, -8))), ("line", poly((-16, -5), (24, -8), (-16, -5)))]
    if kind == "rack":                                               # a rack of slots, where seals stand in rows
        w = w or 320
        slots = [("dark", rect(x - 3, -64, 6, 30)) for x in range(int(-w / 2) + 20, int(w / 2) - 10, 44)]
        return [("dark", rect(-w / 2 + 8, -34, 8, 34)), ("dark", rect(w / 2 - 16, -34, 8, 34)), ("body", rect(-w / 2, -40, w, 12, 3))] + slots
    if kind == "inkpad":
        return [("body", rect(-56, -18, 112, 18, 4)), ("dark", rect(-46, -26, 92, 10, 3))]
    if kind == "page":                                               # a sheet on the wall, stamped over and over
        w = w or 190
        marks = [("dark", oval(-w / 2 + 34 + 42 * i + (9 if j % 2 else 0), -318 + 34 * j, 15, 13)) for j in range(4) for i in range(int((w - 40) // 42))]
        return [("light", rect(-w / 2, -346, w, 150, 2))] + marks
    if kind == "dome":                                               # a glass dome over a round hall
        w = w or 700
        arc = skia.Path()
        arc.moveTo(-w / 2, -150)
        arc.arcTo(skia.Rect.MakeLTRB(-w / 2, -150 - 290, w / 2, -150 + 290), 180, 180, False)
        arc.close()
        ribs = [("line", poly((x, -150), (x * 0.55, -150 - 290 * (1 - (x / (w / 2)) ** 2) ** 0.5 * 0.98), (x, -150))) for x in (-w / 3, 0, w / 3)]
        return [("light", arc)] + ribs + [("body", rect(-w / 2 - 12, -156, w + 24, 12, 3))]
    if kind == "post":                                               # a pivot post for a needle
        return [("dark", rect(-14, -6, 28, 6, 2)), ("dark", rect(-3, -64, 6, 60)), ("body", oval(0, -68, 7, 7))]
    if kind == "pegboard":                                           # a board with a painted outline for each hammer
        w = w or 300
        outs = []
        for i in range(int((w - 40) // 70)):
            x = -w / 2 + 44 + 70 * i
            outs += [("line", rect(x - 22, -330, 44, 20, 3)), ("line", rect(x - 5, -310, 10, 86, 3))]
        return [("body", rect(-w / 2, -350, w, 160, 4))] + outs
    if kind == "crate":
        return [("body", rect(-48, -84, 96, 84, 2)), ("dark", rect(-52, -92, 104, 10, 2)), ("line", poly((-48, -56), (48, -56), (-48, -56))),
                ("line", poly((-48, -28), (48, -28), (-48, -28)))]
    if kind == "chain":
        return [("line", oval(0, y, 7 if i % 2 else 4, 13)) for i, y in enumerate(range(-372, -170, 22))] + [("dark", rect(-12, -172, 24, 30, 5))]
    if kind == "gate":                                               # bars, fastened
        w = w or 260
        bars = [("body", rect(x - 5, -330, 10, 330)) for x in range(int(-w / 2) + 12, int(w / 2), 34)]
        return bars + [("dark", rect(-w / 2, -334, w, 12, 3)), ("dark", rect(-w / 2, -180, w, 12, 3)), ("dark", rect(-w / 2, -30, w, 12, 3))]
    if kind == "hooks":                                              # a rail of hooks, where pairs hang by their laces
        w = w or 300
        return [("body", rect(-w / 2, -300, w, 9, 3))] + [("dark", rect(x - 3, -292, 6, 26, 3)) for x in range(int(-w / 2) + 24, int(w / 2), 56)]
    if kind == "bag":                                                # a punching bag, split
        return [("line", poly((0, -372), (0, -300), (0, -372))), ("body", rect(-36, -300, 72, 176, 30)), ("dark", poly((-6, -250), (10, -200), (-4, -150), (6, -200))),
                ("light", oval(18, -122, 16, 9)), ("light", oval(-22, -4, 20, 8)), ("light", oval(30, -2, 13, 6))]
    if kind == "ropes":                                              # a ring whose ropes have gone slack
        w = w or 420
        sag = [("line", poly((-w / 2, y), (-w / 6, y + 26), (w / 5, y + 34), (w / 2, y + 6), (w / 5, y + 34), (-w / 6, y + 26))) for y in (-150, -104, -58)]
        return [("dark", rect(-w / 2 - 8, -170, 16, 170, 4)), ("dark", rect(w / 2 - 8, -150, 16, 150, 4))] + sag
    if kind == "crumbs":                                             # what rubbing leaves
        w = w or 300
        return [("body", oval(-w / 2 + (i * 53) % w, ((i * 29) % 30) - 12, 5 + i % 4, 3)) for i in range(int(w // 22))]
    if kind == "ghost":                                              # what is left of a drawing that has been rubbed out
        w = w or 360
        return [("line", poly((-w / 2, -300), (-w / 6, -300), (-w / 2, -300))), ("line", poly((w / 8, -260), (w / 2, -260), (w / 8, -260))),
                ("line", poly((-w / 3, -210), (-w / 3, -330), (-w / 3, -210))), ("line", rect(w / 5, -340, w / 5, 50, 2))]
    if kind == "gantry":                                             # bare timber overhead, and no roof
        w = w or 520
        return [("dark", rect(-w / 2, -384, 14, 384)), ("dark", rect(w / 2 - 14, -384, 14, 384)), ("body", rect(-w / 2 - 16, -396, w + 32, 16, 2)),
                ("line", poly((-w / 2 + 14, -300), (-w / 2 + 96, -384), (-w / 2 + 14, -300))), ("line", poly((w / 2 - 14, -300), (w / 2 - 96, -384), (w / 2 - 14, -300)))]
    if kind == "wallstub":                                           # a wall built true, and stopped
        w = w or 240
        courses = [("line", poly((-w / 2, y), (w / 2, y), (-w / 2, y))) for y in range(-168, 0, 28)]
        return [("body", rect(-w / 2, -196, w, 196))] + courses
    if kind == "mark":                                               # a mark on the floor under a bob
        return [("line", poly((-16, 0), (16, 0), (-16, 0))), ("line", poly((0, -5), (0, 5), (0, -5)))]
    if kind == "parts":                                              # a thing taken to pieces, laid out in order of size
        w = w or 420
        n = 8
        return [("body", rect(-w / 2 + i * w / n, -(8 + 9 * i), w / n - 14, 8 + 9 * i, 2)) for i in range(n)]
    if kind == "crest":                                              # Signet's emblem: a seal's face
        return [("body", oval(0, -300, 46, 46)), ("light", oval(0, -300, 34, 34)), ("body", oval(0, -300, 20, 20)), ("light", oval(0, -300, 8, 8))]
    if kind == "hammermark":                                         # Mallet's emblem
        return [("body", oval(0, -300, 46, 46)), ("light", oval(0, -300, 38, 38)), ("body", rect(-24, -328, 48, 20, 3)), ("body", rect(-5, -310, 10, 40, 3))]
    if kind == "lockmark":                                           # Hasp's emblem
        arc = skia.Path()
        arc.addRoundRect(skia.Rect.MakeLTRB(-13, -330, 13, -292), 13, 13)
        return [("body", oval(0, -300, 46, 46)), ("light", oval(0, -300, 38, 38)), ("body", arc), ("light", rect(-6, -322, 12, 24, 6)), ("body", rect(-20, -304, 40, 28, 4))]
    if kind == "bookwall":                                           # ledgers standing on end: at this scale, a wall
        w = w or 360
        out, x, i = [], -w / 2, 0
        while x < w / 2 - 20:
            bw, bh = 34 + (i * 17) % 30, 250 + (i * 53) % 130
            out += [("body" if i % 3 else "dark", rect(x, -bh, bw, bh, 5)), ("light", rect(x + 6, -bh + 34, bw - 12, 12, 3)), ("line", poly((x + 6, -bh + 60), (x + bw - 6, -bh + 60), (x + 6, -bh + 60)))]
            x, i = x + bw + 3, i + 1
        return out
    if kind == "books":                                              # ledgers lying in a stack
        w = w or 240
        return [s for i in range(4) for s in (("body" if i % 2 else "dark", rect(-w / 2 + (i * 23) % 28, -52 * (i + 1), w - 26, 50, 8)),
                                              ("light", rect(-w / 2 + (i * 23) % 28 + 10, -52 * (i + 1) + 8, 14, 34, 3)))]
    if kind == "inkwell":                                            # an ink bottle, as big as a column
        return [("body", rect(-66, -190, 132, 190, 26)), ("light", rect(-44, -142, 88, 70, 8)), ("body", rect(-30, -232, 60, 48, 6)), ("dark", rect(-38, -256, 76, 28, 8))]
    if kind == "arch":                                               # an open arch: a hole in the wall, with the sky in it
        w = w or 120
        def opening(dx):
            p = skia.Path()
            p.moveTo(-w / 2 + dx, -170)
            p.lineTo(-w / 2 + dx, -170 - 1.25 * w)
            p.arcTo(skia.Rect.MakeLTRB(-w / 2 + dx, -170 - 1.25 * w - w / 2, w / 2 + dx, -170 - 1.25 * w + w / 2), 180, 180, False)
            p.lineTo(w / 2 + dx, -170)
            p.close()
            return p
        return [("dark", opening(-w * 0.07)), ("light", opening(w * 0.05))]         # the thickness of the wall shows down one side
    if kind == "vine":                                               # growth hanging over an arch: the building has been lived in a long time
        w = w or 120
        out = []
        for i in range(5):
            x, drop = -w / 2 + 8 + i * (w - 16) / 4, 54 + (i * 47) % 78
            out.append(("dark", rect(x - 1.5, -382, 3, drop, 1)))
            out += [("body", oval(x + (7 if j % 2 else -7), -376 + j * 17, 9, 5.5, 30 if j % 2 else -30)) for j in range(1, int(drop // 17) + 1)]
        return out
    if kind == "cornice":                                            # the ledge between one tier of arches and the next
        w = w or 1200
        return [("dark", rect(-w / 2, -428, w, 12, 2))]
    if kind == "pot":                                                # a planter, for a tree or a sapling
        return [("body", poly((-56, -70), (56, -70), (44, 0), (-44, 0))), ("dark", rect(-62, -84, 124, 18, 6)), ("dark", oval(0, -78, 48, 7))]
    if kind == "tree":                                               # a grown tree: years of it
        return [("dark", poly((-11, -74), (11, -74), (7, -250), (-7, -250))), ("dark", poly((0, -180), (44, -236), (38, -244), (-2, -196))),
                ("dark", oval(-52, -300, 58, 52)), ("body", oval(48, -292, 62, 56)), ("body", oval(-30, -346, 64, 58)), ("body", oval(22, -384, 56, 50)),
                ("dark", oval(64, -250, 34, 30)), ("body", oval(-6, -296, 60, 50))]
    if kind == "sapling":                                            # a new one, staked: planted not long ago
        return [("line", poly((14, -74), (14, -178), (14, -74))), ("dark", poly((-3, -74), (3, -74), (2, -160), (-2, -160))),
                ("body", oval(-15, -150, 17, 9, -32)), ("body", oval(15, -166, 17, 9, 32)), ("body", oval(0, -182, 9, 17))]
    if kind == "pen":                                                # a pen leaning against the wall
        return [("body", poly((-150, 0), (-128, -8), (120, -388), (98, -380))), ("light", poly((-150, 0), (-128, -8), (-112, -34), (-134, -26))),
                ("dark", poly((98, -380), (120, -388), (132, -408), (110, -400)))]
    if kind == "desklamp":                                           # the lamp over the desk: here, the sun
        return [("dark", rect(-4, -560, 8, 180)), ("body", poly((-34, -392), (34, -392), (92, -318), (-92, -318))), ("light", oval(0, -316, 60, 12))]
    if kind == "nails":                                              # a row of nail heads: Mallet's work
        w = w or 300
        return [("body", oval(x, -214, 5, 5)) for x in range(int(-w / 2), int(w / 2) + 1, 42)]
    if kind == "hasplate":                                           # a hasp and staple on the wall: Hasp's work
        return [("body", rect(-40, -300, 80, 34, 6)), ("dark", oval(-22, -283, 5, 5)), ("dark", oval(22, -283, 5, 5)), ("body", rect(-10, -272, 20, 34, 8)), ("light", rect(-4, -262, 8, 16, 4))]
    if kind == "banner":                                             # a flag hung from the top of the wall, for whoever rules
        w = w or 150
        return [("body", poly((-w / 2, -520), (w / 2, -520), (w / 2, -236), (0, -200), (-w / 2, -236))), ("dark", rect(-w / 2 - 8, -444, w + 16, 8, 3))]
    if kind == "crownmark":                                          # the crown itself, over the chamber
        return [("body", poly((-34, -366), (-40, -398), (-18, -382), (0, -404), (18, -382), (40, -398), (34, -366)))]
    if kind == "bench":                                              # the council's bench
        w = w or 700
        return [("dark", rect(-w / 2, -64, w, 10, 3)), ("body", rect(-w / 2 + 8, -54, w - 16, 54))] + [("line", poly((x, -54), (x, 0), (x, -54))) for x in range(int(-w / 2) + 90, int(w / 2), 90)]
    raise ValueError(f"a place has no piece of kind '{kind}'; the kinds are: " + ", ".join(sorted(COLORS)))


class Painter:
    """One way of drawing a place. A style is which colour each role gets, and whether it is filled, outlined or shadowed."""

    def __init__(self, style, place):
        self.style = style
        self.wall, self.floor = place.get("wall", "#e7e1d3"), place.get("floor", "#d6cdbb")
        if style == "line":
            self.wall = self.floor = "#f5f3ee"
        self.ink = "#aaa497"
        self.window = place.get("window", "#fffdf6")                      # what is seen through a window: daylight, or a night sky
        self.sky, self.sun = place.get("sky", self.window), place.get("sun", "#fff4d6")       # what is seen through an open arch
        self.dark = sum(rgb(self.wall)) < 330                               # in a dark room, solid things are a step lighter than the wall, not darker
        self.shade = "#aab3c8" if self.dark else "#2e2a24"
        self.line = place.get("ink")                                        # an inked place: every shape gets a drawn outline in this colour, as in a comic
        self.deep = self.line or "#3a332a"                                  # what a colour is mixed toward to darken it

    def room(self, c, W, H, base):
        c.drawRect(skia.Rect.MakeLTRB(-W, -1.2 * H, 2 * W, base), paint(self.wall))
        c.drawRect(skia.Rect.MakeLTRB(-W, base, 2 * W, 1.35 * H), paint(self.floor))
        if self.style == "line":
            c.drawLine(-W, base, 2 * W, base, pen(self.ink, 2))
        else:
            c.drawRect(skia.Rect.MakeLTRB(-W, base - 12, 2 * W, base), paint(mix(self.wall, self.floor, 0.5)))    # a skirting board
            if self.line:
                c.drawLine(-W, base - 12, 2 * W, base - 12, pen(self.line, 3))
                c.drawLine(-W, base, 2 * W, base, pen(self.line, 3))

    def piece(self, c, piece, on_floor=False, front=False):
        kind, color = piece["kind"], piece.get("color") or COLORS[piece["kind"]]
        if piece.get("depth") == "far":                                    # far off: paler, hazed toward the wall
            color = mix(color, self.wall, 0.62)
        under, own = self.floor if on_floor else self.wall, piece.get("color")
        lit = self.window if kind == "window" else mix(under, self.shade, 0.28) if self.dark and kind != "lamp" else "#fffdf6"   # in the dark, only windows and lamps are bright
        if kind == "arch":                                                  # through an arch you see the sky, whatever the hour
            lit = self.sky
        for role, path in shapes(kind, piece.get("_w")):
            if self.style == "line":
                if role == "line":
                    c.drawPath(path, pen(self.ink, 2))
                    continue
                c.drawPath(path, paint("#ffffff" if role == "light" else self.ink if role == "dark" else self.wall))
                c.drawPath(path, pen(self.ink, 2.5))
            elif self.style == "paper":
                if front:                                                   # between us and the scene: a dark shape, nothing more
                    if role != "line":
                        c.drawPath(path, paint(mix(self.floor, "#0f0d10", 0.55)))
                    continue
                if piece.get("depth") == "far":
                    if role != "line":
                        c.drawPath(path, paint(mix(color, self.wall, 0.25) if role == "dark" else mix(color, "#fbf8ef", 0.12) if role == "light" else color))
                    continue
                if role == "line":
                    c.drawPath(path, pen(self.line, 2.2) if self.line else pen(mix(color, "#3a332a", 0.25), 2, 150))
                    continue
                if role == "body" and not on_floor and not self.line:
                    c.save()
                    c.translate(7, 9)
                    c.drawPath(path, paint("#3a332a", 20))                   # cut paper sits a little off the wall
                    c.restore()
                sky = kind == "arch" and role == "light"
                if sky and isinstance(self.sky, list):                       # a sky of two colours: the first overhead, the second at the horizon
                    top, low = (skia.Color(*rgb(k)) for k in self.sky)
                    c.drawPath(path, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear([skia.Point(0, path.getBounds().top()), skia.Point(0, path.getBounds().bottom())], [top, low])))
                else:
                    c.drawPath(path, paint((self.sky if kind == "arch" else "#fbf8ef" if not self.dark else mix("#fbf8ef", self.wall, 0.22)) if role == "light" else mix(color, self.deep, 0.3) if role == "dark" else color))
                if kind == "arch" and role == "light" and piece.get("sun"):  # and, in one of them, the sun: low for evening or morning, high for noon
                    c.save()
                    c.clipPath(path, True)
                    w = piece.get("_w") or 120
                    c.drawCircle(w * 0.08, -170 - float(piece["sun"]) * 1.25 * w, w * 0.3, paint(self.sun))
                    c.restore()
                if self.line:                                               # line weight is nearness: the wall is drawn lightly, what stands in the room firmly
                    c.drawPath(path, pen(mix(self.line, self.wall, 0.45), 1.4 if kind == "vine" else 2) if kind in QUIET else pen(self.line, 3))
            else:                                                           # wash: one hue, a step darker for what is solid, lighter for what is lit
                if front:
                    c.drawPath(path, paint(mix(self.floor, "#2e2a24", 0.42 if role != "light" else 0.34)) if role != "line" else pen(self.floor, 0, 0))
                    continue
                if role == "line":
                    c.drawPath(path, pen(mix(under, self.shade, 0.16), 2, 160))
                    continue
                if own:                                                     # a piece given its own colour keeps it: it is what the scene is about
                    c.drawPath(path, paint(lit if role == "light" else mix(own, "#2e2a24", 0.3) if role == "dark" else own))
                else:
                    c.drawPath(path, paint(lit if role == "light" else mix(under, self.shade, 0.20) if role == "dark" else mix(under, self.shade, 0.10)))

    def light(self, c, piece, base):
        """What a lit piece throws into the room. Only the wash style paints with light."""
        if self.style != "wash":
            return
        if piece["kind"] == "window":
            w = piece.get("_w") or 210
            pool = poly((-w / 2 + 40, base + 14), (w / 2 + 40, base + 14), (w / 2 + 230, base + 150), (-w / 2 + 130, base + 150))
            r, g, b = rgb(self.window)
            p = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, base + 14), skia.Point(0, base + 150)], [skia.Color(r, g, b, 120 if sum(rgb(self.wall)) >= 330 else 60), skia.Color(r, g, b, 0)]))
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
        layer = "front" if raw.get("depth") == "front" else "floor" if piece["kind"] in ON_FLOOR else "wall" if piece["kind"] in ON_WALL or raw.get("depth") == "far" else "back"
        layers[layer].append(piece)
    layers["wall"].sort(key=lambda p: p.get("depth") != "far")                # what is far is drawn first
    return layers


def bench_top(bench):
    """How high the top of a room's bench stands above the floor: where its sitters' plates are, and where a thing put on it stands."""
    return float(bench.get("rise", 58)) + float(bench.get("front", 30)) + 9


def cast_lean(lamp):
    """How far sideways a cast shadow runs for each unit of height: away from the side the light is on, and further the longer the shadows."""
    return (0.5 if lamp.get("side", "left") == "left" else -0.5) * float(lamp.get("cast", 0))


def shade_of(place):
    """The colour of a cast shadow in this place: its own `shade:` if it gives one, else its cool shadow colour, darkened."""
    return place.get("shade") or mix(place.get("shadow") or "#120c14", "#120c14", 0.45)


QUIET = ("arch", "cornice", "vine")            # the wall itself: in an inked place these get a thin, soft line so the room stays behind the people


SHADE = 0.5                                   # how dark a cast shadow is, at full light


def sunlit(stage):
    """Where the sun (or moon) behind the room reaches the floor: the shape of each open arch, thrown across the floor the way
    the room's shadows fall. A flag hung over an arch stops the light where it covers it. -> one path, in stage pixels."""
    kept = getattr(stage, "_sunlit", None)
    if kept is not None:
        return kept
    place = stage.look.place
    if getattr(stage, "_place", None) is None:
        stage._place = prepare(place, stage.W)
    lamp, base = place.get("light") or {}, ground(stage.H) - FLOOR_UP
    cast = float(lamp.get("cast", 0))
    lean = cast_lean(lamp)

    def on_wall(piece, role):                                              # a piece's shapes of one role, where they are on the wall
        out = skia.Path()
        for r, path in shapes(piece["kind"], piece.get("_w")):
            if r == role:
                out.addPath(path, piece["_x"], base - float(piece.get("up", 0)))
        return out

    holes = skia.Path()
    for piece in stage._place["wall"]:
        if piece["kind"] == "arch":
            holes = skia.Op(holes, on_wall(piece, "light"), skia.PathOp.kUnion_PathOp)
    for piece in stage._place["wall"]:
        if piece["kind"] == "banner":
            holes = skia.Op(holes, on_wall(piece, "body"), skia.PathOp.kDifference_PathOp)
    thrown = skia.Path()
    holes.transform(skia.Matrix().setAll(1, -lean, lean * base, 0, -cast, base * (1 + cast), 0, 0, 1), thrown)      # a point h up the wall lands cast*h out on the floor
    stage._sunlit = thrown
    return thrown


def draw_behind(c, stage, cam):
    """The room and everything in it that stands behind the entities. Nothing in a room moves, so while the camera holds still the
    room is painted once and kept as a picture; it is painted afresh only while the camera is moving."""
    place, style = stage.look.place, stage.look.style.get("place", "wash")
    if not place or style == "none":
        return False
    key = (round(cam.zoom, 5), round(cam.cx, 3), round(cam.tilt, 5))
    kept = getattr(stage, "_room", None)
    if not kept or kept[0] != key:                                          # always by way of a picture, so a frame is the same whichever frame was drawn before it
        surf = skia.Surface(stage.W, stage.H)
        _paint_behind(surf.getCanvas(), stage, cam)
        kept = stage._room = (key, surf.makeImageSnapshot())
    c.drawImage(kept[1], 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear))
    return True


def _paint_behind(c, stage, cam):
    place, style = stage.look.place, stage.look.style.get("place", "wash")
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
            c.translate(piece["_x"], (foot if name != "wall" else base) - float(piece.get("up", 0)))
            if name == "wall":
                painter.light(c, dict(piece), 0) if piece["kind"] == "window" else None
            painter.piece(c, piece, on_floor=name == "floor")
            if piece["kind"] == "lamp":
                painter.light(c, piece, 0)
            c.restore()
        lamp = place.get("light")
        if lamp and name == "wall" and float(lamp.get("cast", 0)):          # the sun is behind the wall: the floor is in the wall's shade, but for what comes through the arches
            cast = float(lamp["cast"])
            lean = cast_lean(lamp)
            r, g, b = rgb(shade_of(place))
            floor = skia.Rect.MakeLTRB(-stage.W, base, 2 * stage.W, 1.35 * stage.H)
            if lamp.get("warm"):                                            # where the light lands it takes the light's colour: sun on a green floor is gold, not green
                c.save()
                c.clipRect(floor)
                c.drawPath(sunlit(stage), paint(lamp.get("color", "#f6c26b"), 255 * float(lamp["warm"])))
                c.restore()
            c.saveLayer(floor, skia.Paint(Alphaf=SHADE * float(lamp.get("strength", 0.7)),
                                         ColorFilter=skia.ColorFilters.Blend(skia.Color(r, g, b), skia.BlendMode.kSrcIn)))
            c.clipRect(floor)
            c.drawPath(skia.Op(skia.Path().addRect(floor), sunlit(stage), skia.PathOp.kDifference_PathOp), paint("#000000"))
            for piece in layers[name]:                                      # and what stands against the wall throws its own shadow into that light
                if piece["kind"] in ("pot", "tree", "sapling"):
                    c.save()
                    c.translate(piece["_x"], base)
                    c.concat(skia.Matrix().setAll(1, -lean, 0, 0, -cast, 0, 0, 0, 1))
                    for role, path in shapes(piece["kind"], piece.get("_w")):
                        if role != "line":
                            c.drawPath(path, paint("#000000"))
                    c.restore()
            c.restore()
        if lamp and name in ("wall", "floor"):                              # the room's one light: a pool on the wall, and a longer one on the floor
            r, g, b = rgb(lamp.get("color", "#f6c26b"))
            x, reach, k = slot_x(float(lamp.get("at", 4)), stage.W), float(lamp.get("reach", 520)), float(lamp.get("strength", 0.7))
            glow = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kScreen)
            if name == "wall":
                y = base - float(lamp.get("up", 240))
                glow.setShader(skia.GradientShader.MakeRadial(skia.Point(x, y), reach, [skia.Color(r, g, b, int(200 * k)), skia.Color(r, g, b, int(70 * k)), skia.Color(r, g, b, 0)], [0.0, 0.55, 1.0]))
                c.drawCircle(x, y, reach, glow)
            else:
                c.save()
                c.translate(x, gy + 60)
                c.scale(1.0, 0.28)
                glow.setShader(skia.GradientShader.MakeRadial(skia.Point(0, 0), reach * 1.1, [skia.Color(r, g, b, int(120 * k)), skia.Color(r, g, b, 0)]))
                c.drawCircle(0, 0, reach * 1.1, glow)
                c.restore()
            cool = place.get("shadow")                                      # and away from the light, everything goes to the shadow's colour
            if cool:
                r, g, b = rgb(cool)
                far = x + (1 if lamp.get("side", "left") == "left" else -1) * stage.W * 0.95
                c.drawRect(skia.Rect.MakeLTRB(-stage.W, -1.2 * stage.H, 2 * stage.W, 1.35 * stage.H), skia.Paint(BlendMode=skia.BlendMode.kMultiply, Shader=skia.GradientShader.MakeLinear(
                    [skia.Point(x, 0), skia.Point(far, 0)], [skia.Color(255, 255, 255), skia.Color(255, 255, 255), skia.Color(r, g, b)], [0.0, 0.3, 1.0])))
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
