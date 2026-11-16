"""tools/dualwield/dualwield_mod.py and glbfit.py: how mods/dualwield's weapons are made, from the "Relaxing Dual
Wield" zone or from the retail weapons and models.

    python3 -m unittest discover -s tests/dualwield -v
"""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "dualwield"))
import dualwield_mod as D  # noqa: E402
import glbfit as G  # noqa: E402


def weapon_file(path, fields):
    with open(path, "w", encoding="latin-1", newline="") as f:
        f.write("WEAPONFILE" + "".join("\\%s\\%s" % kv for kv in fields))


class WriteWeaponTest(unittest.TestCase):
    def rewrite(self, source, name, fields, xanims=None):
        new, twin, key, _ = D.WEAPONS[source]
        self.assertEqual(new, name)
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = os.path.join(tmp, source), os.path.join(tmp, new)
            weapon_file(src, fields)
            D.write_weapon(src, dst, twin, key, xanims or {})
            return dict(D.weapon_fields(dst)), twin, key

    def test_pair_names_and_ammo(self):
        out, twin, key = self.rewrite("ray_gun_upgraded_zm", "dw_ray_gun_upgraded_zm", [
            ("displayName", "Dual Wield Ray Gun"), ("DualWieldWeapon", "ray_gun_upgraded_lh_zm"),
            ("ammoCountClipRelative", "0"), ("startAmmo", "400"), ("maxAmmo", "400"), ("clipSize", "40")])
        self.assertEqual(out["displayName"], key)
        self.assertEqual(out["DualWieldWeapon"], "dw_ray_gun_upgraded_lh_zm")
        self.assertEqual(twin, "dw_ray_gun_upgraded_lh_zm")
        # the right gun counts clips, the left one rounds: 11 x 40 = 440
        self.assertEqual((out["ammoCountClipRelative"], out["startAmmo"], out["maxAmmo"]), ("1", "11", "11"))
        left, _, _ = self.rewrite("ray_gun_upgraded_lh_zm", "dw_ray_gun_upgraded_lh_zm", [
            ("DualWieldWeapon", "ray_gun_upgraded_zm"), ("ammoCountClipRelative", "0"), ("startAmmo", "400"),
            ("maxAmmo", "400")])
        self.assertEqual((left["DualWieldWeapon"], left["startAmmo"]), ("dw_ray_gun_upgraded_zm", "440"))

    def test_effects_and_xanim_case(self):
        out, _, _ = self.rewrite("m1911_zm", "dw_ppsh_zm", [
            ("viewFlashEffect", "weapon/muzzleflashes/fx_ppsh_flash"),
            ("worldShellEjectEffect", "weapon/shellejects/fx_pistol"),
            ("adsUpAnim", "viewmodel_ppsh_ADS_up"), ("idleAnim", "viewmodel_ppsh_idle"), ("startAmmo", "5")],
            xanims={"viewmodel_ppsh_ads_up": "viewmodel_ppsh_ads_up"})
        self.assertEqual(out["viewFlashEffect"], "weapon/muzzleflashes/fx_smg_flash_base")
        self.assertEqual(out["worldShellEjectEffect"], "weapon/shellejects/fx_pistol")
        self.assertEqual(out["adsUpAnim"], "viewmodel_ppsh_ads_up")
        self.assertEqual(out["idleAnim"], "viewmodel_ppsh_idle")
        # the box PPSh keeps the mod's ammo
        self.assertEqual(out["startAmmo"], "5")

    def test_every_pair_names_its_twin(self):
        names = {new: twin for new, twin, _, _ in D.WEAPONS.values()}
        for new, twin in names.items():
            if twin:
                self.assertEqual(names[twin], new)
        self.assertEqual(len(names), 7)

    def test_rejects_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x")
            with open(path, "w") as f:
                f.write("not a weapon")
            with self.assertRaises(SystemExit):
                D.weapon_fields(path)


class RetailFieldsTest(unittest.TestCase):
    def test_hand_fields_come_from_the_pair(self):
        base = [("displayName", "ZOMBIE_RAY_GUN_UPGRADED"), ("gunModel", "viewmodel_zombie_raygun_up"),
                ("worldModel", "weapon_usa_ray_gun"), ("idleAnim", "viewmodel_ray_gun_idle"),
                ("playerAnimType", "default"), ("dualWield", "0"), ("standMoveR", "2.5"),
                ("standMountedWeapdef", "x"), ("damage", "1000"), ("clipSize", "40"), ("DualWieldWeapon", "")]
        hand = {"idleAnim": "viewmodel_colt1911_dw_right_idle_loop", "playerAnimType": "dualwield",
                "dualWield": "1", "standMoveR": "1", "standMountedWeapdef": "y", "damage": "5", "clipSize": "6"}
        out = dict(D.retail_fields(base, hand, "dw_view", None))
        self.assertEqual(out["idleAnim"], "viewmodel_colt1911_dw_right_idle_loop")
        self.assertEqual((out["playerAnimType"], out["dualWield"], out["standMoveR"]), ("dualwield", "1", "1"))
        # the gun shoots as the retail upgraded weapon
        self.assertEqual((out["damage"], out["clipSize"], out["standMountedWeapdef"]), ("1000", "40", "x"))
        self.assertEqual((out["gunModel"], out["worldModel"]), ("dw_view", "weapon_usa_ray_gun"))
        out = dict(D.retail_fields(base, hand, "dw_view", "dw_world"))
        self.assertEqual(out["worldModel"], "dw_world")
        named = dict(D.rename_fields(list(out.items()), "dw_ray_gun_upgraded_zm", "dw_ray_gun_upgraded_lh_zm",
                                     "DUALWIELD_RAY_GUN_UPGRADED", {}))
        self.assertEqual(named["DualWieldWeapon"], "dw_ray_gun_upgraded_lh_zm")
        self.assertEqual(named["displayName"], "DUALWIELD_RAY_GUN_UPGRADED")

    def test_missing_hand_field_fails(self):
        with self.assertRaises(SystemExit):
            D.retail_fields([("fireAnim", "a")], {}, "v", None)

    def test_retail_table(self):
        names = {new for new, _, _, _ in D.WEAPONS.values()}
        self.assertEqual(set(D.RETAIL) - names, set())
        for new, (_, hand, view, world) in D.RETAIL.items():
            left = new.endswith("_lh_zm")
            self.assertEqual(hand.endswith("lh_upgraded_zm"), left, new)
            for model in filter(None, (view, world)):
                self.assertEqual(model[3], "1" if left else "", new)
            # a right gun keeps the retail world model only when it needs no fitting
            if world is None:
                self.assertFalse(left)


def tiny_glb():
    """A skinned triangle: root j_gun turned -90 degrees about X, tag_flash below it, OAT's layout."""
    s = 0.7071067811865476
    doc = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [3]}],
        "nodes": [{"name": "j_gun", "translation": [0, 0, 0], "rotation": [-s, 0, 0, s], "children": [1]},
                  {"name": "tag_flash", "translation": [10, 0, 2], "rotation": [0, 0, 0, 1]},
                  {"name": "surf0", "skin": 0, "mesh": 0},
                  {"name": "x_skel", "children": [0, 2]}],
        "skins": [{"joints": [0, 1], "skeleton": 0, "inverseBindMatrices": 1}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "min": [0, 0, 0], "max": [10, 2, 0]},
                      {"bufferView": 1, "componentType": 5126, "count": 2, "type": "MAT4"}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                        {"buffer": 0, "byteOffset": 36, "byteLength": 128}],
        "buffers": [{"byteLength": 164}],
    }
    bin_ = struct.pack("<9f", 0, 0, 0, 10, 0, 0, 0, 2, 0) + bytes(128)
    # the exporter's inverse bind matrices, recomputed by an identity fit
    return G.fit_glb(G.write_glb(doc, bytearray(bin_)))


class GlbFitTest(unittest.TestCase):
    def test_move_scale_and_suffix(self):
        doc, bin_ = G.read_glb(G.fit_glb(tiny_glb(), 2.0, (1.0, -1.0, 0.0), "1"))
        self.assertEqual([n["name"] for n in doc["nodes"]], ["j_gun1", "tag_flash1", "surf0", "x_skel"])
        pts = struct.unpack_from("<9f", bin_, 0)
        self.assertEqual(pts, (1, -1, 0, 21, -1, 0, 1, 3, 0))
        self.assertEqual((doc["accessors"][0]["min"], doc["accessors"][0]["max"]), ([1, -1, 0], [21, 3, 0]))
        # the root stays where the hand holds it; tag_flash, (10, 2, 0) in model space, moves with the mesh
        self.assertEqual(doc["nodes"][0]["translation"], [0, 0, 0])
        worlds, _ = G.world_transforms(doc)
        for got, want in zip(worlds[1][1], (21, 3, 0)):
            self.assertAlmostEqual(got, want, places=4)
        # inverse bind matrix of tag_flash: maps its world position to the origin
        ibm = struct.unpack_from("<16f", bin_, 36 + 64)
        r, t = worlds[1]
        mapped = [sum(ibm[4 * c + row] * v for c, v in enumerate(list(t) + [1])) for row in range(3)]
        for v in mapped:
            self.assertAlmostEqual(v, 0, places=4)

    def test_identity_keeps_the_model(self):
        data = tiny_glb()
        doc0, bin0 = G.read_glb(data)
        doc1, bin1 = G.read_glb(G.fit_glb(data))
        self.assertEqual([n.get("name") for n in doc0["nodes"]], [n.get("name") for n in doc1["nodes"]])
        for a, b in zip(struct.unpack("<41f", bytes(bin0)), struct.unpack("<41f", bytes(bin1))):
            self.assertAlmostEqual(a, b, places=5)

    def test_rejects_clashing_names_and_bad_files(self):
        doc, bin_ = G.read_glb(tiny_glb())
        doc["nodes"][1]["name"] = "j_gun1"
        doc["nodes"][0]["name"] = "j_gun"
        doc["nodes"][2]["name"] = "j_gun11"
        with self.assertRaises(ValueError):
            G.fit_glb(G.write_glb(doc, bin_), suffix="1")
        with self.assertRaises(ValueError):
            G.fit_glb(b"not a glb at all, no")
        doc, bin_ = G.read_glb(tiny_glb())
        doc["nodes"][1]["scale"] = [2, 2, 2]
        with self.assertRaises(ValueError):
            G.fit_glb(G.write_glb(doc, bin_))
        self.assertEqual(json.loads(json.dumps(G.bone_names(tiny_glb()))), ["j_gun", "tag_flash"])


if __name__ == "__main__":
    unittest.main()
