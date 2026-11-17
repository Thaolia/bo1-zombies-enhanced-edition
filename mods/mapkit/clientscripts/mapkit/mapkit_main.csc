#include clientscripts\_utility;
#include clientscripts\_music;
#include clientscripts\_zombiemode_weapons;

// MAPKIT MOD - the client level main of an "empty" layout (the engine loads it instead of clientscripts\<mapname>).
// Retail clientscripts\zombie_pentagon::main without the parts that need Five's world (placed fx, teleporter,
// box screens, office lights, vision volumes, ambient sound emitters).

main()
{
	level._uses_crossbow = true;
	level._power_on = false;
	clientscripts\zombie_pentagon::include_weapons(); // before _zombiemode::main (retail order)
	clientscripts\_zombiemode::main();
	// retail zombie_pentagon_fx::main minus the createfx placements: the zombie fx the shared client scripts use
	// (eye_glow for _zombiemode.csc createZombieEyes, headshot/blood/gib fx for the _callbacks.csc gib callback)
	// and the perk machine fx; without them every zombie spawn is a script error on the client
	clientscripts\zombie_pentagon_fx::precache_util_fx();
	clientscripts\zombie_pentagon_fx::precache_createfx_fx();
	clientscripts\zombie_pentagon_fx::precache_scripted_fx();
	level thread clientscripts\_zombiemode::init_perk_machines_fx();
	clientscripts\_zombiemode_deathcard::init();
	thread waitforclient( 0 );
	clientscripts\zombie_pentagon::register_zombie_types();
	thread mapkit_fx();
}

// The layout's "fx" edits (another game's placed effects, tools/bo2/bo2_createfx.py), played once on each local client as
// BO1's createfx plays its ambient effects: they loop by themselves, with no server entity. The server loaded them
// (_mapkit.gsc mapkit_fx_load). An edit with angles is turned by them (light rays, sparks); the others point up.
// mapkit_fx_placed: how many this client placed; +set mapkit_fx 0 leaves them out.
mapkit_fx()
{
	if ( GetDvar( "mapkit_fx" ) == "0" )
	{
		return;
	}
	waitforclient( 0 );
	ids = [];
	placed = 0;
	players = getlocalplayers();
	for ( i = 0; i < bo1_mapkit_editcount(); i++ )
	{
		if ( i % 500 == 499 )
		{
			wait 0.01; // TranZit has 6 000 edits
		}
		if ( bo1_mapkit_get( i, "kind" ) != "fx" )
		{
			continue;
		}
		name = bo1_mapkit_get( i, "fx" );
		if ( !IsDefined( ids[ name ] ) )
		{
			ids[ name ] = loadfx( name );
		}
		forward = ( 0, 0, 1 );
		up = ( 1, 0, 0 );
		angles = bo1_mapkit_get( i, "angles" );
		if ( IsDefined( angles ) )
		{
			forward = AnglesToForward( angles );
			up = AnglesToUp( angles );
		}
		for ( lc = 0; lc < players.size; lc++ )
		{
			playfx( lc, ids[ name ], bo1_mapkit_get( i, "origin" ), forward, up );
		}
		placed++;
	}
	SetDvar( "mapkit_fx_placed", "" + placed );
}
