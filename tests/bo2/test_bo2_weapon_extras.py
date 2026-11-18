"""The scripted BO2 weapons MapKit sells (tools/bo2/bo2_weapon.py EXTRAS, OVERRIDES), on made-up weapon files."""
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bo2"))

import bo2_weapon  # noqa: E402


def write(path, pairs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bo2_weapon.write_weapon(path, pairs)


class Extras(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.bo2, self.bo1, self.out = (os.path.join(root, d) for d in ("bo2", "bo1", "out"))
        os.makedirs(os.path.join(self.bo1, "materials"))
        os.makedirs(os.path.join(self.bo1, "xanim"))
        os.makedirs(os.path.join(self.bo2, "xanim"))
        # BO1 has the perk bottle's anim; BO2's dump has its own copy under the same name
        for folder in (self.bo1, self.bo2):
            with open(os.path.join(folder, "xanim", "viewmodel_zombie_perksacola_idle"), "wb") as f:
                f.write(b"\0")  # no notetracks
        write(os.path.join(self.bo1, "weapons", "zombie_cymbal_monkey"),
              [("offhandClass", "Smoke Grenade"), ("projExplosionType", "grenade"),
               ("projExplosionEffect", "weapon/satchel/fx_explosion_satchel_generic"),
               ("projExplosionSound", "wpn_grenade_explode"), ("projectileModel", "weapon_zombie_monkey_bomb"),
               ("worldModel", "viewmodel_zombie_cymbal_monkey"), ("fuseTime", "8")])
        write(os.path.join(self.bo2, "weapons", "emp_grenade_zm"),
              [("offhandClass", "Flash Grenade"), ("projExplosionType", "smoke"),
               ("projExplosionEffect", "maps/zombie/fx_zmb_wep_emp_explo"), ("projExplosionSound", "wpn_emp_explode"),
               ("projectileModel", "t6_wpn_grenade_emp_world"), ("worldModel", "t6_wpn_grenade_emp_world"),
               ("fuseTime", "1")])
        write(os.path.join(self.bo1, "weapons", "zombie_bowie_flourish"),
              [("idleAnim", "viewmodel_zombie_perksacola_idle"), ("raiseAnim", "viewmodel_zombie_bowie")])
        write(os.path.join(self.bo2, "weapons", "zombie_tazer_flourish"),
              [("idleAnim", "viewmodel_zombie_perksacola_idle"), ("raiseAnim", "viewmodel_tazor_knuckles_first_raise")])
        # Five's Death Machine, the Jet Gun's reference, comes from a map dump of its own
        self.five = os.path.join(root, "five")
        write(os.path.join(self.five, "weapons", "minigun_zm"),
              [("fireType", "Minigun"), ("damage", "500"), ("viewFlashEffect", "weapon/muzzleflashes/fx_minigun"),
               ("spinLoopSoundPlayer", "wpn_minigun_loop_plr"), ("clipSize", "500"), ("maxAmmo", "500"),
               ("startAmmo", "400"), ("unlimitedAmmo", "1"), ("overheatWeapon", "0"), ("fireTime", "0.05"),
               ("spinUpTime", "0.25"), ("minDamage", "300"), ("worldFlashEffect", ""), ("viewShellEjectEffect", ""),
               ("worldShellEjectEffect", ""), ("viewLastShotEjectEffect", ""), ("worldLastShotEjectEffect", ""),
               ("tracerFrequency", "2"), ("fireSound", ""), ("fireSoundPlayer", ""), ("lastShotSound", ""),
               ("lastShotSoundPlayer", ""), ("loopFireSound", "wpn_minigun_fire_loop_npc"),
               ("loopFireSoundPlayer", "wpn_minigun_fire_loop_plr"), ("loopFireEndSound", ""),
               ("loopFireEndSoundPlayer", "")])
        write(os.path.join(self.bo2, "weapons", "jetgun_zm"),
              [("fireType", "Jetgun"), ("damage", "0"), ("viewFlashEffect", "weapon/jet_gun/fx_jetgun_on"),
               ("spinLoopSoundPlayer", "wpn_jetgun_fire_plr_loop"), ("clipSize", "500"), ("overheatWeapon", "1"),
               ("spinUpTime", "3")])
        self.project = bo2_weapon.Project(types.SimpleNamespace(dump=[self.bo2], bo1=self.bo1, out=self.out,
                                                                bo1_map=[self.five]))

    def tearDown(self):
        self.tmp.cleanup()

    def converted(self, name):
        return dict(bo2_weapon.read_weapon(os.path.join(self.out, "zone_raw", "mod", "weapons", name)))

    def test_emp_overrides(self):
        # the world model is not in this dump: the converter falls back on the reference's, and the projectile follows
        self.project.weapon("emp_grenade_zm", "zombie_cymbal_monkey", extra=True)
        emp = self.converted("emp_grenade_zm")
        self.assertEqual(emp["offhandClass"], "Smoke Grenade")
        self.assertEqual(emp["projExplosionType"], "grenade")
        self.assertEqual(emp["projExplosionEffect"], "")
        self.assertEqual(emp["projExplosionSound"], "")
        self.assertEqual(emp["projectileModel"], emp["worldModel"])
        self.assertEqual(emp["fuseTime"], "1")

    def test_extra_keeps_bo1_assets_of_the_same_name(self):
        self.project.weapon("zombie_tazer_flourish", "zombie_bowie_flourish", extra=True)
        self.assertEqual(self.converted("zombie_tazer_flourish")["idleAnim"], "viewmodel_zombie_perksacola_idle")
        self.assertNotIn("viewmodel_zombie_perksacola_idle", self.project.xanims)

    def test_box_weapon_converts_a_same_named_anim(self):
        # outside EXTRAS the rule is unchanged: BO2's copy is converted
        self.project.weapon("zombie_tazer_flourish", "zombie_bowie_flourish")
        self.assertIn("viewmodel_zombie_perksacola_idle", self.project.xanims)

    def test_jetgun_on_the_death_machine_of_a_map_dump(self):
        self.project.weapon("jetgun_zm", "minigun_zm", extra=True)
        jet = self.converted("jetgun_zm")
        self.assertEqual(jet["fireType"], "Minigun")  # BO2's "Jetgun" is no BO1 fire type: the reference's
        self.assertEqual(jet["spinLoopSoundPlayer"], "wpn_minigun_loop_plr")  # BO1 has no BO2 sound
        self.assertEqual((jet["viewFlashEffect"], jet["loopFireSoundPlayer"], jet["damage"]), ("", "", "0"))
        self.assertEqual((jet["clipSize"], jet["maxAmmo"], jet["unlimitedAmmo"], jet["overheatWeapon"]),
                         ("100", "0", "0", "0"))
        self.assertEqual((jet["fireTime"], jet["spinUpTime"]), ("0.06", "0.6"))

    def test_override_of_a_key_the_reference_lacks_stops(self):
        saved = dict(bo2_weapon.OVERRIDES)
        bo2_weapon.OVERRIDES["zombie_tazer_flourish"] = {"noSuchKey": "1"}
        try:
            with self.assertRaises(SystemExit):
                self.project.weapon("zombie_tazer_flourish", "zombie_bowie_flourish", extra=True)
        finally:
            bo2_weapon.OVERRIDES.clear()
            bo2_weapon.OVERRIDES.update(saved)

    def test_accented_name_reaches_bo1_as_one_character(self):
        loc = os.path.join(self.tmp.name, "loc", "french", "localizedstrings")
        os.makedirs(loc)
        with open(os.path.join(loc, "fr_zm.str"), "w", encoding="utf-8") as f:
            f.write('REFERENCE           ZMWEAPON_JETGUN\nLANG_FRENCH         "Modèle 23"\n')
        strings = bo2_weapon.read_strings(os.path.join(self.tmp.name, "loc"))
        self.assertEqual(strings["ZMWEAPON_JETGUN"], "Modèle 23")
        self.project.localize(sorted(strings.items()))
        with open(os.path.join(self.out, "zone_raw", "mod", "english", "localizedstrings", "bo2weapons.str"), "rb") as f:
            self.assertIn(b'"Mod\xe8le 23"', f.read())


if __name__ == "__main__":
    unittest.main()
