"""Rewrites a weapon model exported by OAT's Unlinker (binary glTF) for the other hand of a dual-wield pair.

fit_glb() moves and scales the mesh around the model's origin (the root bone stays where the hand holds it), moves
the other bones with the mesh, and can give every bone a suffix: BO1's left-hand weapon models name their bones
`j_gun1`, `tag_flash1`, `tag_weapon1` (t5_weapon_cz75_dw_lh_viewmodel, t5_weapon_hs10_dw_lh_world), so that the
dual-wield animations move each gun by its own bones.
"""
import json
import math
import struct

GLB_MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
FLOAT = 5126


def read_glb(data):
    if len(data) < 20 or data[:4] != GLB_MAGIC or struct.unpack_from("<I", data, 4)[0] != 2:
        raise ValueError("not a glTF 2.0 binary")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    if jtype != CHUNK_JSON:
        raise ValueError("first chunk is not JSON")
    doc = json.loads(data[20:20 + jlen])
    off = 20 + jlen
    bin_ = b""
    if off + 8 <= len(data):
        blen, btype = struct.unpack_from("<II", data, off)
        if btype != CHUNK_BIN:
            raise ValueError("second chunk is not BIN")
        bin_ = data[off + 8:off + 8 + blen]
    return doc, bytearray(bin_)


def write_glb(doc, bin_):
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_ = bytes(bin_) + b"\0" * (-len(bin_) % 4)
    total = 12 + 8 + len(js) + (8 + len(bin_) if bin_ else 0)
    out = GLB_MAGIC + struct.pack("<II", 2, total) + struct.pack("<II", len(js), CHUNK_JSON) + js
    if bin_:
        out += struct.pack("<II", len(bin_), CHUNK_BIN) + bin_
    return out


def quat_matrix(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_vec(m, v):
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def world_transforms(doc):
    """World rotation and translation of every node (glTF: a parent's transform applies to its children)."""
    parent = {}
    for i, n in enumerate(doc["nodes"]):
        for c in n.get("children", []):
            parent[c] = i
    cache = {}

    def world(i):
        if i not in cache:
            n = doc["nodes"][i]
            if "matrix" in n or any(abs(s - 1) > 1e-6 for s in n.get("scale", [1, 1, 1])):
                raise ValueError("node %r has a matrix or a scale" % n.get("name"))
            r = quat_matrix(n.get("rotation", [0, 0, 0, 1]))
            t = list(n.get("translation", [0, 0, 0]))
            if i in parent:
                pr, pt = world(parent[i])
                r, t = mat_mul(pr, r), [a + b for a, b in zip(mat_vec(pr, t), pt)]
            cache[i] = (r, t)
        return cache[i]

    return {i: world(i) for i in range(len(doc["nodes"]))}, parent


def fit_glb(data, scale=1.0, offset=(0.0, 0.0, 0.0), suffix=""):
    """The model in `data` (GLB bytes) with its vertices and non-root bones at scale * p + offset (model space) and
    `suffix` appended to every bone name."""
    doc, bin_ = read_glb(data)
    skins = doc.get("skins", [])
    if len(skins) != 1:
        raise ValueError("expected one skin, found %d" % len(skins))
    skin = skins[0]
    joints = skin["joints"]
    root = skin.get("skeleton", joints[0])
    worlds, parent = world_transforms(doc)

    done = set()
    for mesh in doc.get("meshes", []):
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            if acc["componentType"] != FLOAT or acc["type"] != "VEC3":
                raise ValueError("POSITION is not float VEC3")
            view = doc["bufferViews"][acc["bufferView"]]
            stride = view.get("byteStride", 12)
            base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
            lo, hi = [math.inf] * 3, [-math.inf] * 3
            for v in range(acc["count"]):
                o = base + v * stride
                p = struct.unpack_from("<3f", bin_, o)
                if o not in done:
                    p = [scale * c + d for c, d in zip(p, offset)]
                    struct.pack_into("<3f", bin_, o, *p)
                    done.add(o)
                lo = [min(a, b) for a, b in zip(lo, p)]
                hi = [max(a, b) for a, b in zip(hi, p)]
            acc["min"], acc["max"] = lo, hi

    new_t = {}
    for j in joints:
        r, t = worlds[j]
        new_t[j] = t if j == root else [scale * c + d for c, d in zip(t, offset)]
    for j in joints:
        if j == root:
            continue
        p = parent.get(j)
        if p is None:
            raise ValueError("bone %r has no parent" % doc["nodes"][j].get("name"))
        pr, pt = worlds[p]
        pt = new_t.get(p, pt)
        doc["nodes"][j]["translation"] = mat_vec(transpose(pr), [a - b for a, b in zip(new_t[j], pt)])

    if "inverseBindMatrices" in skin:
        acc = doc["accessors"][skin["inverseBindMatrices"]]
        view = doc["bufferViews"][acc["bufferView"]]
        base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        for k, j in enumerate(joints):
            r, _ = worlds[j]
            rt = transpose(r)
            t = [-c for c in mat_vec(rt, new_t[j])]
            # column-major 4x4: the inverse of [r | t'] is [r^T | -r^T t']
            m = [rt[0][0], rt[1][0], rt[2][0], 0.0, rt[0][1], rt[1][1], rt[2][1], 0.0,
                 rt[0][2], rt[1][2], rt[2][2], 0.0, t[0], t[1], t[2], 1.0]
            struct.pack_into("<16f", bin_, base + 64 * k, *m)

    if suffix:
        names = [doc["nodes"][j]["name"] + suffix for j in joints]
        others = {n.get("name") for i, n in enumerate(doc["nodes"]) if i not in joints}
        if len(set(names)) != len(names) or others & set(names):
            raise ValueError("bone names clash once suffixed with %r" % suffix)
        for j, name in zip(joints, names):
            doc["nodes"][j]["name"] = name
    return write_glb(doc, bin_)


def bone_names(data):
    doc, _ = read_glb(data)
    return [doc["nodes"][j]["name"] for j in doc["skins"][0]["joints"]]
