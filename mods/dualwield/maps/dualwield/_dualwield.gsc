// DUALWIELD MOD - not part of the original game. The dual-wield weapons that mods/dualwield/mod.ff holds, taken from
// the retail zones or the "Relaxing Dual Wield" mod by tools/dualwield/dualwield_mod.py, under names of their own:
// - dualwield_pap 1 (default): Pack-a-Punch turns the Ray Gun into two Ray Guns and the Thundergun into two
//   Thunderguns ("Zeus and Hera"), where the map has them;
// - dualwield_ppsh 1 (default): the PPSh-41 joins the box, and Pack-a-Punch makes it two PPSh ("The Grim Reapers")
//   (archive build only).
// Both are read when the map loads. A weapon missing from the loaded zones (no mod.ff) is skipped: the map stays
// retail instead of failing on PrecacheItem.

main_start()
{
	default_dvar( "dualwield_pap", "1" );
	default_dvar( "dualwield_ppsh", "1" );
	level.dualwield_upgrades = [];
	if ( GetDvarInt( "dualwield_pap" ) )
	{
		add_upgrade( "ray_gun_zm", "dw_ray_gun_upgraded_zm" );
		add_upgrade( "thundergun_zm", "dw_thundergun_upgraded_zm" );
	}
	level.dualwield_ppsh = GetDvarInt( "dualwield_ppsh" ) && loaded( "dw_ppsh_zm" ) && loaded( "dw_ppsh_upgraded_zm" );
	if ( level.dualwield_ppsh )
	{
		maps\_zombiemode_weapons::include_zombie_weapon( "dw_ppsh_zm", true );
		maps\_zombiemode_weapons::include_zombie_weapon( "dw_ppsh_upgraded_zm", false );
	}
	if ( !level.dualwield_upgrades.size && !level.dualwield_ppsh )
	{
		LogPrint( "dualwield: nothing to add\n" );
		return;
	}
	// init_weapons() calls level._zombie_custom_add_weapons after the retail list: keep a map's own one
	level._dualwield_map_add = level._zombie_custom_add_weapons;
	level._zombie_custom_add_weapons = ::add_weapons;
	level thread thundergun_on_player_connect();
}

default_dvar( name, value )
{
	if ( GetDvar( name ) == "" )
	{
		SetDvar( name, value );
	}
}

loaded( name )
{
	if ( bo1_mapkit_weaponloaded( name ) )
	{
		return true;
	}
	LogPrint( "dualwield: " + name + " not loaded, skipped\n" );
	return false;
}

add_upgrade( weapon, upgrade )
{
	if ( !loaded( upgrade ) )
	{
		return;
	}
	// PrecacheItem now, while the map loads; the PaP gives the right-hand gun and the engine adds its left twin
	maps\_zombiemode_weapons::include_zombie_weapon( upgrade, false );
	level.dualwield_upgrades[weapon] = upgrade;
}

add_weapons()
{
	if ( IsDefined( level._dualwield_map_add ) )
	{
		[[ level._dualwield_map_add ]]();
	}
	if ( level.dualwield_ppsh )
	{
		maps\_zombiemode_weapons::add_zombie_weapon( "dw_ppsh_zm", "dw_ppsh_upgraded_zm", &"ZOMBIE_WEAPON_DUALWIELD", 1200,
			"smg", "", undefined );
		LogPrint( "dualwield: dw_ppsh_zm in the box\n" );
	}
	// the Pack-a-Punch machine and is_weapon_upgraded() read upgrade_name
	keys = GetArrayKeys( level.dualwield_upgrades );
	for ( i = 0; i < keys.size; i++ )
	{
		if ( !IsDefined( level.zombie_weapons[keys[i]] ) )
		{
			continue;
		}
		level.zombie_weapons[keys[i]].upgrade_name = level.dualwield_upgrades[keys[i]];
		LogPrint( "dualwield: " + keys[i] + " -> " + level.dualwield_upgrades[keys[i]] + "\n" );
	}
}

// maps\_zombiemode_weap_thundergun only knows its own two names: the blast of each shot of the dual Thunderguns
thundergun_on_player_connect()
{
	for ( ;; )
	{
		level waittill( "connecting", player );
		player thread wait_for_thundergun_fired();
	}
}

wait_for_thundergun_fired()
{
	self endon( "disconnect" );
	for ( ;; )
	{
		self waittill( "weapon_fired" );
		if ( self GetCurrentWeapon() != "dw_thundergun_upgraded_zm" || !IsDefined( level._effect["thundergun_smoke_cloud"] ) )
		{
			continue;
		}
		self thread maps\_zombiemode_weap_thundergun::thundergun_fired();
		view_pos = self GetTagOrigin( "tag_flash" ) - self GetPlayerViewHeight();
		view_angles = self GetTagAngles( "tag_flash" );
		PlayFX( level._effect["thundergun_smoke_cloud"], view_pos, AnglesToForward( view_angles ), AnglesToUp( view_angles ) );
	}
}
