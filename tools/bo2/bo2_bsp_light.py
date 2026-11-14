"""BO2's baked world lighting as BO1 lightmaps, for bo2_bsp.py.

Each BO2 lightmap becomes one BO1 lightmap with the same coordinates (a world vertex keeps BO2's lightmap uv), its
pixels baked again: every texel a triangle covers takes BO2's light at that point (bo2_worldlight.WorldLight: the
lightmap's slices, the sun or the triangle's lamp, with the triangle's normal), divided by the light of the sunlit
ground (WorldLight.calibrate), so that sunlit ground keeps its colour map. Texels no triangle covers take their
covered neighbours' light (a few passes), so bilinear sampling at a triangle's edge does not fetch black.

A BO1 lightmap (R_LoadLightmaps) is two 512 x 512 halves of float RGBA, whose luminances the world shaders combine,
and a 1024 x 1024 L8 sun visibility for the sun the shaders add. The baked light already holds BO2's sun, so it goes
whole into the first half, the second half and the sun visibility stay 0.

Models take their light from a light grid instead (light_grid): every point takes BO2's light of the floor under it,
without the sun, and the sun primary light where BO2's sun reaches that floor; BO1's sun then has BO2's sun colour on
the same scale (bake_sun_colour).
"""
import numpy as np

import d3dbsp
from bo2_worldlight import OMNI, SPOT, outward_normal

SIZE = 512
DILATE_PASSES = 8


def bake(world_light, triangles):
    """triangles: [(lightmap index, primary light, [(position, (lu, lv))] * 3)]. Returns {BO2 lightmap index:
    (SIZE, SIZE, 3) float32 light}."""
    light = {i: np.zeros((SIZE, SIZE, 3), np.float32) for i in world_light.lightmaps}
    weight = {i: np.zeros((SIZE, SIZE), np.float32) for i in world_light.lightmaps}
    samples = []
    for index, primary, corners in triangles:
        if index not in light:
            continue
        normal = outward_normal(*(c[0] for c in corners))
        if normal is None:
            continue
        (p0, t0), (p1, t1), (p2, t2) = corners
        x = [t[0] * SIZE - 0.5 for t in (t0, t1, t2)]
        y = [t[1] * SIZE - 0.5 for t in (t0, t1, t2)]
        area = (x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0])
        pixels = []
        if abs(area) > 1e-9:
            for py in range(max(int(np.floor(min(y))), 0), min(int(np.ceil(max(y))), SIZE - 1) + 1):
                for px in range(max(int(np.floor(min(x))), 0), min(int(np.ceil(max(x))), SIZE - 1) + 1):
                    w1 = ((px - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (py - y[0])) / area
                    w2 = ((x[1] - x[0]) * (py - y[0]) - (px - x[0]) * (y[1] - y[0])) / area
                    w0 = 1.0 - w1 - w2
                    if min(w0, w1, w2) >= -0.01:
                        pixels.append((px, py, w0, w1, w2))
        if not pixels:
            # smaller than a texel: its centre's texel
            pixels.append((min(max(int(round(sum(x) / 3)), 0), SIZE - 1),
                           min(max(int(round(sum(y) / 3)), 0), SIZE - 1), 1 / 3, 1 / 3, 1 / 3))
        for px, py, w0, w1, w2 in pixels:
            pos = [w0 * p0[k] + w1 * p1[k] + w2 * p2[k] for k in range(3)]
            l = world_light.light(index, primary, (px + 0.5) / SIZE, (py + 0.5) / SIZE, normal, pos)
            if l is None:
                continue
            light[index][py, px] += l
            weight[index][py, px] += 1.0
            if primary == world_light.sun_index:
                samples.append((l, world_light.lightmaps[index].sample((px + 0.5) / SIZE, (py + 0.5) / SIZE, 2)[3]))
    world_light.calibrate(samples)
    ref = np.array(world_light.reference, np.float32)
    out = {}
    for index in light:
        w = weight[index]
        image = np.where(w[..., None] > 0, light[index] / np.maximum(w, 1)[..., None], 0) / ref
        covered = w > 0
        for _ in range(DILATE_PASSES):
            if covered.all():
                break
            total = np.zeros_like(image)
            count = np.zeros(covered.shape, np.float32)
            padded = np.pad(image * covered[..., None], ((1, 1), (1, 1), (0, 0)))
            padded_cov = np.pad(covered.astype(np.float32), 1)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                total += padded[1 + dy:1 + dy + SIZE, 1 + dx:1 + dx + SIZE]
                count += padded_cov[1 + dy:1 + dy + SIZE, 1 + dx:1 + dx + SIZE]
            fill = ~covered & (count > 0)
            image[fill] = total[fill] / count[fill][:, None]
            covered = covered | fill
        out[index] = image.astype(np.float32)
    return out


def lightmap_bytes(image):
    """The 9 MB a BSP stores per lightmap: the first half (float RGBA, the light, alpha 0), the second half (zero),
    then the sun visibility (zero)."""
    rgba = np.zeros((SIZE, SIZE, 4), np.float32)
    rgba[..., :3] = np.clip(image, 0.0, 31.875)
    return rgba.tobytes() + bytes(SIZE * SIZE * 16) + bytes(1024 * 1024)


def white_lightmap_bytes():
    """A lightmap of light 1 for lit surfaces BO2 drew without one."""
    rgba = np.zeros((SIZE, SIZE, 4), np.float32)
    rgba[..., :3] = 1.0
    return rgba.tobytes() + bytes(SIZE * SIZE * 16) + bytes(1024 * 1024)


GRID_ORIGIN = -131072.0
GRID_XY, GRID_Z = 32.0, 64.0       # the engine's light grid spacing (rb_light.cpp)
GRID_PAD = 1024.0                  # beyond the play area (the rocks and houses at its edge)
GRID_ABOVE = 192.0                 # grid points above the highest floor
FLOOR_REACH = 24.0                 # a floor counts for a point this far above it (a point inside a step)
FLOOR_NORMAL_Z = 0.5               # a triangle this flat is a floor
COLOUR_STEP = 1.0 / 64.0           # light grid colours are quantised to this
SMOOTH_RADIUS = 2                  # columns on each side a point's light is averaged over (64 units)
GRID_BLOCK = 8                     # columns along y that share a height range in the grid's rows
GRID_SLAB = 32                     # rows smoothed at a time (memory)
AMBIENT_MIN = 0.12                 # the darkest ambient light, as the lightmaps' LIGHT_FLOOR: BO2 lifts its shade
# The share of its colour a grid point keeps around its luminance. The floors' light without the sun is mostly light
# bounced off Nuketown's orange ground, and dividing it by the reference (the sunlit ground: BO2's blue sun) turned
# it orange, 1.8 times more red than blue on average: doors and hedges out of the sun drew orange and brown where the
# MapKit mesh, lit by BO2's own light of each prop, draws them neutral (measured on screenshots of the same door).
AMBIENT_SATURATION = 0.0
LUMA = (0.2126, 0.7152, 0.0722)


def desaturate(colours):
    """colours (..., 3) with AMBIENT_SATURATION of their colour around their luminance."""
    colours = np.asarray(colours, np.float32)
    luma = (colours * np.asarray(LUMA, np.float32)).sum(axis=-1, keepdims=True)
    return luma + AMBIENT_SATURATION * (colours - luma)


def weighted_median(values, weights):
    """np.median(axis=0) of values (n, 3) with each row counted weights[i] times."""
    out = np.empty(values.shape[1], np.float32)
    total = float(weights.sum())
    for k in range(values.shape[1]):
        order = np.argsort(values[:, k], kind="stable")
        cumulative = np.cumsum(weights[order])
        lo = order[np.searchsorted(cumulative, (total - 1) // 2, side="right")]
        hi = order[np.searchsorted(cumulative, total // 2, side="right")]
        out[k] = (values[lo, k] + values[hi, k]) / 2.0
    return out


def grid_columns(boxes):
    """The light grid columns (gx, gy) over boxes [(mins, maxs)] (the zones), GRID_PAD around each."""
    keep = set()
    for lo, hi in boxes:
        x0 = int((lo[0] - GRID_PAD - GRID_ORIGIN) // GRID_XY)
        x1 = int((hi[0] + GRID_PAD - GRID_ORIGIN) // GRID_XY) + 1
        y0 = int((lo[1] - GRID_PAD - GRID_ORIGIN) // GRID_XY)
        y1 = int((hi[1] + GRID_PAD - GRID_ORIGIN) // GRID_XY) + 1
        keep.update((gx, gy) for gx in range(x0, x1 + 1) for gy in range(y0, y1 + 1))
    return keep


def light_grid(world_light, triangles, boxes, light_index, none_index):
    """BO1's light grid over the play area (boxes: the zones' [(mins, maxs)], GRID_PAD around each) from BO2's light.
    Each point takes the light of the floor under it, BO2's lightmap there without its primary light: its first slice
    plus half its second (the second is directional light, which a model takes from every side), divided by
    world_light.reference as the lightmaps are; and the floor's primary light (the sun or a lamp, light_index maps
    BO2's index to the BSP's) where it reaches that floor (none_index elsewhere): BO1 adds that light to the model as
    it draws it. Each point then takes at least the mean of the floors around it, and AMBIENT_MIN, and the primary
    light most of them have; a point with no floor below takes that mean (the median of all points without one).
    The grid is sparse, as the compiler's: each block of GRID_BLOCK columns spans its floors' heights (from the lowest
    floor to GRID_ABOVE over the highest), a block without a floor holds no point and the engine extrapolates there.
    TranZit's dense grid (26 000 x 18 000 units, 20 million points) did not fit in memory.
    triangles: as bake's. Returns (mins, maxs, rows, colours) for D3dBsp.set_light_grid, or None."""
    ref = world_light.reference
    keep = grid_columns(boxes)
    if not keep:
        return None
    # a point on a cell's corner takes the triangles of the four cells around it
    keep_cells = keep | {(gx - 1, gy) for gx, gy in keep} | {(gx, gy - 1) for gx, gy in keep} \
        | {(gx - 1, gy - 1) for gx, gy in keep}
    cells = {}
    for index, primary, corners in triangles:
        lightmap = world_light.lightmaps.get(index)
        normal = outward_normal(*(c[0] for c in corners))
        if lightmap is None or normal is None or normal[2] < FLOOR_NORMAL_Z:
            continue
        xs = [c[0][0] for c in corners]
        ys = [c[0][1] for c in corners]
        for gx in range(int((min(xs) - GRID_ORIGIN) // GRID_XY), int((max(xs) - GRID_ORIGIN) // GRID_XY) + 1):
            for gy in range(int((min(ys) - GRID_ORIGIN) // GRID_XY), int((max(ys) - GRID_ORIGIN) // GRID_XY) + 1):
                if (gx, gy) in keep_cells:
                    cells.setdefault((gx, gy), []).append((lightmap, primary, corners))
    if not cells:
        return None

    def floors_at(x, y, candidates):
        out = []
        for lightmap, primary, ((p0, t0), (p1, t1), (p2, t2)) in candidates:
            area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
            if abs(area) < 1e-6:
                continue
            w1 = ((x - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (y - p0[1])) / area
            w2 = ((p1[0] - p0[0]) * (y - p0[1]) - (x - p0[0]) * (p1[1] - p0[1])) / area
            w0 = 1.0 - w1 - w2
            if min(w0, w1, w2) < -1e-4:
                continue
            z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
            u = w0 * t0[0] + w1 * t1[0] + w2 * t2[0]
            v = w0 * t0[1] + w1 * t1[1] + w2 * t2[1]
            out.append((z, lightmap, primary, u, v))
        out.sort(key=lambda f: f[0])
        return out

    def floor_light(lightmap, primary, u, v):
        s0, s1, s2 = (lightmap.sample(u, v, k) for k in range(3))
        a0, a1 = 1.0 / (s0[3] + 1e-6), 1.0 / (s1[3] + 1e-6)
        colour = [(s0[k] * a0 + 0.5 * s1[k] * a1) / ref[k] for k in range(3)]
        return colour, light_index[primary] if primary in light_index and s2[3] >= 0.5 else none_index

    # Pass 1: each column with a floor, from its lowest floor to GRID_ABOVE over its highest: its points' light (NaN
    # under the lowest floor's reach) and primary light (-1 there)
    columns = {}
    for gx, gy in keep:
        x, y = GRID_ORIGIN + gx * GRID_XY, GRID_ORIGIN + gy * GRID_XY
        floors = floors_at(x, y, [t for c in ((gx, gy), (gx - 1, gy), (gx, gy - 1), (gx - 1, gy - 1))
                                  for t in cells.get(c, ())])
        if not floors:
            continue
        z0 = int((floors[0][0] - GRID_ORIGIN) // GRID_Z)
        z1 = min(int((floors[-1][0] + GRID_ABOVE - GRID_ORIGIN) // GRID_Z) + 1, z0 + 254)
        light = np.full((z1 - z0 + 1, 3), np.nan, np.float32)
        prim = np.full(z1 - z0 + 1, -1, np.int32)
        cache = {}
        for gz in range(z0, z1 + 1):
            z = GRID_ORIGIN + gz * GRID_Z
            below = [f for f in floors if f[0] <= z + FLOOR_REACH]
            if not below:
                continue
            f = below[-1]
            if f[0] not in cache:
                cache[f[0]] = floor_light(f[1], f[2], f[3], f[4])
            light[gz - z0], prim[gz - z0] = cache[f[0]]
        columns[(gx, gy)] = (z0, light, prim)
    if not columns:
        return None
    # Over its highest floor a column keeps that floor's light up to the grid's top (the dense grid did so, and a point
    # high over the street then takes its neighbours' light, not the default): z_top is that top, and the default
    # light the median of every such point, each column's top light counted once per level up to z_top.
    z_low = min(c[0] for c in columns.values())
    z_top = min(max(c[0] + len(c[1]) for c in columns.values()), z_low + 255)
    values, weights = [], []
    for z0, light, _ in columns.values():
        have = ~np.isnan(light[:, 0])
        values.append(light[have])
        w = np.ones(int(have.sum()), np.float32)
        if len(w):
            w[-1] += max(z_top - (z0 + len(light)), 0)
        weights.append(w)
    values, weights = np.concatenate(values), np.concatenate(weights)
    default = weighted_median(values, weights) if len(values) else np.full(3, 0.5, np.float32)
    candidates = sorted(set(light_index.values()) | {none_index})
    sun = light_index.get(world_light.sun_index, none_index)

    # The blocks: GRID_BLOCK columns along y, each spanning its floored columns' heights
    xs_all = sorted({gx for gx, _ in keep})
    ys = {}
    for gx, gy in keep:
        ys.setdefault(gx, []).append(gy)
    blocks_of = {}
    for gx in xs_all:
        lo, hi = min(ys[gx]), max(ys[gx])
        row = []
        for y0 in range(lo, hi + 1, GRID_BLOCK):
            n = min(GRID_BLOCK, hi + 1 - y0)
            spans = [(columns[(gx, gy)][0], columns[(gx, gy)][0] + len(columns[(gx, gy)][1]))
                     for gy in range(y0, y0 + n) if (gx, gy) in columns]
            if spans:
                z0 = min(a for a, _ in spans)
                row.append([y0, n, z0, min(max(b for _, b in spans) - z0, 255)])
            else:
                row.append([y0, n, 0, 0])
        while row and not row[-1][3]:
            row.pop()
        while row and not row[0][3]:
            row.pop(0)
        if row:
            blocks_of[gx] = row

    # Pass 2, in slabs of rows: each point takes at least the mean of the floors around it (SMOOTH_RADIUS columns:
    # a model's lighting origin often lies over the floor its own shadow darkens, a bus, a truck, a rock) and the
    # primary light most of them have; points without a floor of their own take that mean too, so the edges are not
    # black.
    r = SMOOTH_RADIUS
    colours, colour_index, rows = [], {}, {}

    def colour_of(c):
        key = tuple(float(v) for v in c)
        if key not in colour_index:
            colour_index[key] = len(colours)
            colours.append(key)
        return colour_index[key]

    default_q = np.maximum(desaturate(default), AMBIENT_MIN)
    colour_of(np.round(default_q / COLOUR_STEP) * COLOUR_STEP)
    row_xs = sorted(blocks_of)
    for s in range(0, len(row_xs), GRID_SLAB):
        slab = row_xs[s:s + GRID_SLAB]
        x0, x1 = slab[0] - r, slab[-1] + r
        near = [(gx, gy) for gx in range(x0, x1 + 1) for gy in ys.get(gx, ()) if (gx, gy) in columns]
        y0 = min(min(b[0] for b in blocks_of[gx]) for gx in slab) - r
        y1 = max(max(b[0] + b[1] for b in blocks_of[gx]) for gx in slab) + r
        zs = [columns[c][0] for c in near] + [b[2] for gx in slab for b in blocks_of[gx] if b[3]]
        ze = [columns[c][0] + len(columns[c][1]) for c in near] + [b[2] + b[3] for gx in slab for b in blocks_of[gx]]
        z0, z1 = min(zs), max(ze)
        shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0)
        light = np.full(shape + (3,), np.nan, np.float32)
        prim = np.full(shape, -1, np.int32)
        for gx, gy in near:
            if y0 <= gy < y1 + 1:
                cz, cl, cp = columns[(gx, gy)]
                light[gx - x0, gy - y0, cz - z0:cz - z0 + len(cl)] = cl
                prim[gx - x0, gy - y0, cz - z0:cz - z0 + len(cl)] = cp
                # its top floor's light up to the slab's top (z_top)
                light[gx - x0, gy - y0, cz - z0 + len(cl):] = cl[-1]
                prim[gx - x0, gy - y0, cz - z0 + len(cl):] = cp[-1]
        have = ~np.isnan(light[..., 0])
        filled = np.where(have[..., None], light, 0.0)
        inner = (shape[0] - 2 * r, shape[1] - 2 * r, shape[2])
        total = np.zeros(inner + (3,), np.float32)
        count = np.zeros(inner, np.float32)
        hf = have.astype(np.float32)
        for dx in range(2 * r + 1):
            for dy in range(2 * r + 1):
                total += filled[dx:dx + inner[0], dy:dy + inner[1]]
                count += hf[dx:dx + inner[0], dy:dy + inner[1]]
        best = np.full(inner, sun, np.int32)
        best_count = np.zeros(inner, np.int32)
        present = sorted(set(np.unique(prim).tolist()) - {-1})
        for c in candidates:
            if c not in present:
                continue
            votes = np.zeros(inner, np.int32)
            hit = prim == c
            for dx in range(2 * r + 1):
                for dy in range(2 * r + 1):
                    votes += hit[dx:dx + inner[0], dy:dy + inner[1]]
            better = votes > best_count
            best = np.where(better, c, best)
            best_count = np.where(better, votes, best_count)
        core = light[r:r + inner[0], r:r + inner[1]]
        core_have = have[r:r + inner[0], r:r + inner[1]]
        mean = total / np.maximum(count, 1.0)[..., None]
        out = np.where(core_have[..., None], np.maximum(core, mean),
                       np.where(count[..., None] > 0, mean, default))
        out = desaturate(out)
        out = np.clip(np.maximum(out, AMBIENT_MIN), 0.0, 31.0)
        out = np.round(out / COLOUR_STEP) * COLOUR_STEP
        chosen = np.where(count > 0, best, sun)
        for gx in slab:
            row = []
            for by, n, bz, h in blocks_of[gx]:
                entries = []
                for gy in range(by, by + n):
                    for gz in range(bz, bz + h):
                        p = (gx - x0 - r, gy - y0 - r, gz - z0)
                        entries.append((colour_of(out[p]), int(chosen[p])))
                row.append((by, n, bz, h, entries))
            rows[gx] = row
    if len(colours) > 0xFFFF:
        raise ValueError("light grid: %d colours" % len(colours))
    all_blocks = [b for row in rows.values() for b in row if b[3]]
    mins = (min(rows), min(row[0][0] for row in rows.values()), min(b[2] for b in all_blocks))
    maxs = (max(rows), max(row[-1][0] + row[-1][1] - 1 for row in rows.values()), max(b[2] + b[3] - 1 for b in all_blocks))
    return mins, maxs, rows, colours


def bake_sun_colour(world_light):
    """BO1's sun colour on the lightmaps' scale: BO2's sun diffuse colour over world_light.reference."""
    return tuple(world_light.sun_diffuse[k] / world_light.reference[k] for k in range(3))


def add_lamps(bsp, world_light):
    """BO2's lamps and spots (<map>.d3dbsp.lights.csv) as the BSP's primary lights: a spot stays a spot, the cube-lit
    lamps (type 5) become omni lights, their colour over the reference's luminance. They light the models only (the
    lightmaps already hold their light), and over the reference channel by channel, as the lightmaps are, BO2's blue
    sunlit ground turned a warm lamp (16, 10.8, 6.4) into (1.88, 0.68, 0.32): 5.8 times more red than blue, which drew
    the doors and hedges near a house orange. Over the luminance a lamp keeps BO2's own colour. Returns {BO2 index:
    BSP index}."""
    out = {}
    for index in sorted(world_light.lights):
        lamp = world_light.lights[index]
        if lamp["type"] not in (SPOT, OMNI):
            continue
        kind = d3dbsp.LIGHT_SPOT if lamp["type"] == SPOT else d3dbsp.LIGHT_OMNI
        luma = sum(w * r for w, r in zip(LUMA, world_light.reference))
        colour = [lamp[c] / luma for c in "rgb"]
        out[index] = bsp.add_primary_light(kind, (lamp["x"], lamp["y"], lamp["z"]), (lamp["dx"], lamp["dy"], lamp["dz"]),
                                           colour, lamp["radius"], lamp["cosHalfFovOuter"], lamp["cosHalfFovInner"],
                                           lamp.get("roundness", 0.0), cull_dist=int(lamp.get("cullDist", 0)))
    return out
