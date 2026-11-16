#!/usr/bin/env python3
"""Builds mods/dualwield's mod.ff, from the player's own game files, in one of two ways.

--archive: from the player's copy of the "Relaxing Dual Wield" mod (2015, Call of the Dead). That mod replaces Call
of the Dead's patch zone and gives its weapons other weapons' names (M1911 -> PPSh, M72 LAW -> Thundergun). This takes
only the dual-wield weapons out of it, under names of their own, so nothing retail is replaced and the weapons work on
every map:

    dw_ppsh_zm                                        the PPSh-41 (box weapon)
    dw_ppsh_upgraded_zm + dw_ppsh_upgraded_lh_zm      "The Grim Reapers", two PPSh
    dw_ray_gun_upgraded_zm + dw_ray_gun_upgraded_lh_zm    two Ray Guns
    dw_thundergun_upgraded_zm + dw_thundergun_upgraded_lh_zm    "Zeus and Hera", two Thunderguns

--retail: the Ray Gun and Thundergun pairs only, made from the retail zones alone (common_zombie, zombie_theater):
each gun is the retail upgraded weapon with the animations, view offsets and dual-wield fields of a retail pair (the
Mustang & Sally's for the Ray Guns, the Typhoid & Mary's for the Thunderguns), and a copy of its retail model placed in
the hand (glbfit.py; the left gun's bones take BO1's left-hand suffix "1"). There is no PPSh, and both hands reload with
the retail pair's animation.

Steps: unlink the source zones with OAT's Unlinker, write an OAT Linker project (T5) with the new weapons and their
names, link it against the retail zones. Images whose pixels the new zone embeds go to <out>/images: BO1 draws embedded
pixels of a mod.ff black (docs/BO2_WEAPONS.md, "Images"). The result is the player's own game data: keep it out of the
repository.

    tools/dualwield/dualwield_mod.py --archive zm_relaxing_dual_wield.rar --game build/Release --work /tmp/dw \
        --out build/Release/mods/dualwield
    tools/dualwield/dualwield_mod.py --retail --game build/Release --work /tmp/dw --out build/Release/mods/dualwield

Then convert <out>/mod.ff with ffconv for the 64-bit builds (mods/dualwield/README.md).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glbfit  # noqa: E402

OAT = os.path.expanduser("~/bo2tools/oat-src/build/bin/Release_x64")

# source weapon in the mod's zone -> (our name, its left/right twin or "", localize key, English name)
WEAPONS = {
    "m1911_zm": ("dw_ppsh_zm", "", "DUALWIELD_PPSH", "PPSh-41"),
    "m1911_upgraded_zm": ("dw_ppsh_upgraded_zm", "dw_ppsh_upgraded_lh_zm", "DUALWIELD_PPSH_UPGRADED",
                          "The Grim Reapers"),
    "m1911_upgraded_lh_zm": ("dw_ppsh_upgraded_lh_zm", "dw_ppsh_upgraded_zm", "DUALWIELD_PPSH_UPGRADED",
                             "The Grim Reapers"),
    "ray_gun_upgraded_zm": ("dw_ray_gun_upgraded_zm", "dw_ray_gun_upgraded_lh_zm", "DUALWIELD_RAY_GUN_UPGRADED",
                            "Porter's X2 Ray Guns"),
    "ray_gun_upgraded_lh_zm": ("dw_ray_gun_upgraded_lh_zm", "dw_ray_gun_upgraded_zm", "DUALWIELD_RAY_GUN_UPGRADED",
                               "Porter's X2 Ray Guns"),
    "m72_law_upgraded_zm": ("dw_thundergun_upgraded_zm", "dw_thundergun_upgraded_lh_zm",
                            "DUALWIELD_THUNDERGUN_UPGRADED", "Zeus and Hera"),
    "m72_law_upgraded_lh_zm": ("dw_thundergun_upgraded_lh_zm", "dw_thundergun_upgraded_zm",
                               "DUALWIELD_THUNDERGUN_UPGRADED", "Zeus and Hera"),
}
# OAT cannot unlink or link BO1 effects: an effect the reference zones lack becomes the closest one they have. The
# Thundergun's own flashes are in Kino's and Ascension's zones only; the shot's cloud is the script's (_dualwield.gsc).
FX_SUBSTITUTES = {
    "weapon/muzzleflashes/fx_ppsh_flash": "weapon/muzzleflashes/fx_smg_flash_base",
    "weapon/muzzleflashes/fx_ppsh_flash_upg": "weapon/muzzleflashes/fx_zombie_smg_flash_base_ug",
    "weapon/muzzleflashes/fx_thundergun_view_ug": "weapon/muzzleflashes/fx_zombie_shotgun_flash_base_ug",
    "weapon/muzzleflashes/fx_thundergun_world_ug": "weapon/muzzleflashes/fx_zombie_shotgun_flash_base_ug",
}
# A dual-wield pair's ammo as BO1's own pairs and the mod's PPSh count it (cz75dw_upgraded_zm: 16 clips of 20 with
# ammoCountClipRelative, cz75lh_upgraded_zm: 320 rounds): the right gun in clips, the left gun in rounds, both clips
# included. The mod's Ray Gun and Thundergun pairs gave both guns 400 / 48 rounds, so GiveStartAmmo (the
# Pack-a-Punch's) left the left clip empty. Same supply here: 11 clips of 40, 13 clips of 4.
AMMO = {
    "dw_ray_gun_upgraded_zm": {"ammoCountClipRelative": "1", "startAmmo": "11", "maxAmmo": "11"},
    "dw_ray_gun_upgraded_lh_zm": {"ammoCountClipRelative": "0", "startAmmo": "440", "maxAmmo": "440"},
    "dw_thundergun_upgraded_zm": {"ammoCountClipRelative": "1", "startAmmo": "13", "maxAmmo": "13"},
    "dw_thundergun_upgraded_lh_zm": {"ammoCountClipRelative": "0", "startAmmo": "52", "maxAmmo": "52"},
}
EXTRA_STRINGS = {"ZOMBIE_WEAPON_DUALWIELD": "Hold ^3[{+activate}]^7 to buy weapon [Cost: &&1]"}
SOURCE_ZONE = "zombie_coast_patch"
# zones whose assets the weapons reference instead of carrying them (loaded on every zombie map)
REFERENCE_ZONES = ["code_post_gfx", "common", "common_zombie", "common_zombie_patch"]
# --retail: our weapon -> (retail weapon it shoots as, retail dual-wield weapon whose hand it takes, view model
# (source, scale, offset, bone suffix), world model (same, or None to keep the source's)). The scale and offsets put the
# retail model's grip in the pair's hand, where the 2015 mod put its copies. The left guns' bones take BO1's left-hand
# suffix (t5_weapon_cz75_dw_lh_viewmodel: j_gun1, tag_flash1).
RETAIL = {
    "dw_ray_gun_upgraded_zm": ("ray_gun_upgraded_zm", "m1911_upgraded_zm",
                               ("viewmodel_zombie_raygun_up", 1.0, (1.188, -1.118, 0.0), ""), None),
    "dw_ray_gun_upgraded_lh_zm": ("ray_gun_upgraded_zm", "m1911lh_upgraded_zm",
                                  ("viewmodel_zombie_raygun_up", 1.0, (1.188, -1.118, 0.0), "1"),
                                  ("weapon_usa_ray_gun", 1.0, (0.0, 0.0, 0.0), "1")),
    "dw_thundergun_upgraded_zm": ("thundergun_upgraded_zm", "hs10_upgraded_zm",
                                  ("t5_weapon_thundergun_viewmodel", 0.6322, (-7.943, -3.75, 0.0), ""),
                                  ("t5_weapon_thundergun_world", 1.0, (-1.226, -1.885, 0.0), "")),
    "dw_thundergun_upgraded_lh_zm": ("thundergun_upgraded_zm", "hs10lh_upgraded_zm",
                                     ("t5_weapon_thundergun_viewmodel", 0.6408, (-7.461, -3.523, 0.0), "1"),
                                     ("t5_weapon_thundergun_world", 1.0, (-0.95, -1.406, 0.0), "1")),
}
# the zones the retail weapons and models come from: the Thundergun is in Kino's (and Ascension's) only, so its models
# and materials are carried by mod.ff, the Ray Gun's are referenced
RETAIL_ZONES = ["common_zombie", "zombie_theater"]
# fields a retail gun takes from the retail pair's weapon: animations, the gun's place in view, dual-wield handling
HAND_FIELDS = re.compile(r"anim|^dtp_|^(stand|ducked|prone|sprint|strafe|mantle|pos)[A-Z]|^dualWield$|^aimDownSight$",
                         re.I)
NOT_HAND_FIELDS = {"standMountedWeapdef", "proneMountedWeapdef"}
# unlinked folders that are not weapon data (the Call of the Dead scripts, the mod's zone list)
SKIP_DIRS = {"maps", "clientscripts", "mod", "tahcep", "zone_source", "weapons"}


def run(cmd, log, all_lines=False):
    with open(log, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    with open(log, errors="replace") as f:
        lines = f.read().splitlines()
    if r.returncode:
        sys.exit("%s failed (%d), see %s: %s" % (os.path.basename(cmd[0]), r.returncode, log, " / ".join(lines[-3:])))
    return lines if all_lines else lines[-3:]


def find_member(root, name):
    for d, _, files in os.walk(root):
        for f in files:
            if f.lower() == name.lower():
                return os.path.join(d, f)
    return None


def weapon_fields(path):
    with open(path, encoding="latin-1") as f:
        parts = f.read().split("\\")
    if parts[0] != "WEAPONFILE" or len(parts) % 2 != 1:
        sys.exit("%s: not an OAT weapon file" % path)
    return list(zip(parts[1::2], parts[2::2]))


def write_fields(dst, fields):
    with open(dst, "w", encoding="latin-1", newline="") as f:
        f.write("WEAPONFILE" + "".join("\\%s\\%s" % kv for kv in fields))


def write_weapon(src, dst, twin, key, xanims):
    write_fields(dst, rename_fields(weapon_fields(src), os.path.basename(dst), twin, key, xanims))


def rename_fields(source, name, twin, key, xanims):
    fields = []
    for k, v in source:
        if k == "displayName":
            v = key
        elif k in AMMO.get(name, {}):
            v = AMMO[name][k]
        elif k == "DualWieldWeapon":
            v = twin
        v = FX_SUBSTITUTES.get(v, v)
        # the Unlinker writes lower-case xanim files; a weapon may name one in another case (viewmodel_ppsh_ADS_up)
        v = xanims.get(v.lower(), v) if v.lower() != v else v
        fields.append((k, v))
    return fields


def retail_fields(base, hand, view, world):
    """The retail weapon `base` (field list) held as the retail pair weapon `hand` (dict) holds its gun."""
    out = []
    for k, v in base:
        if HAND_FIELDS.search(k) and k not in NOT_HAND_FIELDS:
            if k not in hand:
                sys.exit("the dual-wield weapon has no field %s" % k)
            v = hand[k]
        elif k == "gunModel":
            v = view
        elif k == "worldModel" and world:
            v = world
        out.append((k, v))
    return out


def fit_model(dumps, source, new, scale, offset, suffix, raw):
    """raw/xmodel/<new>.json and its LODs: the retail model `source` fitted by glbfit."""
    for d in dumps:
        src = os.path.join(d, "xmodel", source + ".json")
        if os.path.isfile(src):
            break
    else:
        sys.exit("model %s not found in %s" % (source, ", ".join(dumps)))
    with open(src) as f:
        model = json.load(f)
    for i, lod in enumerate(model["lods"]):
        with open(os.path.join(d, lod["file"]), "rb") as f:
            data = glbfit.fit_glb(f.read(), scale, offset, suffix)
        lod["file"] = "model_export/%s_lod%d.glb" % (new, i)
        with open(os.path.join(raw, lod["file"]), "wb") as f:
            f.write(data)
    with open(os.path.join(raw, "xmodel", new + ".json"), "w") as f:
        json.dump(model, f, indent=4)


def unlinker(a, args, log, all_lines=False):
    return run([os.path.join(a.oat, "Unlinker"), "--no-color"] + args, os.path.join(a.work, log), all_lines)


def write_project(proj, keys, weapons, ignores=()):
    """The Linker project's zone list and English names; the weapons are already in zone_raw/dualwield/weapons.
    `ignores` names zone definitions in zone_source whose assets the zone only references."""
    raw = os.path.join(proj, "zone_raw", "dualwield")
    loc = os.path.join(raw, "english", "localizedstrings")
    os.makedirs(loc)
    with open(os.path.join(loc, "dualwield.str"), "w", newline="\r\n") as f:
        f.write('VERSION             "1"\nCONFIG              "C:/projects/cod/t5/bin/StringEd.cfg"\n'
                'FILENOTES           ""\n\n')
        for k, v in keys.items():
            f.write('REFERENCE           %s\nLANG_ENGLISH        "%s"\n\n' % (k, v))
        f.write("ENDMARKER\n")
    os.makedirs(os.path.join(proj, "zone_source"), exist_ok=True)
    with open(os.path.join(proj, "zone_source", "dualwield.zone"), "w") as f:
        f.write(">game,T5\n\n")
        for z in ignores:
            f.write("ignore,%s\n" % z)
        f.write("localize,dualwield\n")
        for new in weapons:
            f.write("weapon,%s\n" % new)


def link(a, zones, proj, extra=()):
    cmd = [os.path.join(a.oat, "Linker"), "--no-color", "-b", proj]
    for z in REFERENCE_ZONES:
        cmd += ["-l", os.path.abspath(os.path.join(zones, z + ".ff"))]
    for d in extra:
        cmd += ["--add-asset-search-path", d]
    tail = run(cmd + ["dualwield"], os.path.join(a.work, "link.log"))
    built = os.path.join(proj, "zone_out", "dualwield", "dualwield.ff")
    if not os.path.isfile(built):
        sys.exit("the Linker wrote no zone: %s" % " / ".join(tail))
    return built


def ship(a, built, images, folders):
    """mod.ff, and the images named in `images` found in `folders` (their images/ subfolders)."""
    os.makedirs(os.path.join(a.out, "images"), exist_ok=True)
    shutil.copyfile(built, os.path.join(a.out, "mod.ff"))
    shipped, missing = 0, []
    for name in sorted(images):
        for d in folders:
            p = os.path.join(d, "images", name + ".iwi")
            if os.path.isfile(p):
                shutil.copyfile(p, os.path.join(a.out, "images", name + ".iwi"))
                shipped += 1
                break
        else:
            missing.append(name)
    return shipped, missing


def embedded_images(a, ff, name):
    """Names of the images whose pixels the zone `ff` carries (an images-only unlink without the iwds)."""
    out = os.path.join(a.work, name)
    unlinker(a, ["--include-assets", "image", "--image-format", "IWI", "-o", out, ff], name + ".log")
    emb = os.path.join(out, "images")
    return {os.path.splitext(n)[0] for n in os.listdir(emb)} if os.path.isdir(emb) else set()


def reference_lists(a, zones, proj):
    """zone_source/<zone>.zone listing each reference zone's assets. The Linker loads an asset it finds on disk before
    one of a zone loaded with -l, so the dumps on its search path would put copies of retail assets (animations,
    materials and their pixels) in mod.ff; an `ignore` of these lists makes them references instead."""
    os.makedirs(os.path.join(proj, "zone_source"), exist_ok=True)
    for z in REFERENCE_ZONES:
        lines = unlinker(a, ["--list", os.path.abspath(os.path.join(zones, z + ".ff"))], "list_%s.log" % z, all_lines=True)
        assets = [m.groups() for m in map(re.compile(r"^([a-z_]+), (.+)$").match, lines) if m]
        if not assets:
            sys.exit("no asset listed for %s" % z)
        with open(os.path.join(proj, "zone_source", z + ".zone"), "w") as f:
            f.write(">game,T5\n\n" + "".join("%s,%s\n" % kv for kv in assets))


def build_archive(a, zones):
    src = a.archive
    if os.path.isfile(src):
        src = os.path.join(a.work, "src")
        os.makedirs(src)
        subprocess.run(["bsdtar", "-xf", os.path.abspath(a.archive), "-C", src], check=True)
    ff = find_member(src, SOURCE_ZONE + ".ff")
    iwd = find_member(src, "iw_42.iwd")
    if not ff or not iwd:
        sys.exit("%s.ff or iw_42.iwd missing from %s" % (SOURCE_ZONE, a.archive))
    with open(ff, "rb") as f:
        if f.read(8) != b"IWffu100":
            sys.exit("%s: not a BO1 PC fastfile" % ff)
    with zipfile.ZipFile(iwd) as z:
        mod_images = {os.path.splitext(os.path.basename(n))[0] for n in z.namelist() if n.lower().endswith(".iwi")}

    # the zone's own images: those the archive's zone embeds (dumped without the iwds) and those of its iwd
    unl = os.path.join(a.work, "unl")
    embedded = embedded_images(a, ff, "embedded")
    search = ";".join([os.path.dirname(iwd), os.path.abspath(os.path.join(a.game, "main"))])
    unlinker(a, ["--image-format", "IWI", "--model-format", "GLB", "--search-path", search, "-o", unl, ff],
             "unlink.log")

    proj = os.path.join(a.work, "proj")
    raw = os.path.join(proj, "zone_raw", "dualwield")
    os.makedirs(os.path.join(raw, "weapons"))
    for d in os.listdir(unl):
        if d not in SKIP_DIRS and os.path.isdir(os.path.join(unl, d)):
            shutil.copytree(os.path.join(unl, d), os.path.join(raw, d))
    keys = dict(EXTRA_STRINGS)
    xanim_dir = os.path.join(raw, "xanim")
    xanims = {n.lower(): n for n in os.listdir(xanim_dir)} if os.path.isdir(xanim_dir) else {}
    for name, (new, twin, key, text) in WEAPONS.items():
        write_weapon(os.path.join(unl, "weapons", name), os.path.join(raw, "weapons", new), twin, key, xanims)
        keys[key] = text
    write_project(proj, keys, [new for new, _, _, _ in WEAPONS.values()])
    built = link(a, zones, proj)
    # images the mod's iwd holds but its zone never names are not shipped: only those the unlink wrote
    shipped, _ = ship(a, built, {n for n in mod_images | embedded
                                 if os.path.isfile(os.path.join(raw, "images", n + ".iwi"))}, [raw])
    return len(WEAPONS), built, shipped


def build_retail(a, zones):
    for z in RETAIL_ZONES:
        if not os.path.isfile(os.path.join(zones, z + ".ff")):
            sys.exit("%s.ff not found in %s" % (z, zones))
    dumps = [os.path.join(a.work, "retail", z) for z in RETAIL_ZONES]
    unlinker(a, ["--image-format", "IWI", "--model-format", "GLB", "--search-path",
                 os.path.abspath(os.path.join(a.game, "main")), "-o", os.path.join(a.work, "retail", "?zone?")]
             + [os.path.abspath(os.path.join(zones, z + ".ff")) for z in RETAIL_ZONES], "unlink.log")

    def weapon(name):
        for d in dumps:
            p = os.path.join(d, "weapons", name)
            if os.path.isfile(p):
                return weapon_fields(p)
        sys.exit("weapon %s not found in %s" % (name, ", ".join(dumps)))

    proj = os.path.join(a.work, "proj")
    raw = os.path.join(proj, "zone_raw", "dualwield")
    for d in ("weapons", "xmodel", "model_export"):
        os.makedirs(os.path.join(raw, d))
    names = {new: (twin, key, text) for new, twin, key, text in WEAPONS.values()}
    keys = {}
    for new, (base, hand, view, world) in RETAIL.items():
        twin, key, text = names[new]
        view_name = new + "_view"
        fit_model(dumps, view[0], view_name, *view[1:], raw)
        world_name = None
        if world:
            world_name = new + "_world"
            fit_model(dumps, world[0], world_name, *world[1:], raw)
        fields = retail_fields(weapon(base), dict(weapon(hand)), view_name, world_name)
        write_fields(os.path.join(raw, "weapons", new), rename_fields(fields, new, twin, key, {}))
        keys[key] = text
    reference_lists(a, zones, proj)
    write_project(proj, keys, list(RETAIL), REFERENCE_ZONES)
    # what the reference zones lack comes from the dumps: the accuracy graphs (files, not zone assets) and the
    # Thundergun's materials, techniques and images (Kino's zone)
    built = link(a, zones, proj, [os.path.abspath(d) for d in dumps])
    shipped, missing = ship(a, built, embedded_images(a, built, "embedded"), dumps)
    if missing:
        sys.exit("images embedded in mod.ff but in no dump: %s" % ", ".join(missing))
    return len(RETAIL), built, shipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--archive", help="zm_relaxing_dual_wield.rar (or the folder it extracts to)")
    src.add_argument("--retail", action="store_true", help="the Ray Gun and Thundergun pairs from the retail zones")
    ap.add_argument("--game", required=True, help="BO1 install (holds zone/Common and main/iw_*.iwd), only read")
    ap.add_argument("--work", required=True, help="scratch folder (emptied)")
    ap.add_argument("--out", required=True, help="the mod folder: mod.ff and images/ are written there")
    ap.add_argument("--oat", default=OAT, help="folder of OAT's Unlinker and Linker (tools/bo2/oat/README.md)")
    a = ap.parse_args()

    zones = os.path.join(a.game, "zone", "Common")
    if not os.path.isdir(zones):
        zones = os.path.join(a.game, "zone", "common")
    for z in REFERENCE_ZONES:
        if not os.path.isfile(os.path.join(zones, z + ".ff")):
            sys.exit("%s.ff not found in %s" % (z, zones))
    shutil.rmtree(a.work, ignore_errors=True)
    os.makedirs(a.work)

    count, built, shipped = build_retail(a, zones) if a.retail else build_archive(a, zones)
    print("dualwield: %d weapons, mod.ff %d bytes, %d images -> %s" % (
        count, os.path.getsize(built), shipped, a.out))


if __name__ == "__main__":
    main()
