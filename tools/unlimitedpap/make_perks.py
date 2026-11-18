#!/usr/bin/env python3
"""Writes mods/unlimitedpap/maps/_zombiemode_perks.gsc from the player's own game files.

The mod needs the retail Pack-a-Punch script with 13 lines changed (each marked UNLIMITEDPAP, mods/unlimitedpap/README.md).
The retail script is game data, so the repository only holds the changes: this reads maps/_zombiemode_perks.gsc out of
the player's zone/Common/common_zombie_patch.ff (the version the game runs; common_zombie.ff holds an older one), applies
the changes at exact anchors and writes the result. A missing or ambiguous anchor stops it with nothing written.

    tools/unlimitedpap/make_perks.py --game build/Release --out build/Release/mods/unlimitedpap

The result is the player's own game data: keep it out of the repository (.gitignore lists it).
"""
import argparse
import os
import re
import sys
import zlib

ZONE = os.path.join("zone", "Common", "common_zombie_patch.ff")
SCRIPT = "maps/_zombiemode_perks.gsc"
MOD = r"maps\unlimitedpap\_unlimitedpap"

# (retail text, replacement), on the script's own CRLF lines. Each retail text must occur exactly once.
EDITS = [
    # third_person_weapon_upgrade: level.zombie_weapons has no entry for an upgraded gun
    ("third_person_weapon_upgrade( current_weapon, origin, angles, packa_rollers, perk_machine )\r\n{\r\n",
     "third_person_weapon_upgrade( current_weapon, origin, angles, packa_rollers, perk_machine )\r\n{\r\n"
     "\tupgrade_name = " + MOD + "::upgrade_of( current_weapon ); "
     "// UNLIMITEDPAP: level.zombie_weapons has no entry for an upgraded gun\r\n"),
    ("\tworldgun setModel( GetWeaponModel( level.zombie_weapons[current_weapon].upgrade_name ) );\r\n"
     "\tworldgun useweaponhidetags( level.zombie_weapons[current_weapon].upgrade_name );\r\n",
     "\tworldgun setModel( GetWeaponModel( upgrade_name ) );\r\n"
     "\tworldgun useweaponhidetags( upgrade_name );\r\n"),
    ("\tif ( maps\\_zombiemode_weapons::weapon_is_dual_wield( level.zombie_weapons[current_weapon].upgrade_name ) )\r\n",
     "\tif ( maps\\_zombiemode_weapons::weapon_is_dual_wield( upgrade_name ) )\r\n"),
    ("\t\tworldgundw setModel( maps\\_zombiemode_weapons::get_left_hand_weapon_model_name( "
     "level.zombie_weapons[current_weapon].upgrade_name ) );\r\n"
     "\t\tworldgundw useweaponhidetags( level.zombie_weapons[current_weapon].upgrade_name );\r\n",
     "\t\tworldgundw setModel( maps\\_zombiemode_weapons::get_left_hand_weapon_model_name( upgrade_name ) );\r\n"
     "\t\tworldgundw useweaponhidetags( upgrade_name );\r\n"),
    # vending_weapon_upgrade: the machine's hint shows the doubled price
    ("\tself thread vending_weapon_upgrade_cost();\r\n",
     "\tself thread vending_weapon_upgrade_cost();\r\n"
     "\tself thread " + MOD + "::hint_think(); // UNLIMITEDPAP\r\n"),
    # retail refused an already upgraded weapon
    ("\t\t\tplayer isThrowingGrenade() ||\r\n"
     "\t\t\tplayer maps\\_zombiemode_weapons::is_weapon_upgraded( current_weapon ) )\r\n",
     "\t\t\tplayer isThrowingGrenade() ) // UNLIMITEDPAP: retail also refused an already upgraded weapon here\r\n"),
    ("\t\tif ( !IsDefined( level.zombie_include_weapons[current_weapon] ) )\r\n",
     "\t\tif ( !IsDefined( level.zombie_include_weapons[current_weapon] ) || !IsDefined( " + MOD
     + "::upgrade_of( current_weapon ) ) ) // UNLIMITEDPAP: upgrade_of also accepts an upgraded gun\r\n"),
    # the price doubles with every pack
    ("\t\tif ( player.score < self.cost )\r\n",
     "\t\tcost = " + MOD + "::pap_cost( player, current_weapon, self.cost ); // UNLIMITEDPAP: doubles with every pack\r\n"
     "\t\tif ( player.score < cost )\r\n"),
    ("\t\tplayer maps\\_zombiemode_score::minus_to_player_score( self.cost ); \r\n",
     "\t\tplayer maps\\_zombiemode_score::minus_to_player_score( cost ); // UNLIMITEDPAP\r\n"),
    # wait_for_player_to_take: an upgraded gun upgrades to itself
    ("\tAssertEx( IsDefined( level.zombie_weapons[weapon] ), \"wait_for_player_to_take: weapon does not exist\" );\r\n"
     "\tAssertEx( IsDefined( level.zombie_weapons[weapon].upgrade_name ), "
     "\"wait_for_player_to_take: upgrade_weapon does not exist\" );\r\n"
     "\t\r\n"
     "\tupgrade_weapon = level.zombie_weapons[weapon].upgrade_name;\r\n",
     "\tupgrade_weapon = " + MOD + "::upgrade_of( weapon ); // UNLIMITEDPAP: was level.zombie_weapons[weapon].upgrade_name\r\n"),
    # the gun taken back counts one more pack
    ("\t\t\t\tplayer.pap_used = true;\r\n",
     "\t\t\t\tplayer.pap_used = true;\r\n"
     "\t\t\t\tplayer " + MOD + "::count_pack( weapon, upgrade_weapon ); // UNLIMITEDPAP\r\n"),
]


def read_rawfile(ff_path, name):
    """A rawfile's text from a PC fastfile: 'IWffu100' + version, one zlib stream from byte 12, and in it each rawfile
    as ff ff ff ff, its name, a NUL, u32 size, u32 compressed size, zlib data."""
    with open(ff_path, "rb") as f:
        data = f.read()
    if data[:8] != b"IWffu100":
        raise ValueError(f"{ff_path}: not a PC fastfile (header {data[:8]!r})")
    stream = zlib.decompressobj().decompress(data[12:])
    found = [m.end() for m in re.finditer(rb"\xff\xff\xff\xff" + re.escape(name.encode()) + rb"\x00", stream)]
    if len(found) != 1:
        raise ValueError(f"{ff_path}: {len(found)} copies of {name}, expected one")
    at = found[0]
    size = int.from_bytes(stream[at:at + 4], "little")
    packed = int.from_bytes(stream[at + 4:at + 8], "little")
    text = zlib.decompress(stream[at + 8:at + 8 + packed])
    if len(text) != size:
        raise ValueError(f"{ff_path}: {name} is {len(text)} bytes, its header says {size}")
    return text.decode("latin-1")


def apply_edits(text):
    for old, new in EDITS:
        count = text.count(old)
        if count != 1:
            raise ValueError(f"anchor found {count} times, expected once: {old.splitlines()[0].strip()!r}")
        text = text.replace(old, new)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", required=True, help="the game folder holding zone/Common (build/Release)")
    ap.add_argument("--out", required=True, help="mods/unlimitedpap of the install or package")
    a = ap.parse_args()
    try:
        text = apply_edits(read_rawfile(os.path.join(a.game, ZONE), SCRIPT))
    except (OSError, ValueError, zlib.error) as e:
        sys.exit(f"make_perks: {e}")
    dest = os.path.join(a.out, "maps", "_zombiemode_perks.gsc")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(text.encode("latin-1"))
    print(f"make_perks: {dest} ({len(EDITS)} edits)")


if __name__ == "__main__":
    main()
