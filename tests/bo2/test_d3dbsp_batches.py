"""The BSP writer's vertex batches (tools/bo2/d3dbsp.py write): consecutive surfaces share firstVertex, their indices
count from it, and every index still names the surface's own vertex.

    python3 -m unittest discover -s tests/bo2 -v
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "bo2"))
import d3dbsp  # noqa: E402
from test_d3dbsp_submodels import lumps  # noqa: E402


def surfaces(out):
    data = out[d3dbsp.LUMP_TRIANGLES]
    # materialIndex, lightmap, ..., firstVertex, vertexCount, indexCount, firstIndex (DiskTriangleSoup, 28 bytes)
    return [struct.unpack_from("<HBBBBBxhxxiIHHi", data, 28 * i) for i in range(len(data) // 28)]


def positions(out):
    data = out[d3dbsp.LUMP_DRAWVERTS]
    stride = struct.calcsize("<3f3f4B2f2f3f3f")
    return [struct.unpack_from("<3f", data, stride * i) for i in range(len(data) // stride)]


class BatchTest(unittest.TestCase):
    def build(self, quads, verts_per_quad=4):
        bsp = d3dbsp.build_room()
        mat = bsp.add_material("batch_test", 0, 0)
        for q in range(quads):
            x = 100.0 * q
            pos = [(x + 10.0 * (v % 2), 10.0 * (v // 2 % 2), float(v)) for v in range(verts_per_quad)]
            idx = []
            for v in range(1, verts_per_quad - 1):
                idx += [0, v, v + 1]
            bsp.add_mesh(material=mat, positions=pos, indices=idx)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "room.d3dbsp")
            bsp.write(path)
            out = lumps(path)
        return out

    def check_indices_name_own_vertices(self, out):
        verts = positions(out)
        indices = struct.unpack("<%dH" % (len(out[d3dbsp.LUMP_DRAWINDICES]) // 2), out[d3dbsp.LUMP_DRAWINDICES])
        for surf in surfaces(out):
            first, count, index_count, first_index = surf[8], surf[9], surf[10], surf[11]
            used = [first + indices[first_index + k] for k in range(index_count)]
            self.assertTrue(all(first <= u < first + count for u in used), surf)
            self.assertLessEqual(count, 0xFFFF)
        return verts

    def test_small_surfaces_share_a_batch(self):
        out = self.build(5)
        self.check_indices_name_own_vertices(out)
        firsts = {s[8] for s in surfaces(out)}
        self.assertEqual(firsts, {0})

    def test_batches_stay_below_16_bits(self):
        # 3 surfaces of 30 000 vertices: two batches (60 000, then 30 000 more would pass 65 535)
        out = self.build(3, verts_per_quad=30000)
        self.check_indices_name_own_vertices(out)
        firsts = sorted({s[8] for s in surfaces(out) if s[9] >= 30000})
        self.assertEqual(len(firsts), 2)


if __name__ == "__main__":
    unittest.main()
