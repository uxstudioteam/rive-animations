#!/usr/bin/env python3
"""Generates scene.rml for the animated Arlo OG image.

The lettering comes from the landing page's arlo-union.svg (letters + dashed
outline); the avatar faces/glyphs are rebuilt from small-avatars.svg.
Run: python3 tools/gen.py  (from the project root)
"""
import math, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNION_SVG = os.path.join(ROOT, 'assets', 'arlo-union.svg')

W, H = 1200, 627
INK = 'FF1B1917'

# ---------------------------------------------------------------- ids
_next = [100]
def nid():
    _next[0] += 1
    return f'0:{_next[0]}'

# ---------------------------------------------------------------- svg paths
def parse_path(d):
    """Absolute M/L/H/V/C/Z only (all our sources use these). Returns a list of
    subpaths; each is a list of segments ('L', p0, p1) / ('C', p0, c1, c2, p1)."""
    toks = re.findall(r'[MLHVCZ]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?', d)
    i, subs, cur, start, pt, cmd = 0, [], None, None, None, None
    def num():
        nonlocal i
        v = float(toks[i]); i += 1; return v
    while i < len(toks):
        t = toks[i]
        if t in 'MLHVCZ':
            cmd = t; i += 1
            if cmd == 'Z':
                if cur is not None:
                    if pt != start:
                        cur.append(('L', pt, start))
                    subs.append(cur); cur = None; pt = start
                continue
        if cmd == 'M':
            if cur: subs.append(cur)
            pt = start = (num(), num()); cur = []; cmd = 'L'
        elif cmd == 'L':
            p = (num(), num()); cur.append(('L', pt, p)); pt = p
        elif cmd == 'H':
            p = (num(), pt[1]); cur.append(('L', pt, p)); pt = p
        elif cmd == 'V':
            p = (pt[0], num()); cur.append(('L', pt, p)); pt = p
        elif cmd == 'C':
            c1 = (num(), num()); c2 = (num(), num()); p = (num(), num())
            cur.append(('C', pt, c1, c2, p)); pt = p
    if cur: subs.append(cur)
    return subs

def f(v):
    s = f'{v:.3f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def points_path(segs, tf, closed=True, ind='    '):
    """segs -> <PointsPath> with vertices transformed by tf(x,y)."""
    segs = [s for s in segs if not (s[0] == 'L' and s[1] == s[2])]
    n = len(segs)
    verts = []
    for k, s in enumerate(segs):
        p = tf(*s[1])
        out_h = tf(*s[2]) if s[0] == 'C' else None
        prev = segs[k - 1] if (closed or k > 0) else None
        in_h = tf(*prev[3]) if prev is not None and prev[0] == 'C' else None
        verts.append((p, in_h, out_h))
    if not closed:  # last end point
        s = segs[-1]
        verts.append((tf(*s[-1]), tf(*s[3]) if s[0] == 'C' else None, None))
    # winding (y down: positive shoelace = clockwise)
    area = sum(verts[k][0][0] * verts[(k + 1) % len(verts)][0][1] -
               verts[(k + 1) % len(verts)][0][0] * verts[k][0][1] for k in range(len(verts)))
    lines = [f'{ind}<PointsPath isClosed="{"true" if closed else "false"}" '
             f'isClockwise="{"true" if area > 0 else "false"}" name="Path">']
    for p, ih, oh in verts:
        if ih is None and oh is None:
            lines.append(f'{ind}    <StraightVertex x="{f(p[0])}" y="{f(p[1])}"/>')
        else:
            def rd(h):
                if h is None: return 0.0, 0.0
                dx, dy = h[0] - p[0], h[1] - p[1]
                return math.atan2(dy, dx), math.hypot(dx, dy)
            ir, idist = rd(ih); orr, od = rd(oh)
            lines.append(f'{ind}    <CubicDetachedVertex x="{f(p[0])}" y="{f(p[1])}" '
                         f'inRotation="{f(ir)}" inDistance="{f(idist)}" '
                         f'outRotation="{f(orr)}" outDistance="{f(od)}"/>')
    lines.append(f'{ind}</PointsPath>')
    return '\n'.join(lines)

def fill(c, ind):
    return f'{ind}<Fill name="Fill"><SolidColor colorValue="{c}" name="Color"/></Fill>'

def stroke(c, t, ind, cap='round'):
    return (f'{ind}<Stroke thickness="{f(t)}" cap="{cap}" join="round" name="Stroke">'
            f'<SolidColor colorValue="{c}" name="Color"/></Stroke>')

def svg_shape(name, d, dx, dy, ind, paint, sid=None, x=0, y=0, closed=True):
    """A Shape whose path is svg path data offset by (-dx,-dy)."""
    subs = parse_path(d)
    tf = lambda X, Y: (X - dx, Y - dy)
    idattr = f' id="{sid}"' if sid else ''
    body = '\n'.join(points_path(s, tf, closed, ind + '    ') for s in subs)
    return (f'{ind}<Shape x="{f(x)}" y="{f(y)}" name="{name}"{idattr}>\n{body}\n'
            f'{paint(ind + "    ")}\n{ind}</Shape>')

# ---------------------------------------------------------------- scene parts
out = []
def emit(s): out.append(s)

# The cursor: a node the pointer drags around (ListenerAlignTarget). Everything
# that "looks" at the cursor is constrained toward it.
CURSOR = nid()
HIT = nid()  # full-artboard hit area for the move listener

# Avatar specs: center measured from the reference OG image.
R = 27.0                 # on-screen radius
S = R / 11.5             # svg avatar units -> pixels
SW = 0.5                 # glyph stroke in svg units (~1.2px on screen)
AVATARS = [
    dict(key='green',  color='FFC5FE79', cx=274.5, cy=256.5, kind='face'),
    dict(key='blue',   color='FF3E85F1', cx=441.5, cy=341.5, kind='square'),
    dict(key='orange', color='FFFF6E23', cx=717.0, cy=213.5, kind='triangle'),
    dict(key='pink',   color='FFFE86F7', cx=946.5, cy=279.0, kind='rings'),
]
for a in AVATARS:
    for k in ('root', 'jump', 'react', 'body', 'look', 'look_anchor', 'spin',
              'eyes_l', 'eyes_r', 'pupil_l', 'pupil_r', 'smile', 'white_l', 'white_r',
              'hit'):
        a[k] = nid()

# Face pieces (from small-avatars.svg, green avatar centered at 54,12).
EYE_WHITE = 'M53.7829 12.9502C53.7829 11.7123 53.3694 9.29199 52.6335 8.41665C51.8976 7.54132 50.8995 7.04956 49.8587 7.04956C48.818 7.04956 47.8198 7.54132 47.0839 8.41665C46.348 9.29199 45.9346 11.7123 45.9346 12.9502L49.8587 12.9502H53.7829Z'
PUPIL = 'M52.4993 12.9505C52.4993 12.1167 52.2208 10.4864 51.7251 9.8968C51.2294 9.30719 50.5571 8.97595 49.8561 8.97595C49.1551 8.97595 48.4828 9.30719 47.9871 9.8968C47.4914 10.4864 47.2129 12.1167 47.2129 12.9505L49.8561 12.9505H52.4993Z'
SMILE = 'M52.2696 15.3563C52.2451 15.3311 52.216 15.3092 52.1826 15.2979C52.1493 15.2867 52.1147 15.2868 52.0842 15.2994C52.0536 15.3119 52.0289 15.336 52.0131 15.3675C51.9972 15.3989 51.9919 15.4349 51.9921 15.4701C51.9957 15.5601 52.009 15.6515 52.0307 15.7417C52.2251 16.555 53.0521 17.2157 53.9871 17.1978C54.9436 17.193 55.6838 16.4721 55.9193 15.7464C55.9475 15.6655 55.9714 15.5838 55.9929 15.4986C56.0007 15.4643 56.0032 15.428 55.9945 15.3939C55.9858 15.3598 55.9668 15.3309 55.9397 15.3121C55.9126 15.2933 55.8788 15.2857 55.8439 15.2895C55.8089 15.2933 55.7758 15.3085 55.7463 15.3278C55.6774 15.3732 55.611 15.4141 55.5452 15.4532C54.9407 15.8204 54.427 15.9723 53.9695 15.9754C53.5122 15.9783 52.9676 15.8717 52.4387 15.4979C52.3808 15.455 52.3241 15.4081 52.2696 15.3563Z'

def look_constraints(a, dist, ind):
    # Snap toward the cursor, then clamp to a small radius around the rest spot.
    return (f'{ind}<TranslationConstraint targetId="{CURSOR}" name="Follow cursor"/>\n'
            f'{ind}<DistanceConstraint targetId="{a["look_anchor"]}" distance="{f(dist)}" name="Clamp"/>')

def eye(a, side, ex, ey, i):
    """One eye: blink node at the eye's base (scaleY squashes onto the base),
    containing a clipped pupil that follows the cursor."""
    eid = a['eyes_l' if side == 'l' else 'eyes_r']
    pid = a['pupil_l' if side == 'l' else 'pupil_r']
    wid = a['white_l' if side == 'l' else 'white_r']
    anchor = nid()
    return f'''{i}<Node x="{f(ex)}" y="{f(ey)}" name="Eye {side.upper()}" id="{eid}">
{i}    <Node name="Pupil" id="{pid}">
{i}        <ClippingShape sourceId="{wid}" name="Clip to eye"/>
{i}        <TranslationConstraint targetId="{CURSOR}" name="Follow cursor"/>
{i}        <DistanceConstraint targetId="{anchor}" distance="3" name="Clamp"/>
{i}        <Shape x="-0.43" y="-2.5" name="Glint">
{i}            <Ellipse width="0.86" height="1.02" name="Path"/>
{fill('FFFFFFFF', i + '            ')}
{i}        </Shape>
{svg_shape('Pupil Dome', PUPIL, 49.8561, 12.9505, i + '        ', lambda j: fill(INK, j))}
{i}    </Node>
{i}    <Node name="Pupil Anchor" id="{anchor}"/>
{svg_shape('White', EYE_WHITE, 49.8587, 12.9502, i + '    ', lambda j: fill('FFFFFFFF', j), sid=wid)}
{i}</Node>'''

def glyph(a, i):
    k = a['kind']
    if k == 'face':
        return f'''{eye(a, 'l', -4.14, 0.95, i)}
{eye(a, 'r', 4.14, 0.95, i)}
{i}<Node x="0" y="3.29" name="Smile" id="{a['smile']}">
{svg_shape('Mouth', SMILE, 53.99, 15.29, i + '    ', lambda j: fill(INK, j))}
{i}</Node>'''
    if k == 'square':
        return f'''{i}<Shape name="Square">
{i}    <Rectangle width="11" height="11" name="Path"/>
{stroke(INK, SW, i + '    ', 'butt')}
{i}</Shape>
{i}<Shape name="Cross">
{i}    <PointsPath isClosed="false" name="Path">
{i}        <StraightVertex x="-5.5" y="-5.5"/><StraightVertex x="5.5" y="5.5"/>
{i}    </PointsPath>
{i}    <PointsPath isClosed="false" name="Path">
{i}        <StraightVertex x="5.5" y="-5.5"/><StraightVertex x="-5.5" y="5.5"/>
{i}    </PointsPath>
{stroke(INK, SW, i + '    ', 'butt')}
{i}</Shape>'''
    if k == 'triangle':
        return f'''{i}<Shape name="Triangle">
{i}    <PointsPath isClosed="true" name="Path">
{i}        <StraightVertex x="-4.69" y="-2.94"/><StraightVertex x="4.69" y="-2.94"/><StraightVertex x="0" y="6.44"/>
{i}    </PointsPath>
{stroke(INK, SW, i + '    ')}
{i}</Shape>
{i}<Shape name="Ring">
{i}    <Ellipse width="13" height="13" name="Path"/>
{stroke(INK, SW, i + '    ')}
{i}</Shape>'''
    if k == 'rings':
        return f'''{i}<Shape x="-2.256" name="Ring L" id="{nid()}">
{i}    <Ellipse width="9" height="11" name="Path"/>
{stroke(INK, SW, i + '    ')}
{i}</Shape>
{i}<Shape x="2.256" name="Ring R" id="{nid()}">
{i}    <Ellipse width="9" height="11" name="Path"/>
{stroke(INK, SW, i + '    ')}
{i}</Shape>'''

def avatar(a, i):
    # Root sits at the avatar's bottom so jump squash/stretch lands on its feet.
    look_dist = 1.4 if a['kind'] == 'face' else 2.2  # svg units, world-scaled below
    return f'''{i}<Node x="{f(a['cx'])}" y="{f(a['cy'] + R)}" name="Avatar {a['key'].title()}" id="{a['root']}">
{i}    <Node name="Jump" id="{a['jump']}">
{i}        <Node name="React" id="{a['react']}">
{i}            <Node y="{f(-R)}" scaleX="{f(S)}" scaleY="{f(S)}" name="Body" id="{a['body']}">
{i}                <Node name="Look" id="{a['look']}">
{look_constraints(a, look_dist * S, i + '                    ')}
{i}                    <Node name="Spin" id="{a['spin']}">
{glyph(a, i + '                        ')}
{i}                    </Node>
{i}                </Node>
{i}                <Node name="Look Anchor" id="{a['look_anchor']}"/>
{i}                <Shape name="Disc" id="{a['hit']}">
{i}                    <Ellipse width="23" height="23" name="Path"/>
{fill(a['color'], i + '                    ')}
{stroke(INK, 0.45, i + '                    ')}
{i}                </Shape>
{i}            </Node>
{i}        </Node>
{i}    </Node>
{i}</Node>'''

# ---------------------------------------------------------------- background
def grid(i):
    lines = []
    lines.append(f'{i}<Shape name="Grid Lines">')
    for x in range(64, W, 64):
        lines.append(f'{i}    <Rectangle x="{x}" y="{f(H/2)}" width="2" height="{H}" name="V"/>')
    for y in range(64, 576, 64):
        lines.append(f'{i}    <Rectangle x="{f(W/2)}" y="{y}" width="{W}" height="2" name="H"/>')
    lines.append(fill('FFEDEDEB', i + '    '))
    lines.append(f'{i}</Shape>')
    return '\n'.join(lines)

def dots(i):
    lines = [f'{i}<Shape name="Grid Dots">']
    for j, y in enumerate(range(64, 576, 64)):
        for x in range(64 + (128 if j % 2 else 0), W, 256):
            lines.append(f'{i}    <Ellipse x="{x}" y="{y}" width="6" height="6" name="Dot"/>')
    lines.append(fill('FF78716B', i + '    '))
    lines.append(f'{i}</Shape>')
    return '\n'.join(lines)

def bar(i):
    cols = ['FFC5FE79', 'FFFE86F7', 'FFFF6E23', 'FF3E85F1', 'FFC5FE79']
    seg = W / 5
    s = []
    for k, c in enumerate(cols):
        s.append(f'''{i}<Shape x="{f(seg*k + seg/2)}" y="{f((576 + H)/2)}" name="Bar {k+1}">
{i}    <Rectangle width="{f(seg)}" height="{H-576}" name="Path"/>
{fill(c, i + '    ')}
{i}</Shape>''')
    return '\n'.join(s)

def lettering(i):
    d = re.search(r' d="([^"]+)"', open(UNION_SVG).read()).group(1)
    subs = parse_path(d)
    xs = [p[0] for s in subs for seg in s for p in seg[1:]]
    ys = [p[1] for s in subs for seg in s for p in seg[1:]]
    x0, y0, y1 = min(xs), min(ys), max(ys)
    sc = (467.5 - 91) / (y1 - y0)          # measured from the reference
    tf = lambda X, Y: ((X - x0) * sc, (Y - y0) * sc)
    body = '\n'.join(points_path(s, tf, True, i + '    ') for s in subs)
    return (f'{i}<Shape x="153" y="91" name="Lettering">\n{body}\n'
            f'{fill(INK, i + "    ")}\n{i}</Shape>')

# ---------------------------------------------------------------- animation
FPS = 60
def kf(prop, keys, ease='cubic', typ='KeyFrameDouble'):
    """keys: list of (frame, value[, ease])"""
    s = [f'            <KeyedProperty property="{prop}">']
    for k in keys:
        fr, v = k[0], k[1]
        e = k[2] if len(k) > 2 else ease
        if e == 'cubic':
            s.append(f'                <{typ} frame="{fr}" value="{f(v)}" interpolationType="cubic">'
                     f'<CubicEaseInterpolator x1="0.42" y1="0" x2="0.58" y2="1"/></{typ}>')
        elif e == 'out':
            s.append(f'                <{typ} frame="{fr}" value="{f(v)}" interpolationType="cubic">'
                     f'<CubicEaseInterpolator x1="0.2" y1="0.7" x2="0.4" y2="1"/></{typ}>')
        elif e == 'in':
            s.append(f'                <{typ} frame="{fr}" value="{f(v)}" interpolationType="cubic">'
                     f'<CubicEaseInterpolator x1="0.6" y1="0" x2="0.8" y2="0.3"/></{typ}>')
        elif e == 'elastic':
            s.append(f'                <{typ} frame="{fr}" value="{f(v)}" interpolationType="elastic">'
                     f'<ElasticInterpolator easingValue="1" amplitude="1" period="0.35"/></{typ}>')
        else:
            s.append(f'                <{typ} frame="{fr}" value="{f(v)}" interpolationType="{e}"/>')
    s.append('            </KeyedProperty>')
    return '\n'.join(s)

def keyed(obj, *props):
    return f'        <KeyedObject objectId="{obj}">\n' + '\n'.join(props) + '\n        </KeyedObject>'

def anim(name, aid, dur, loop, keyed_objs):
    return (f'    <LinearAnimation loopValue="{loop}" duration="{dur}" fps="{FPS}" name="{name}" id="{aid}">\n'
            + '\n'.join(keyed_objs) + '\n    </LinearAnimation>')

IDLE_DUR = 300   # 5s loop: each avatar hops in turn, a-r-l-o, then a group hop
def jump_keys(t, h=34):
    """A squash-and-stretch hop starting at frame t (lasts 42 frames)."""
    y = [(0, 0, 'hold'), (t, 0, 'cubic'), (t + 8, 0, 'out'), (t + 22, -h, 'in'),
         (t + 34, 0, 'cubic'), (t + 42, 0, 'linear'), (IDLE_DUR, 0)]
    sx = [(0, 1, 'hold'), (t, 1, 'cubic'), (t + 8, 1.14, 'out'), (t + 16, 0.92, 'cubic'),
          (t + 30, 1.0, 'cubic'), (t + 34, 1.16, 'out'), (t + 42, 1, 'linear'), (IDLE_DUR, 1)]
    sy = [(0, 1, 'hold'), (t, 1, 'cubic'), (t + 8, 0.84, 'out'), (t + 16, 1.1, 'cubic'),
          (t + 30, 1.0, 'cubic'), (t + 34, 0.86, 'out'), (t + 42, 1, 'linear'), (IDLE_DUR, 1)]
    return y, sx, sy

def merge(*seqs):
    """Merge several key lists that each start with (0,..,'hold') and end at
    IDLE_DUR, keeping every key inside its own active window."""
    keys = {}
    for seq in seqs:
        for k in seq[1:-1]:
            keys[k[0]] = k
    first = seqs[0][0]
    last = seqs[0][-1]
    out = [first] + [keys[k] for k in sorted(keys)] + [last]
    return out

idle_objs = []
STARTS = [20, 70, 120, 170]   # a, r, l, o in sequence
GROUP = 232                   # then everyone together
for a, t in zip(AVATARS, STARTS):
    y1, sx1, sy1 = jump_keys(t)
    y2, sx2, sy2 = jump_keys(GROUP + (AVATARS.index(a) * 3), h=46)
    idle_objs.append(keyed(a['jump'], kf('y', merge(y1, y2)),
                           kf('scaleX', merge(sx1, sx2)), kf('scaleY', merge(sy1, sy2))))
# the green one grins on its hops
g = AVATARS[0]
smile = [(0, 1, 'hold')]
for t in (STARTS[0], GROUP):
    smile += [(t + 4, 1, 'out'), (t + 14, 1.7, 'cubic'), (t + 40, 1.7, 'cubic'), (t + 56, 1, 'hold')]
smile.append((IDLE_DUR, 1))
idle_objs.append(keyed(g['smile'], kf('scaleX', [(k[0], 1 + (k[1]-1) * 0.55) + k[2:] for k in smile]),
                       kf('scaleY', smile)))

# blink: one loop, the face blinks twice; glyph avatars squash shut like a blink
BLINK_DUR = 260
def blink(t, dur=10):
    return [(t, 1, 'in'), (t + dur // 2, 0.08, 'out'), (t + dur, 1, 'hold')]
blink_objs = []
face_b = [(0, 1, 'hold')] + blink(40) + blink(58) + blink(190) + [(BLINK_DUR, 1)]
blink_objs.append(keyed(g['eyes_l'], kf('scaleY', face_b)))
blink_objs.append(keyed(g['eyes_r'], kf('scaleY', face_b)))
for a, t in zip(AVATARS[1:], (100, 150, 222)):
    blink_objs.append(keyed(a['spin'], kf('scaleY', [(0, 1, 'hold')] + blink(t, 12) + [(BLINK_DUR, 1)])))

# hover reaction, per avatar
HOVER_DUR = 40
def hover_anim(a):
    objs = [keyed(a['react'],
                  kf('scaleX', [(0, 1, 'elastic'), (HOVER_DUR, 1.16)]),
                  kf('scaleY', [(0, 1, 'elastic'), (HOVER_DUR, 1.16)]),
                  kf('rotation', [(0, 0, 'cubic'), (8, -0.16, 'cubic'), (18, 0.12, 'cubic'),
                                  (28, -0.05, 'cubic'), (HOVER_DUR, 0)]))]
    k = a['kind']
    if k == 'face':
        objs.append(keyed(a['smile'], kf('scaleX', [(0, 1, 'elastic'), (HOVER_DUR, 1.5)]),
                          kf('scaleY', [(0, 1, 'elastic'), (HOVER_DUR, 2.2)])))
    elif k == 'square':
        objs.append(keyed(a['spin'], kf('rotation', [(0, 0, 'elastic'), (HOVER_DUR, math.pi / 2)])))
    elif k == 'triangle':
        objs.append(keyed(a['spin'], kf('rotation', [(0, 0, 'elastic'), (HOVER_DUR, math.pi)])))
    elif k == 'rings':
        objs.append(keyed(a['spin'], kf('rotation', [(0, 0, 'elastic'), (HOVER_DUR, math.pi / 2)])))
    return objs

def rest_anim(a):
    objs = [keyed(a['react'], kf('scaleX', [(0, 1)]), kf('scaleY', [(0, 1)]), kf('rotation', [(0, 0)]))]
    if a['kind'] == 'face':
        objs.append(keyed(a['smile'], kf('scaleX', [(0, 1)]), kf('scaleY', [(0, 1)])))
    else:
        objs.append(keyed(a['spin'], kf('rotation', [(0, 0)])))
    return objs

# ---------------------------------------------------------------- view model
VM = nid(); VMI = nid()
for a in AVATARS:
    a['vp'] = nid()

def bool_write(a, v):
    return (f'''            <ListenerViewModelChange>
                <BindablePropertyBoolean propertyValue="{v}">
                    <DataBindContext sourcePathIds="{VM}-{a['vp']}" propertyKey="634" direction="true"/>
                </BindablePropertyBoolean>
            </ListenerViewModelChange>''')

def cond(a, v):
    return f'''                    <TransitionViewModelCondition>
                        <TransitionPropertyViewModelComparator>
                            <BindablePropertyBoolean>
                                <DataBindContext sourcePathIds="{VM}-{a['vp']}" propertyKey="634"/>
                            </BindablePropertyBoolean>
                        </TransitionPropertyViewModelComparator>
                        <TransitionValueBooleanComparator value="{v}"/>
                    </TransitionViewModelCondition>'''

IDLE, BLINK = nid(), nid()
SM = nid()
for a in AVATARS:
    a['a_rest'], a['a_hover'], a['s_rest'], a['s_hover'] = nid(), nid(), nid(), nid()

def layer(name, entry_to, states):
    return f'''        <StateMachineLayer name="{name}">
            <AnyState x="0" y="-150"/>
            <ExitState x="400" y="-150"/>
            <EntryState x="0" y="0">
                <StateTransition stateToId="{entry_to}"/>
            </EntryState>
{states}
        </StateMachineLayer>'''

sm = [f'    <StateMachine name="State Machine 1" id="{SM}">']
sm.append(layer('Idle Hops', 'IDLE_S', f'            <AnimationState x="200" y="0" animationId="{IDLE}" id="IDLE_S"/>'))
sm.append(layer('Blink', 'BLINK_S', f'            <AnimationState x="200" y="0" animationId="{BLINK}" id="BLINK_S"/>'))
for a in AVATARS:
    states = f'''            <AnimationState x="200" y="0" animationId="{a['a_rest']}" id="{a['s_rest']}">
                <StateTransition stateToId="{a['s_hover']}" duration="0">
{cond(a, 'true')}
                </StateTransition>
            </AnimationState>
            <AnimationState x="400" y="0" animationId="{a['a_hover']}" id="{a['s_hover']}">
                <StateTransition stateToId="{a['s_rest']}" duration="350">
                    <CubicEaseInterpolator x1="0.42" y1="0" x2="0.58" y2="1"/>
{cond(a, 'false')}
                </StateTransition>
            </AnimationState>'''
    sm.append(layer(f'Hover {a["key"].title()}', a['s_rest'], states))
# pointer: the cursor node follows the pointer anywhere on the artboard
sm.append(f'''        <StateMachineListenerSingle targetId="{HIT}" listenerTypeValue="move" name="Track Cursor">
            <ListenerAlignTarget targetId="{CURSOR}"/>
        </StateMachineListenerSingle>''')
for a in AVATARS:
    sm.append(f'''        <StateMachineListenerSingle targetId="{a['hit']}" listenerTypeValue="enter" name="{a['key'].title()} In">
{bool_write(a, 'true')}
        </StateMachineListenerSingle>
        <StateMachineListenerSingle targetId="{a['hit']}" listenerTypeValue="exit" name="{a['key'].title()} Out">
{bool_write(a, 'false')}
        </StateMachineListenerSingle>''')
sm.append('    </StateMachine>')
sm_text = '\n'.join(sm).replace('IDLE_S', '0:90').replace('BLINK_S', '0:91')

# ---------------------------------------------------------------- assemble
I = '        '
emit('<Rive version="1" kind="fragment">')
emit(f'    <Artboard defaultStateMachineId="{SM}" viewModelId="{VM}" styleId="0:5" width="{W}" height="{H}" name="Arlo OG" id="0:2">')
emit('        <LayoutComponentStyle name="Artboard Style" id="0:5"/>')
emit(fill('FFFAFAF9', I))
emit(f'{I}<Node x="{W/2}" y="{f(H/2)}" name="Cursor" id="{CURSOR}"/>')
for a in AVATARS:
    emit(avatar(a, I))
emit(lettering(I))
emit(bar(I))
emit(dots(I))
emit(grid(I))
emit(f'''{I}<Shape x="{W/2}" y="{f(H/2)}" name="Pointer Area" id="{HIT}">
{I}    <Rectangle width="{W}" height="{H}" name="Path"/>
{fill('00FFFFFF', I + '    ')}
{I}</Shape>''')
emit(sm_text)
emit(anim('Idle Hops', IDLE, IDLE_DUR, 'loop', idle_objs))
emit(anim('Blink', BLINK, BLINK_DUR, 'loop', blink_objs))
for a in AVATARS:
    emit(anim(f'{a["key"].title()} Rest', a['a_rest'], 1, 'oneShot', rest_anim(a)))
    emit(anim(f'{a["key"].title()} Hover', a['a_hover'], HOVER_DUR, 'oneShot', hover_anim(a)))
emit('    </Artboard>')
vm_props = '\n'.join(f'        <ViewModelPropertyBoolean name="hover{a["key"].title()}" id="{a["vp"]}"/>' for a in AVATARS)
vm_vals = '\n'.join(f'            <ViewModelInstanceBoolean propertyValue="false" viewModelPropertyId="{a["vp"]}"/>' for a in AVATARS)
emit(f'''    <ViewModel defaultInstanceId="{VMI}" name="Arlo OG" id="{VM}">
{vm_props}
        <ViewModelInstance exports="true" name="Default" id="{VMI}">
{vm_vals}
        </ViewModelInstance>
    </ViewModel>''')
emit('</Rive>')

open(os.path.join(ROOT, 'scene.rml'), 'w').write('\n'.join(out) + '\n')
print('wrote scene.rml')
