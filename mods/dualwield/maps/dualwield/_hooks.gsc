// DUALWIELD MOD - not part of the original game. With +set fs_mods "... dualwield" (mods/_stack/maps/_modstack.gsc):
// the dual-wield weapons of the player's own mod.ff (tools/dualwield/dualwield_mod.py) after Pack-a-Punch.

register()
{
	// maps\_zombiemode::main() runs this hook before maps\_zombiemode_weapons::init() on every zombie map
	maps\_modstack::add( "_zombiemode_ffotd::main_start", maps\dualwield\_dualwield::main_start );
}
