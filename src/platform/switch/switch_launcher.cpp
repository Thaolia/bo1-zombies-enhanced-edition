// The start menu of the Switch build. Map, aim assist, god mode, the Tab zombie counter, graphics and controllers are
// chosen with the pad on libnx's text console before the engine starts, so a game opens straight on its map without the
// front end. A second view sets up joining a dedicated server instead (docs/SERVER.md): the game then opens on its own
// menu and joins by itself. Another sets a solo game's start kit (points and perks, given by mods/admin). A third
// chooses which button does what in the game (gamepad_remap.h); this menu itself
// keeps reading the console's buttons as they are, so a layout that went wrong can always be fixed here. The choices
// persist in menu.cfg; Start writes launch.cfg and gfx.cfg from them (launcher_config.cpp), which a skip_menu boot
// (emulator, scripted runs) then reuses as they are. The console font is ASCII only: no accents in the text.

// libnx before anything that could pull the Win32 shim (switch_main.cpp explains why).
#include <switch.h>

#include "launcher_config.h"
#include "../lan_browser.h"
#include "switch_launcher.h"
#include "switch_net.h"

#include <sys/iosupport.h>
#include <sys/stat.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

extern "C" void Switch_BootLogWrite(const char *text);
extern "C" int Switch_BatteryPercent();

namespace
{
const char *const kMenuConfigPath = "sdmc:/switch/bo1zm/menu.cfg";
const char *const kLaunchConfigPath = "sdmc:/switch/bo1zm/launch.cfg";
const char *const kGfxConfigPath = "sdmc:/switch/bo1zm/gfx.cfg";
const char *const kLaunchExtraPath = "sdmc:/switch/bo1zm/launch_extra.cfg";

// Through the boot log's one writer only: stdout belongs to the console while the menu is up, and a printf would land
// on the screen over the menu.
void Log(const char *fmt, ...)
{
    static const char kPrefix[] = "[launcher] ";
    char text[600];
    std::memcpy(text, kPrefix, sizeof(kPrefix) - 1);
    va_list ap;
    va_start(ap, fmt);
    const int n = std::vsnprintf(text + sizeof(kPrefix) - 1, sizeof(text) - sizeof(kPrefix), fmt, ap);
    va_end(ap);
    size_t len = sizeof(kPrefix) - 1 + (n < 0 ? 0 : size_t(n));
    if (len > sizeof(text) - 2)
        len = sizeof(text) - 2;
    text[len] = '\n';
    text[len + 1] = '\0';
    Switch_BootLogWrite(text);
}

std::string ReadText(const char *path, size_t maxBytes)
{
    std::string text;
    if (FILE *f = std::fopen(path, "rb"))
    {
        text.resize(maxBytes);
        text.resize(std::fread(&text[0], 1, maxBytes, f));
        std::fclose(f);
    }
    return text;
}

// A map is offered when the files it needs beside the game's own are on the SD card (Launcher_MapFile: the player's
// own extraction of another game, which the Switch package holds only when make_dist.sh had one).
bool MapAvailable(int map)
{
    for (int i = 0; i < Launcher_MapFileCount(map); ++i)
    {
        struct stat st;
        if (stat(("sdmc:/switch/bo1zm/" + Launcher_MapFile(map, i)).c_str(), &st) != 0)
            return false;
    }
    return true;
}

bool WriteText(const char *path, const std::string &text)
{
    FILE *f = std::fopen(path, "wb");
    if (!f)
        return false;
    const bool ok = std::fwrite(text.data(), 1, text.size(), f) == text.size();
    return std::fclose(f) == 0 && ok;
}

// launch_extra.cfg as one line: its line breaks become spaces, runs of blanks one space.
std::string ReadExtraArgs()
{
    const std::string raw = ReadText(kLaunchExtraPath, 512);
    std::string out;
    for (char c : raw)
    {
        const bool blank = c == ' ' || c == '\t' || c == '\r' || c == '\n';
        if (!blank)
            out += c;
        else if (!out.empty() && out.back() != ' ')
            out += ' ';
    }
    if (!out.empty() && out.back() == ' ')
        out.pop_back();
    return out;
}

enum View
{
    VIEW_MAIN,
    VIEW_SERVER,
    VIEW_PAD,
    VIEW_KIT,
};

enum Item
{
    // Main view.
    ITEM_SERVER,
    ITEM_MAP,
    ITEM_AIMASSIST,
    ITEM_AIM_SLOWDOWN,
    ITEM_AIM_LOCKON,
    ITEM_AIM_AUTOAIM,
    ITEM_RUNINFO,
    ITEM_GOD,
    ITEM_TABINFO,
    ITEM_KIT,
    ITEM_BACKEND,
    ITEM_RESOLUTION,
    ITEM_FSR,
    ITEM_UPSCALE_OUTPUT,
    ITEM_FSR_SHARPNESS,
    ITEM_MAXFPS,
    ITEM_SHADOWS,
    ITEM_PROPDIST,
    ITEM_TEXFILTER,
    ITEM_FPSCOUNTER,
    ITEM_PAD,
    ITEM_CONTROLLERS,
    ITEM_START,
    // Server view.
    ITEM_NET_ENABLE,
    ITEM_NET_HOST,
    ITEM_NET_PORT,
    ITEM_NET_PASS,
    ITEM_NET_NAME,
    ITEM_NET_DETECT,
    ITEM_NET_BO2W,
    ITEM_NET_DUAL,
    ITEM_NET_LANAUTO,
    ITEM_NET_SCAN,
    ITEM_NET_FOUND_FIRST,
    ITEM_NET_FOUND_LAST = ITEM_NET_FOUND_FIRST + 5,
    ITEM_NET_BACK,
    // Pad view: one line per game control (Bo1PadControl order), then reset and back.
    ITEM_PAD_FIRST,
    ITEM_PAD_LAST = ITEM_PAD_FIRST + BO1_PAD_COUNT - 1,
    ITEM_PAD_RESET,
    ITEM_PAD_BACK,
    // Start kit view: the points, one line per perk (kLauncherPerks order), back.
    ITEM_KIT_POINTS,
    ITEM_KIT_POWER,
    ITEM_KIT_PAP,
    ITEM_KIT_PERK_FIRST,
    ITEM_KIT_PERK_LAST = ITEM_KIT_PERK_FIRST + 7,
    ITEM_KIT_FAR,
    ITEM_KIT_DUAL,
    ITEM_KIT_HIT,
    ITEM_KIT_UPAP,
    ITEM_KIT_SPAWN,
    ITEM_KIT_RUSH,
    ITEM_KIT_BACK,
    ITEM_COUNT
};

bool PadControlItem(int item)
{
    return item >= ITEM_PAD_FIRST && item <= ITEM_PAD_LAST;
}

bool KitPerkItem(int item)
{
    return item >= ITEM_KIT_PERK_FIRST && item <= ITEM_KIT_PERK_LAST;
}

struct ItemInfo
{
    View view;
    int row;
    const char *label; // null on a pad control line: Launcher_PadActionLabel names it
    const char *help;
};

// Console rows (1-based, 45 of them at 1280x720).
const ItemInfo kItems[ITEM_COUNT] = {
    {VIEW_MAIN, 6, "Server", "A: join a dedicated server (address, port, name). Left/Right: on or off."},
    {VIEW_MAIN, 8, "Map", "The map the game starts on directly, without the game's menu."},
    {VIEW_MAIN, 10, "Aim assist", "Controller aim assist on zombies."},
    {VIEW_MAIN, 11, "  Slowdown", "Aiming slows down while the crosshair is over a zombie."},
    {VIEW_MAIN, 12, "  Lock-on", "Aiming follows the zombie you aim at."},
    {VIEW_MAIN, 13, "  Auto aim", "When aiming (ZL), the crosshair snaps to the nearest zombie."},
    {VIEW_MAIN, 14, "Speedrun info", "Settings and hashes of the program and zones: while loading, or in game too."},
    {VIEW_MAIN, 15, "God mode", "Zombies cannot kill the player (solo game)."},
    {VIEW_MAIN, 16, "Zombie counter", "Zombies alive and left in the round, beside the scoreboard."},
    {VIEW_MAIN, 17, "Start kit", "A: points, perks and mods of a solo game (hit marker, unlimited PaP...)."},
    {VIEW_MAIN, 19, "Renderer", "deko3d: the fastest. OpenGL: the older path, slower."},
    {VIEW_MAIN, 20, "Resolution", "720p: the screen's own. 540p, 480p: softer image, more FPS (online)."},
    {VIEW_MAIN, 21, "  Upscaling", "FSR 1.0: frame by frame. ASR: accumulates frames, sharper, costlier."},
    {VIEW_MAIN, 22, "  Output", "Size of the upscaled image. 1080p: for the TV (dock); the screen is 720p."},
    {VIEW_MAIN, 23, "  Sharpness", "Sharpening of the image FSR 1.0 upscales. Maximum: the sharpest."},
    {VIEW_MAIN, 24, "FPS limit", "30: steadier and easier on the battery. 60: smoother."},
    {VIEW_MAIN, 25, "Shadows", "Dynamic shadows. Turning them off gains FPS."},
    {VIEW_MAIN, 26, "Prop distance", "Scenery objects drawn less far and simpler: more FPS (TranZit)."},
    {VIEW_MAIN, 27, "Texture filter", "Sharpness of distant textures. 16x: the sharpest. Bilinear: the lightest."},
    {VIEW_MAIN, 28, "FPS counter", "FPS and battery counter in the top right corner."},
    {VIEW_MAIN, 29, "Button mapping", "A: choose the button of each game action (fire, aim, jump...)."},
    {VIEW_MAIN, 30, "Controllers", "A: the Switch's screen to connect or change controllers."},
    {VIEW_MAIN, 39, "START", "Starts the game with these settings (also: + button)."},
    {VIEW_SERVER, 7, "Connection", "On: the game joins this server instead of a solo game."},
    {VIEW_SERVER, 8, "IP address", "A: the IP address of the PC that runs the server (Server.bat, Server.sh)."},
    {VIEW_SERVER, 9, "Port", "A: the server's UDP port, 3074 by default."},
    {VIEW_SERVER, 10, "Password", "A: the server's player password (g_password), empty if it has none."},
    {VIEW_SERVER, 11, "Player name", "A: your name on the server (letters, digits, _ - .), empty: the game's."},
    {VIEW_SERVER, 12, "Auto mods", "Yes: on start, asks the server for its mods and map, and loads them."},
    {VIEW_SERVER, 13, "BO2 weapons", "Yes: your Black Ops II weapons (mods/bo2weapons), if the server says nothing."},
    {VIEW_SERVER, 14, "Dual wield", "Yes: the dual-wield weapons (mods/dualwield), if the server says nothing."},
    {VIEW_SERVER, 16, "Auto search", "Yes: searches the local network for servers when this screen opens."},
    {VIEW_SERVER, 17, "Search now", "A: searches the local network for servers (one second)."},
#define NET_FOUND(row) {VIEW_SERVER, row, nullptr, "A: join this server (address and port filled in, connection on)."}
    NET_FOUND(18), NET_FOUND(19), NET_FOUND(20), NET_FOUND(21), NET_FOUND(22), NET_FOUND(23),
#undef NET_FOUND
    {VIEW_SERVER, 24, "BACK", "Back to the menu (also: B button)."},
#define PAD_LINE(row) {VIEW_PAD, row, nullptr, "Left/Right: choose the button. The action that had it takes the old one."}
    PAD_LINE(6),  PAD_LINE(7),  PAD_LINE(8),  PAD_LINE(9),  PAD_LINE(10), PAD_LINE(11), PAD_LINE(12), PAD_LINE(13),
    PAD_LINE(14), PAD_LINE(15), PAD_LINE(16), PAD_LINE(17), PAD_LINE(18), PAD_LINE(19), PAD_LINE(20), PAD_LINE(21),
#undef PAD_LINE
    {VIEW_PAD, 23, "Reset", "A: puts back the game's original buttons."},
    {VIEW_PAD, 25, "BACK", "Back to the menu (also: B button)."},
    {VIEW_KIT, 6, "Start points", "Left/Right: the points on arrival on the map, instead of the game's 500."},
    {VIEW_KIT, 7, "Power", "Yes: the map's power is on from the start (doors, perks, Pack-a-Punch)."},
    {VIEW_KIT, 8, "Pack-a-Punch", "Yes: a Pack-a-Punch, always on, at the players' start point."},
#define KIT_PERK(row) {VIEW_KIT, row, nullptr, "Left/Right or A: a free perk on arrival, if the map has its machine."}
    KIT_PERK(9), KIT_PERK(10), KIT_PERK(11), KIT_PERK(12), KIT_PERK(13), KIT_PERK(14), KIT_PERK(15), KIT_PERK(16),
#undef KIT_PERK
    {VIEW_KIT, 17, "Far zombies", "Left/Right: a zombie this far from everyone and unseen is replaced."},
    {VIEW_KIT, 18, "Dual wield", "Yes: Pack-a-Punch gives two Ray Guns, Thunderguns, PPSh (mods/dualwield)."},
    {VIEW_KIT, 19, "Hit marker", "Yes: an X in the middle of the screen on each zombie hit (mods/hitmarker)."},
    {VIEW_KIT, 20, "Unlimited Pack-a-Punch", "Yes: endless repacks, price and damage doubled each time (mods/unlimitedpap)."},
    {VIEW_KIT, 21, "Zombie spawn rate", "Left/Right: zombies come out faster, short breaks (mods/spawnrate)."},
    {VIEW_KIT, 22, "  Sprint to barriers", "Yes: each zombie runs to its barrier, then goes back to its own speed."},
    {VIEW_KIT, 23, "BACK", "Back to the menu (also: B button)."},
};
static_assert(ITEM_KIT_PERK_LAST - ITEM_KIT_PERK_FIRST + 1 == 8, "one kit line per kLauncherPerks entry");
static_assert(sizeof(kItems) / sizeof(kItems[0]) == ITEM_COUNT, "one kItems line per Item");
const int kGraphicsHeaderRow = 18;
const int kControllerFirstRow = 31; // below Controllers (row 30)
const int kControllerMaxRows = 8; // handheld + players 1-7: the rows up to START
const int kPadInfoRow = 28;
const int kNetInfoRow = 26;
const int kKitInfoRow = 25;
// The console is 80 x 45: a help or status line holds 78 characters from column 3, and the footer ends on row 45.
const int kHelpRow = 40;
const int kStatusRow = 41;
const int kAsrWarnRow = 42;
const int kFooterRow = 43;

// The last LAN search's servers (lan_browser.h), and whether one ran since the server view opened.
std::vector<LanServer> s_found;
bool s_searched;

bool FoundItem(int item)
{
    return item >= ITEM_NET_FOUND_FIRST && item <= ITEM_NET_FOUND_LAST;
}

bool Selectable(const LauncherSettings &s, View view, int item)
{
    if (kItems[item].view != view)
        return false;
    if (item == ITEM_AIM_SLOWDOWN || item == ITEM_AIM_LOCKON || item == ITEM_AIM_AUTOAIM)
        return s.aimAssist;
    // A dedicated server picks the map and decides god mode, the zombie counter and its players' start.
    if (item == ITEM_MAP || item == ITEM_GOD || item == ITEM_TABINFO || item == ITEM_KIT)
        return !s.join;
    if (FoundItem(item))
        return size_t(item - ITEM_NET_FOUND_FIRST) < s_found.size();
    if (item == ITEM_NET_BO2W)
        return s.bo2WeaponsInstalled;
    if (item == ITEM_NET_DUAL || item == ITEM_KIT_DUAL)
        return s.dualWieldInstalled;
    if (item == ITEM_KIT_UPAP)
        return s.unlimitedPapInstalled;
    if (item == ITEM_KIT_RUSH)
        return s.spawnRate > 0;
    // The upscalers take a frame below 720p to the output size: nothing to do at 720p.
    if (item == ITEM_FSR)
        return s.height < 720;
    if (item == ITEM_UPSCALE_OUTPUT)
        return s.height < 720 && s.upscaler > 0;
    // ASR runs without its sharpening pass on the Switch (gb_deko3d.cpp): the stops only drive FSR 1.0's RCAS.
    if (item == ITEM_FSR_SHARPNESS)
        return s.height < 720 && s.upscaler > 0 && !Launcher_UpscalerIsAsr(s.upscaler);
    return true;
}

// Lines whose value comes from the console's keyboard (A), not from left/right.
bool TypedItem(int item)
{
    return item == ITEM_NET_HOST || item == ITEM_NET_PORT || item == ITEM_NET_PASS || item == ITEM_NET_NAME;
}

// Lines A acts on without a value to change.
bool ActionItem(int item)
{
    return item == ITEM_CONTROLLERS || item == ITEM_START || item == ITEM_NET_BACK || item == ITEM_PAD ||
           item == ITEM_PAD_RESET || item == ITEM_PAD_BACK || item == ITEM_KIT || item == ITEM_KIT_BACK ||
           item == ITEM_NET_SCAN || FoundItem(item);
}

const char *ItemLabel(int item)
{
    if (FoundItem(item))
        return "";
    if (KitPerkItem(item))
        return kLauncherPerks[item - ITEM_KIT_PERK_FIRST].label;
    return PadControlItem(item) ? Launcher_PadActionLabel(item - ITEM_PAD_FIRST) : kItems[item].label;
}

// An item's value starts on column 33 (column 3, then "> ", a 24-column label and "[A] "): 48 columns are left on
// the 80-column console, and a longer value wraps onto the next row.
const size_t kValueWidth = 48;

std::string Clip(const std::string &text, size_t width)
{
    return text.size() <= width ? text : text.substr(0, width - 3) + "...";
}

// Joins the parts that fit in kValueWidth and counts the others ("+3").
std::string JoinFitting(const std::vector<std::string> &parts)
{
    std::string text;
    for (size_t i = 0; i < parts.size(); ++i)
    {
        const std::string next = text.empty() ? parts[i] : text + ", " + parts[i];
        const size_t rest = parts.size() - i - 1;
        const size_t room = rest ? kValueWidth - (" +" + std::to_string(rest)).size() : kValueWidth;
        if (next.size() > room)
            return text.empty() ? Clip(next, kValueWidth) : text + " +" + std::to_string(parts.size() - i);
        text = next;
    }
    return text;
}

const char *YesNo(bool v)
{
    return v ? "Yes" : "No";
}

std::string ValueText(const LauncherSettings &s, int item)
{
    switch (item)
    {
    case ITEM_SERVER:
        if (!s.join)
            return "Off (solo game)";
        return s.serverHost.empty() ? "On, address to enter" : "On: " + Launcher_ServerAddress(s);
    case ITEM_MAP:
        return kLauncherMaps[s.map].label;
    case ITEM_AIMASSIST:
        return s.aimAssist ? "On" : "Off";
    case ITEM_AIM_SLOWDOWN:
        return YesNo(s.aimSlowdown);
    case ITEM_AIM_LOCKON:
        return YesNo(s.aimLockon);
    case ITEM_AIM_AUTOAIM:
        return YesNo(s.aimAutoaim);
    case ITEM_GOD:
        return YesNo(s.god);
    case ITEM_TABINFO:
        return YesNo(s.tabInfo);
    case ITEM_KIT:
    {
        int perks = 0;
        for (int i = 0; i < kLauncherPerkCount; ++i)
            perks += (s.startPerks >> i) & 1;
        std::vector<std::string> parts;
        if (!s.startPoints && !perks && !s.startPower && !s.startPap && !s.farRespawn)
            parts.push_back("The game's");
        else
        {
            parts.push_back(s.startPoints ? std::to_string(s.startPoints) + " points" : "500 points");
            if (perks)
                parts.push_back(std::to_string(perks) + (perks > 1 ? " perks" : " perk"));
            if (s.startPower)
                parts.push_back("power");
            if (s.startPap)
                parts.push_back("Pack-a-Punch");
            if (s.farRespawn > 0)
                parts.push_back("far respawn");
        }
        if (s.dualWield && s.dualWieldInstalled)
            parts.push_back("dual wield");
        if (s.hitmarker)
            parts.push_back("hit marker");
        if (s.unlimitedPap && s.unlimitedPapInstalled)
            parts.push_back("unlimited PaP");
        if (s.spawnRate > 0)
            parts.push_back("zombies x" + std::to_string(s.spawnRate));
        return JoinFitting(parts);
    }
    case ITEM_KIT_POINTS:
        return s.startPoints ? std::to_string(s.startPoints) : "The game's (500)";
    case ITEM_BACKEND:
        return s.backend == LAUNCHER_BACKEND_DEKO3D ? "deko3d" : "OpenGL";
    case ITEM_KIT_POWER:
        return YesNo(s.startPower);
    case ITEM_KIT_PAP:
        return YesNo(s.startPap);
    case ITEM_KIT_FAR:
        return s.farRespawn > 0 ? "Beyond " + std::to_string(s.farRespawn) : std::string("No");
    case ITEM_RESOLUTION:
        return s.height == 480 ? "480p" : s.height == 540 ? "540p" : "720p";
    case ITEM_FSR:
        return s.height < 720 ? kLauncherUpscalers[s.upscaler].label : "Not needed at 720p";
    case ITEM_UPSCALE_OUTPUT:
        return s.output == 1080 ? "1080p (dock)" : "720p";
    case ITEM_FSR_SHARPNESS:
        return kLauncherFsrSharpness[s.fsrSharpness].label;
    case ITEM_MAXFPS:
        return std::to_string(s.maxFps);
    case ITEM_SHADOWS:
        return YesNo(s.shadows);
    case ITEM_PROPDIST:
        return kLauncherPropDistances[s.propDistance].label;
    case ITEM_TEXFILTER:
        return Launcher_TexFilterLabel(s.texFilter);
    case ITEM_FPSCOUNTER:
        return YesNo(s.fpsCounter);
    case ITEM_RUNINFO:
        return s.runInfo == 0 ? "No" : s.runInfo == 1 ? "While loading" : "Loading + in game";
    case ITEM_NET_ENABLE:
        return s.join ? "On" : "Off";
    case ITEM_NET_LANAUTO:
        return YesNo(s.lanAuto);
    case ITEM_NET_DETECT:
        return YesNo(s.joinDetectMods);
    case ITEM_NET_BO2W:
        return s.bo2WeaponsInstalled ? YesNo(s.joinBo2Weapons) : "not on the SD card";
    case ITEM_NET_DUAL:
        return s.dualWieldInstalled ? YesNo(s.joinDualWield) : "not on the SD card";
    case ITEM_KIT_DUAL:
        return s.dualWieldInstalled ? YesNo(s.dualWield) : "not on the SD card";
    case ITEM_KIT_HIT:
        return YesNo(s.hitmarker);
    case ITEM_KIT_UPAP:
        return s.unlimitedPapInstalled ? YesNo(s.unlimitedPap) : "script not on the SD card";
    case ITEM_KIT_SPAWN:
        return s.spawnRate > 0 ? std::to_string(s.spawnRate) + " times faster" : std::string("The game's");
    case ITEM_KIT_RUSH:
        return YesNo(s.spawnRush);
    case ITEM_NET_SCAN:
        if (!s_searched)
            return "not run yet";
        return s_found.empty() ? "no server found"
                               : std::to_string(s_found.size()) + (s_found.size() > 1 ? " servers found" : " server found");
    case ITEM_NET_HOST:
        return s.serverHost.empty() ? "(to enter)" : s.serverHost;
    case ITEM_NET_PORT:
        return std::to_string(s.serverPort);
    case ITEM_NET_PASS:
        return s.serverPassword.empty() ? "(none)" : std::string(s.serverPassword.size(), '*');
    case ITEM_NET_NAME:
        return s.playerName.empty() ? "(the game's)" : s.playerName;
    case ITEM_PAD:
        return Bo1_PadRemapIsIdentity(s.pad) ? "The game's" : "Custom";
    case ITEM_PAD_RESET:
        return Bo1_PadRemapIsIdentity(s.pad) ? "already the game's buttons" : "the game's original buttons";
    default:
        if (PadControlItem(item))
            return Launcher_PadButtonLabel(s.pad.source[item - ITEM_PAD_FIRST]);
        if (KitPerkItem(item))
            return YesNo((s.startPerks >> (item - ITEM_KIT_PERK_FIRST)) & 1);
        return "";
    }
}

// Left/right (dir -1/+1) and A (+1) on a value line.
void Change(LauncherSettings *s, int item, int dir)
{
    switch (item)
    {
    case ITEM_SERVER:
    case ITEM_NET_ENABLE:
        s->join = !s->join;
        break;
    case ITEM_NET_LANAUTO:
        s->lanAuto = !s->lanAuto;
        break;
    case ITEM_NET_DETECT:
        s->joinDetectMods = !s->joinDetectMods;
        break;
    case ITEM_NET_BO2W:
        s->joinBo2Weapons = !s->joinBo2Weapons;
        break;
    case ITEM_NET_DUAL:
        s->joinDualWield = !s->joinDualWield;
        break;
    case ITEM_KIT_DUAL:
        s->dualWield = !s->dualWield;
        break;
    case ITEM_KIT_HIT:
        s->hitmarker = !s->hitmarker;
        break;
    case ITEM_KIT_UPAP:
        s->unlimitedPap = !s->unlimitedPap;
        break;
    case ITEM_KIT_RUSH:
        s->spawnRush = !s->spawnRush;
        break;
    case ITEM_KIT_SPAWN:
    {
        int at = 0;
        while (at < kLauncherSpawnRateCount && kLauncherSpawnRates[at] != s->spawnRate)
            ++at;
        at = (at % kLauncherSpawnRateCount + dir + kLauncherSpawnRateCount) % kLauncherSpawnRateCount;
        s->spawnRate = kLauncherSpawnRates[at];
        break;
    }
    case ITEM_MAP:
        do
            s->map = (s->map + dir + kLauncherMapCount) % kLauncherMapCount;
        while (!MapAvailable(s->map));
        break;
    case ITEM_AIMASSIST:
        s->aimAssist = !s->aimAssist;
        break;
    case ITEM_AIM_SLOWDOWN:
        s->aimSlowdown = !s->aimSlowdown;
        break;
    case ITEM_AIM_LOCKON:
        s->aimLockon = !s->aimLockon;
        break;
    case ITEM_AIM_AUTOAIM:
        s->aimAutoaim = !s->aimAutoaim;
        break;
    case ITEM_GOD:
        s->god = !s->god;
        break;
    case ITEM_TABINFO:
        s->tabInfo = !s->tabInfo;
        break;
    case ITEM_BACKEND:
        s->backend = s->backend == LAUNCHER_BACKEND_DEKO3D ? LAUNCHER_BACKEND_GL : LAUNCHER_BACKEND_DEKO3D;
        break;
    case ITEM_KIT_POWER:
        s->startPower = !s->startPower;
        break;
    case ITEM_KIT_PAP:
        s->startPap = !s->startPap;
        break;
    case ITEM_RESOLUTION:
    {
        static const int kHeights[] = {720, 540, 480};
        int at = 0;
        while (at < 2 && kHeights[at] != s->height)
            ++at;
        s->height = kHeights[(at + dir + 3) % 3];
        break;
    }
    case ITEM_FSR:
        s->upscaler = (s->upscaler + dir + kLauncherUpscalerCount) % kLauncherUpscalerCount;
        break;
    case ITEM_UPSCALE_OUTPUT:
        s->output = s->output == 1080 ? 720 : 1080;
        break;
    case ITEM_FSR_SHARPNESS:
        s->fsrSharpness = (s->fsrSharpness + dir + kLauncherFsrSharpnessCount) % kLauncherFsrSharpnessCount;
        break;
    case ITEM_MAXFPS:
        s->maxFps = s->maxFps == 60 ? 30 : 60;
        break;
    case ITEM_SHADOWS:
        s->shadows = !s->shadows;
        break;
    case ITEM_PROPDIST:
        s->propDistance = (s->propDistance + dir + kLauncherPropDistanceCount) % kLauncherPropDistanceCount;
        break;
    case ITEM_TEXFILTER:
        s->texFilter = LauncherTexFilter((s->texFilter + dir + LAUNCHER_TEXFILTER_COUNT) % LAUNCHER_TEXFILTER_COUNT);
        break;
    case ITEM_FPSCOUNTER:
        s->fpsCounter = !s->fpsCounter;
        break;
    case ITEM_RUNINFO:
        s->runInfo = (s->runInfo + dir + 3) % 3;
        break;
    case ITEM_KIT_FAR:
    {
        int at = 0;
        while (at < kLauncherFarRespawnCount && kLauncherFarRespawns[at] != s->farRespawn)
            ++at;
        at = (at % kLauncherFarRespawnCount + dir + kLauncherFarRespawnCount) % kLauncherFarRespawnCount;
        s->farRespawn = kLauncherFarRespawns[at];
        break;
    }
    case ITEM_KIT_POINTS:
    {
        int at = 0;
        while (at < kLauncherStartPointCount && kLauncherStartPoints[at] != s->startPoints)
            ++at;
        at = (at % kLauncherStartPointCount + dir + kLauncherStartPointCount) % kLauncherStartPointCount;
        s->startPoints = kLauncherStartPoints[at];
        break;
    }
    default:
        if (KitPerkItem(item))
            s->startPerks ^= 1u << (item - ITEM_KIT_PERK_FIRST);
        if (PadControlItem(item))
        {
            const int control = item - ITEM_PAD_FIRST;
            const int physical = (s->pad.source[control] + dir + BO1_PAD_COUNT) % BO1_PAD_COUNT;
            Bo1_PadRemapAssign(&s->pad, control, physical);
        }
        break;
    }
}

int Step(const LauncherSettings &s, View view, int item, int dir)
{
    do
        item = (item + dir + ITEM_COUNT) % ITEM_COUNT;
    while (!Selectable(s, view, item));
    return item;
}

const char *StyleName(u32 style)
{
    if (style & HidNpadStyleTag_NpadHandheld)
        return "Joy-Con attached to the console";
    if (style & HidNpadStyleTag_NpadFullKey)
        return "Pro Controller";
    if (style & HidNpadStyleTag_NpadJoyDual)
        return "Pair of Joy-Con";
    if (style & HidNpadStyleTag_NpadJoyLeft)
        return "Left Joy-Con alone";
    if (style & HidNpadStyleTag_NpadJoyRight)
        return "Right Joy-Con alone";
    if (style & HidNpadStyleTag_NpadGc)
        return "GameCube controller";
    return "Other controller";
}

// One line per connected controller, "" when none: the menu redraws when it changes.
std::string ControllerList()
{
    static const HidNpadIdType kIds[] = {HidNpadIdType_Handheld, HidNpadIdType_No1, HidNpadIdType_No2,
                                         HidNpadIdType_No3,      HidNpadIdType_No4, HidNpadIdType_No5,
                                         HidNpadIdType_No6,      HidNpadIdType_No7, HidNpadIdType_No8};
    std::string list;
    for (HidNpadIdType id : kIds)
    {
        const u32 style = hidGetNpadStyleSet(id);
        if (!style)
            continue;
        char line[96];
        if (id == HidNpadIdType_Handheld)
            std::snprintf(line, sizeof(line), "Handheld: %s\n", StyleName(style));
        else
            std::snprintf(line, sizeof(line), "Player %d: %s\n", int(id) + 1, StyleName(style));
        list += line;
    }
    return list;
}

void LogControllers(const std::string &list)
{
    std::string oneLine = list.empty() ? "none" : list;
    for (char &c : oneLine)
        if (c == '\n')
            c = ';';
    Log("controllers: %s", oneLine.c_str());
}

// The console's controller screen: solo game, so one player, handheld allowed (single mode). The ForSystem call,
// because the game's own ShowControllerSupport only shows its screen when the connected pads fall short of the
// request: with the Joy-Cons attached it returned at once (0x5d59, LibAppletBadExit) and the screen never appeared.
// flag false: the game's screen, not the HOME menu's.
void ShowControllerApplet()
{
    HidLaControllerSupportArg arg;
    hidLaCreateControllerSupportArg(&arg);
    arg.hdr.enable_single_mode = 1;
    HidLaControllerSupportResultInfo info = {};
    const Result rc = hidLaShowControllerSupportForSystem(&info, &arg, false);
    Log("controller applet -> 0x%x, players %d, selected id %u", rc, int(info.player_count), info.selected_id);
}

// The console's keyboard applet, which takes the screen and gives it back as the controller screen does. True with the
// typed text in *text; false, *text unchanged, when the player cancelled it (B) or it failed.
bool AskText(int item, std::string *text)
{
    SwkbdConfig kbd;
    Result rc = swkbdCreate(&kbd, 0);
    if (R_FAILED(rc))
    {
        Log("swkbdCreate -> 0x%x", rc);
        return false;
    }
    swkbdConfigMakePresetDefault(&kbd);
    if (item == ITEM_NET_HOST)
    {
        // Digits, with '.' on the key beside 0.
        swkbdConfigSetType(&kbd, SwkbdType_NumPad);
        swkbdConfigSetLeftOptionalSymbolKey(&kbd, ".");
        swkbdConfigSetHeaderText(&kbd, "Server IP address");
        swkbdConfigSetGuideText(&kbd, "192.168.1.20");
        swkbdConfigSetStringLenMax(&kbd, 63);
    }
    else if (item == ITEM_NET_PORT)
    {
        swkbdConfigSetType(&kbd, SwkbdType_NumPad);
        swkbdConfigSetHeaderText(&kbd, "Server port");
        swkbdConfigSetGuideText(&kbd, "3074");
        swkbdConfigSetStringLenMax(&kbd, 5);
    }
    else if (item == ITEM_NET_PASS)
    {
        swkbdConfigSetKeySetDisableBitmask(&kbd, SwkbdKeyDisableBitmask_Space);
        swkbdConfigSetHeaderText(&kbd, "Server password");
        swkbdConfigSetGuideText(&kbd, "empty: none");
        swkbdConfigSetStringLenMax(&kbd, 31);
    }
    else
    {
        swkbdConfigSetKeySetDisableBitmask(&kbd, SwkbdKeyDisableBitmask_Space);
        swkbdConfigSetHeaderText(&kbd, "Player name");
        swkbdConfigSetStringLenMax(&kbd, 15);
    }
    swkbdConfigSetInitialText(&kbd, text->c_str());
    char out[64] = "";
    rc = swkbdShow(&kbd, out, sizeof(out));
    swkbdClose(&kbd);
    Log("keyboard (%s) -> 0x%x \"%s\"", kItems[item].label, rc,
        item == ITEM_NET_PASS ? "(password)" : R_SUCCEEDED(rc) ? out : "");
    if (R_FAILED(rc))
        return false;
    *text = out;
    return true;
}

// A on a keyboard line: takes the typed value, or says why it was refused ("" when taken or cancelled).
std::string EditTyped(LauncherSettings *s, int item)
{
    std::string typed = item == ITEM_NET_HOST   ? s->serverHost
                        : item == ITEM_NET_PORT ? std::to_string(s->serverPort)
                        : item == ITEM_NET_PASS ? s->serverPassword
                                                : s->playerName;
    if (!AskText(item, &typed))
        return "";
    if (item == ITEM_NET_HOST)
    {
        if (!typed.empty() && !Launcher_ValidServerHost(typed))
            return "Address refused: digits and dots only, for example 192.168.1.20.";
        s->serverHost = typed;
    }
    else if (item == ITEM_NET_PORT)
    {
        if (!Launcher_ParsePort(typed, &s->serverPort))
            return "Port refused: a number from 1 to 65535.";
    }
    else if (item == ITEM_NET_PASS)
    {
        if (!typed.empty() && !Launcher_ValidPassword(typed))
            return "Password refused: 31 characters at most, no space, quote, ; or +.";
        s->serverPassword = typed;
    }
    else
    {
        if (!typed.empty() && !Launcher_ValidPlayerName(typed))
            return "Name refused: 1 to 15 letters, digits, _ - . and no space.";
        s->playerName = typed;
    }
    return "";
}

void At(int row, int col)
{
    std::printf("\x1b[%d;%dH", row, col);
}

// Bright black is the console's grey, for lines that do not apply.
const char *const kColorNormal = "\x1b[0m";
const char *const kColorSelected = "\x1b[33;1m";
const char *const kColorDisabled = "\x1b[30;1m";
const char *const kColorTitle = "\x1b[36;1m";
const char *const kColorWarn = "\x1b[31;1m";

struct Screen
{
    const char *buildStamp;
    int battery;
    std::string controllers;
    std::string network; // the console's address, or "none"
    bool networkUp;
    std::string status; // why the last Start or keyboard entry was refused, until the next change
};

void DrawItem(const LauncherSettings &s, View view, int item, int selected)
{
    const ItemInfo &info = kItems[item];
    const bool isSelected = item == selected;
    At(info.row, 3);
    if (item == ITEM_START || item == ITEM_NET_BACK || item == ITEM_PAD_BACK || item == ITEM_KIT_BACK)
    {
        std::printf("%s%s[ %s ]%s", isSelected ? "> " : "  ", isSelected ? "\x1b[30;43m" : kColorSelected, info.label,
                    kColorNormal);
        return;
    }
    const char *color = isSelected ? kColorSelected : (Selectable(s, view, item) ? kColorNormal : kColorDisabled);
    if (FoundItem(item))
    {
        const size_t index = size_t(item - ITEM_NET_FOUND_FIRST);
        if (index < s_found.size())
        {
            const LanServer &f = s_found[index];
            std::string where = f.address + ":" + std::to_string(f.port);
            std::string count = std::to_string(f.players) + (f.maxPlayers > 0 ? "/" + std::to_string(f.maxPlayers) : "");
            std::printf("%s%s %-21s %-22.22s %-16.16s %s%s", color, isSelected ? ">" : " ", where.c_str(),
                        f.hostname.c_str(), f.map.c_str(), count.c_str(), kColorNormal);
        }
        return;
    }
    std::printf("%s%s %-24s", color, isSelected ? ">" : " ", ItemLabel(item));
    if (item == ITEM_CONTROLLERS)
        std::printf("[A] controller screen%s", kColorNormal);
    else if (item == ITEM_SERVER || item == ITEM_PAD || item == ITEM_PAD_RESET || item == ITEM_KIT || TypedItem(item) ||
             item == ITEM_NET_SCAN)
        std::printf("[A] %s%s", Clip(ValueText(s, item), kValueWidth).c_str(), kColorNormal);
    else if (PadControlItem(item))
    {
        // The game's own button beside a changed one, so a custom layout reads at a glance.
        const int control = item - ITEM_PAD_FIRST;
        std::printf("<  %-7s >", ValueText(s, item).c_str());
        if (s.pad.source[control] != control)
            std::printf("   %s(game: %s)", kColorDisabled, Launcher_PadButtonLabel(control));
        std::printf("%s", kColorNormal);
    }
    else
        std::printf("<  %s  >%s", Clip(ValueText(s, item), kValueWidth - 2).c_str(), kColorNormal);
}

void Draw(const LauncherSettings &s, View view, int selected, const Screen &screen)
{
    std::printf("\x1b[2J");
    At(2, 3);
    const char *title = view == VIEW_MAIN     ? "LAUNCHER"
                        : view == VIEW_SERVER ? "JOIN A SERVER"
                        : view == VIEW_KIT    ? "START KIT (POINTS AND PERKS)"
                                              : "BUTTON MAPPING";
    std::printf("%sBLACK OPS ZOMBIES - %s%s", kColorTitle, title, kColorNormal);
    if (screen.battery >= 0)
    {
        At(2, 64);
        std::printf("Battery %3d%%", screen.battery);
    }
    At(3, 3);
    std::printf("%sbuild %s%s", kColorDisabled, screen.buildStamp, kColorNormal);
    At(4, 3);
    std::printf("----------------------------------------------------------------------------");

    for (int item = 0; item < ITEM_COUNT; ++item)
        if (kItems[item].view == view)
            DrawItem(s, view, item, selected);

    if (view == VIEW_MAIN)
    {
        At(kGraphicsHeaderRow, 3);
        std::printf("%sGraphics%s", kColorTitle, kColorNormal);
        if (screen.controllers.empty())
        {
            At(kControllerFirstRow, 7);
            std::printf("%sNo controller detected%s", kColorWarn, kColorNormal);
        }
        else
        {
            int row = kControllerFirstRow;
            size_t pos = 0;
            while (pos < screen.controllers.size() && row < kControllerFirstRow + kControllerMaxRows)
            {
                const size_t end = screen.controllers.find('\n', pos);
                At(row++, 7);
                std::printf("%s", screen.controllers.substr(pos, end - pos).c_str());
                pos = end + 1;
            }
        }
    }
    else if (view == VIEW_PAD)
    {
        At(kPadInfoRow, 3);
        std::printf("%sOn the left the game's action, on the right the Switch button for it.%s", kColorTitle,
                    kColorNormal);
        At(kPadInfoRow + 1, 5);
        std::printf("The game's menus follow it too: confirm = Jump, back = Crouch.");
        At(kPadInfoRow + 2, 5);
        std::printf("This launcher keeps the console's buttons: a mistake is fixed here.");
        At(kPadInfoRow + 3, 5);
        std::printf("The sticks (movement, camera) do not change.");
    }
    else if (view == VIEW_KIT)
    {
        At(kKitInfoRow, 3);
        std::printf("%sGiven in every solo game, on arrival on the map (admin mod).%s", kColorTitle, kColorNormal);
        At(kKitInfoRow + 1, 5);
        std::printf("A perk is given only if the map has its machine:");
        At(kKitInfoRow + 2, 5);
        std::printf("Kino and Five only have Juggernog, Quick Revive, Speed Cola and Double Tap.");
        At(kKitInfoRow + 3, 5);
        std::printf("On a server, the server decides.");
    }
    else
    {
        At(kNetInfoRow, 3);
        std::printf("%sConsole network%s", kColorTitle, kColorNormal);
        At(kNetInfoRow + 1, 5);
        if (screen.networkUp)
            std::printf("Connected, IP address %s", screen.network.c_str());
        else
            std::printf("%sNo network: turn Wi-Fi on (airplane mode off).%s", kColorWarn, kColorNormal);
        At(kNetInfoRow + 3, 3);
        std::printf("%sOn start%s", kColorTitle, kColorNormal);
        At(kNetInfoRow + 4, 5);
        if (!s.join)
            std::printf("Solo game on %s (connection off).", kLauncherMaps[s.map].label);
        else if (s.serverHost.empty())
            std::printf("%sServer address to enter.%s", kColorWarn, kColorNormal);
        else
        {
            std::printf("The game's menu opens, then joins %s.", Launcher_ServerAddress(s).c_str());
            At(kNetInfoRow + 5, 5);
            std::printf("It retries by itself if the server is not up yet or restarts.");
        }
        At(kNetInfoRow + 7, 3);
        std::printf("%sThe server picks the map, its mods and god mode.%s", kColorDisabled, kColorNormal);
        At(kNetInfoRow + 8, 3);
        std::printf("%sAuto mods: the game loads the same mods and imported map as the server.%s", kColorDisabled,
                    kColorNormal);
    }

    // Measured on the console at Kino, ASR performance from 480p to 720p: 30 fps with the GPU at 768 MHz (the dock's
    // clock), 20 fps at 537 MHz; its accumulate pass runs per output pixel, 2.25 times as many at 1080p.
    if (view == VIEW_MAIN && s.height < 720 && Launcher_UpscalerIsAsr(s.upscaler))
    {
        At(kAsrWarnRow, 3);
        if (s.output == 1080)
            std::printf("%sASR to 1080p: will not hold 30 fps, even docked. Prefer 720p.%s", kColorWarn,
                        kColorNormal);
        else
            std::printf("%sASR: 30 fps with the GPU at 768 MHz (dock). Handheld: 20 fps or less.%s", kColorWarn,
                        kColorNormal);
    }
    At(kHelpRow, 3);
    std::printf("%s", kItems[selected].help);
    if (!screen.status.empty())
    {
        At(kStatusRow, 3);
        std::printf("%s%s%s", kColorWarn, screen.status.c_str(), kColorNormal);
    }
    At(kFooterRow, 3);
    std::printf("----------------------------------------------------------------------------");
    At(kFooterRow + 1, 3);
    if (view == VIEW_MAIN)
        std::printf("Up/Down: select  Left/Right: change  A: confirm  +: play  -: quit");
    else if (view == VIEW_KIT)
        std::printf("Up/Down: select  Left/Right: change  A: confirm  B: back  +: play  -: quit");
    else if (view == VIEW_PAD)
        std::printf("Up/Down: select  Left/Right: button  A: confirm  B: back  +: play  -: quit");
    else
        std::printf("Up/Down: select  A: change  B: back  +: play  -: quit");
    At(kFooterRow + 2, 3);
    std::printf("%sSettings: sdmc:/switch/bo1zm/menu.cfg   (skip_menu file: no menu)%s", kColorDisabled,
                kColorNormal);
    consoleUpdate(nullptr);
}

// Held directions repeat after 350 ms, every 120 ms, so the map list scrolls without one press per entry.
struct Repeat
{
    u64 heldSince = 0;
    u64 lastFire = 0;

    bool Fire(bool down, bool held, u64 now)
    {
        if (down)
        {
            heldSince = lastFire = now;
            return true;
        }
        if (!held)
            return false;
        if (armTicksToNs(now - heldSince) >= 350000000ull && armTicksToNs(now - lastFire) >= 120000000ull)
        {
            lastFire = now;
            return true;
        }
        return false;
    }
};

// Why Start cannot go yet, or "".
std::string StartRefusal(const LauncherSettings &s, bool networkUp)
{
    if (s.join && s.serverHost.empty())
        return "Enter the server's address (Server, A) or turn the connection off.";
    if (s.join && !networkUp)
        return "No network: turn Wi-Fi on (airplane mode off) or play solo.";
    return "";
}
// Start's question to the server (getmodinfo, lan_browser.h): what its clients load. Fills serverModsKnown and
// serverModArgs; returns why Start cannot go ("" when it can). No answer (an older server, or a host name, which the
// query does not resolve): the manual choices, as ZmClient does.
std::string DetectServerMods(LauncherSettings *s)
{
    s->serverModsKnown = false;
    s->serverModArgs.clear();
    if (!s->join || !s->joinDetectMods)
        return "";
    ServerModInfo info;
    if (!LanBrowser_QueryModInfo(s->serverHost, s->serverPort, s->serverPassword, 1500, &info))
    {
        Log("server mods: no answer from %s, the manual choices", Launcher_ServerAddress(*s).c_str());
        return "";
    }
    if (info.refused)
    {
        Log("server mods: %s refused the password", Launcher_ServerAddress(*s).c_str());
        return "Password refused by the server (Password, A).";
    }
    s->serverModsKnown = true;
    s->serverModArgs = LanBrowser_ModInfoArgs(info);
    Log("server mods: %s", s->serverModArgs.empty() ? "none" : s->serverModArgs.c_str());
    for (const std::string &file : Launcher_ServerModFiles(info.fsMods, info.zones, info.bspWorld))
    {
        struct stat st;
        if (stat(("sdmc:/switch/bo1zm/" + file).c_str(), &st) != 0)
        {
            Log("server mods: %s is not on the SD card", file.c_str());
            return "Not on the SD card: " + file + " (server).";
        }
    }
    return "";
}
} // namespace

LauncherResult Launcher_Run(const char *buildStamp, char *line, size_t lineSize, char *backend, size_t backendSize)
{
    LauncherSettings s = Launcher_ParseSettings(ReadText(kMenuConfigPath, 4096));
    if (!MapAvailable(s.map))
    {
        Log("menu.cfg map %s: its files are not on the SD card, Kino instead", Launcher_MapKey(s.map).c_str());
        s.map = 0;
    }
    struct stat bo2weapons;
    s.bo2WeaponsInstalled = stat("sdmc:/switch/bo1zm/mods/bo2weapons/mod.ff", &bo2weapons) == 0;
    s.dualWieldInstalled = stat("sdmc:/switch/bo1zm/mods/dualwield/mod.ff", &bo2weapons) == 0;
    s.unlimitedPapInstalled =
        stat("sdmc:/switch/bo1zm/mods/unlimitedpap/maps/_zombiemode_perks.gsc", &bo2weapons) == 0;
    Log("menu.cfg read: map %s, backend %s, server %s (%s), BO2 weapons %s, dual wield %s, unlimited PaP %s",
        Launcher_MapKey(s.map).c_str(),
        Launcher_BackendName(s.backend),
        s.serverHost.empty() ? "-" : Launcher_ServerAddress(s).c_str(), s.join ? "join" : "solo",
        !s.bo2WeaponsInstalled ? "not on the SD card" : s.joinBo2Weapons ? "loaded to join" : "off",
        !s.dualWieldInstalled ? "not on the SD card" : s.dualWield ? "solo on" : "solo off",
        !s.unlimitedPapInstalled ? "not on the SD card" : s.unlimitedPap ? "on" : "off");
    Screen screen;
    screen.buildStamp = buildStamp;
    // The first battery query logs through stdout (switch_main.cpp's BootLog), which the console would print over the
    // menu: make it before consoleInit.
    screen.battery = Switch_BatteryPercent();

    const devoptab_t *const stdoutDevice = devoptab_list[STD_OUT];
    const devoptab_t *const stderrDevice = devoptab_list[STD_ERR];
    consoleInit(nullptr);
    padConfigureInput(8, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeAny(&pad);

    View view = VIEW_MAIN;
    int selected = ITEM_START; // the last settings are one press away
    screen.controllers = ControllerList();
    LogControllers(screen.controllers);
    char address[32];
    screen.networkUp = SwitchNet_Address(address, sizeof(address));
    screen.network = address;
    bool dirty = true;
    // The server view's LAN search: about a second, so the screen first says it is searching. Ryujinx 1.1.1375 stops
    // on the first UDP reply (recvfrom, switch-homebrew.md): judge it on the console.
    auto searchLan = [&]() {
        screen.status = "Searching the local network for servers...";
        Draw(s, view, selected, screen);
        unsigned int ip = 0, mask = 0;
        s_searched = true;
        if (!SwitchNet_AddressAndMask(&ip, &mask))
        {
            s_found.clear();
            screen.status = "No network: turn Wi-Fi on (airplane mode off).";
            return;
        }
        s_found = LanBrowser_Scan(LanBrowser_Broadcasts(ip, mask), kLanFirstPort, kLanPortCount, 1000);
        if (s_found.size() > size_t(ITEM_NET_FOUND_LAST - ITEM_NET_FOUND_FIRST + 1))
            s_found.resize(size_t(ITEM_NET_FOUND_LAST - ITEM_NET_FOUND_FIRST + 1));
        screen.status.clear();
        Log("LAN search: %d servers", int(s_found.size()));
        for (const LanServer &f : s_found)
            Log("  %s:%d \"%s\" %s %d/%d players, %d ms", f.address.c_str(), f.port, f.hostname.c_str(), f.map.c_str(),
                f.players, f.maxPlayers, f.pingMs);
        if (FoundItem(selected) && !Selectable(s, view, selected))
            selected = ITEM_NET_SCAN;
    };
    u64 lastPoll = armGetSystemTick();
    Repeat vertical, horizontal;
    LauncherResult result = LAUNCHER_QUIT;

    // appletMainLoop must never be called again once it said false (switch-homebrew.md): leaving the loop on it is
    // final, and main then returns without the engine.
    while (appletMainLoop())
    {
        padUpdate(&pad);
        const u64 down = padGetButtonsDown(&pad);
        const u64 held = padGetButtons(&pad);
        const u64 now = armGetSystemTick();
        bool start = false;

        if (vertical.Fire(down & (HidNpadButton_AnyUp | HidNpadButton_AnyDown),
                          held & (HidNpadButton_AnyUp | HidNpadButton_AnyDown), now))
        {
            selected = Step(s, view, selected, (held & HidNpadButton_AnyUp) ? -1 : 1);
            dirty = true;
        }
        if (horizontal.Fire(down & (HidNpadButton_AnyLeft | HidNpadButton_AnyRight),
                            held & (HidNpadButton_AnyLeft | HidNpadButton_AnyRight), now) &&
            !ActionItem(selected) && !TypedItem(selected))
        {
            Change(&s, selected, (held & HidNpadButton_AnyLeft) ? -1 : 1);
            screen.status.clear();
            dirty = true;
        }
        if (down & HidNpadButton_A)
        {
            screen.status.clear();
            if (selected == ITEM_START)
                start = true;
            else if (selected == ITEM_CONTROLLERS)
            {
                ShowControllerApplet();
                screen.controllers = ControllerList();
                LogControllers(screen.controllers);
            }
            else if (selected == ITEM_SERVER)
            {
                view = VIEW_SERVER;
                selected = s.join ? ITEM_NET_HOST : ITEM_NET_ENABLE;
                if (s.lanAuto)
                    searchLan();
            }
            else if (selected == ITEM_NET_SCAN)
                searchLan();
            else if (FoundItem(selected))
            {
                const LanServer &f = s_found[size_t(selected - ITEM_NET_FOUND_FIRST)];
                s.serverHost = f.address;
                s.serverPort = f.port;
                s.join = true;
                screen.status = "Server chosen: " + Launcher_ServerAddress(s) + " (+ to join).";
                Log("LAN search: %s chosen", Launcher_ServerAddress(s).c_str());
            }
            else if (selected == ITEM_NET_BACK)
            {
                view = VIEW_MAIN;
                selected = ITEM_SERVER;
            }
            else if (selected == ITEM_PAD)
            {
                view = VIEW_PAD;
                selected = ITEM_PAD_FIRST + int(BO1_PAD_RTRIGGER); // Fire, the line players change first
            }
            else if (selected == ITEM_PAD_RESET)
            {
                Bo1_PadRemapIdentity(&s.pad);
                Log("pad layout reset to the game's");
            }
            else if (selected == ITEM_PAD_BACK)
            {
                view = VIEW_MAIN;
                selected = ITEM_PAD;
            }
            else if (selected == ITEM_KIT)
            {
                view = VIEW_KIT;
                selected = ITEM_KIT_POINTS;
            }
            else if (selected == ITEM_KIT_BACK)
            {
                view = VIEW_MAIN;
                selected = ITEM_KIT;
            }
            else if (TypedItem(selected))
                screen.status = EditTyped(&s, selected);
            else
                Change(&s, selected, 1);
            dirty = true;
        }
        if ((down & HidNpadButton_B) && view != VIEW_MAIN)
        {
            screen.status.clear();
            selected = view == VIEW_SERVER ? ITEM_SERVER : view == VIEW_KIT ? ITEM_KIT : ITEM_PAD;
            view = VIEW_MAIN;
            dirty = true;
        }
        if (down & HidNpadButton_Plus)
            start = true;
        if (start)
        {
            screen.status = StartRefusal(s, screen.networkUp);
            if (screen.status.empty() && s.join && s.joinDetectMods)
            {
                screen.status = "Asking the server for its mods...";
                Draw(s, view, selected, screen);
                screen.status = DetectServerMods(&s);
            }
            if (screen.status.empty())
            {
                result = LAUNCHER_START;
                break;
            }
            Log("start refused: %s", screen.status.c_str());
            dirty = true;
        }
        if (down & HidNpadButton_Minus)
        {
            Log("quit from the menu");
            break;
        }

        if (armTicksToNs(now - lastPoll) >= 500000000ull)
        {
            lastPoll = now;
            const std::string list = ControllerList();
            if (list != screen.controllers)
            {
                screen.controllers = list;
                LogControllers(screen.controllers);
                dirty = true;
            }
            const int level = Switch_BatteryPercent();
            if (level != screen.battery)
            {
                screen.battery = level;
                dirty = true;
            }
            const bool up = SwitchNet_Address(address, sizeof(address));
            if (up != screen.networkUp || screen.network != address)
            {
                screen.networkUp = up;
                screen.network = address;
                Log("network: %s", address);
                dirty = true;
            }
        }
        if (dirty)
        {
            Draw(s, view, selected, screen);
            dirty = false;
        }
        else
            consoleUpdate(nullptr); // also paces the loop at the display's rate
    }

    if (!WriteText(kMenuConfigPath, Launcher_FormatSettings(s)))
        Log("could not write %s", kMenuConfigPath);
    if (result == LAUNCHER_START)
    {
        const std::string extra = ReadExtraArgs();
        std::string args = Launcher_BuildLaunchLine(s, extra);
        if (args.size() >= lineSize)
        {
            Log("launch_extra.cfg makes the line too long (%u bytes), started without it", unsigned(args.size()));
            args = Launcher_BuildLaunchLine(s, "");
        }
        std::snprintf(line, lineSize, "%s", args.c_str());
        std::snprintf(backend, backendSize, "%s", Launcher_BackendName(s.backend));
        if (!WriteText(kLaunchConfigPath, args + "\n"))
            Log("could not write %s", kLaunchConfigPath);
        if (!WriteText(kGfxConfigPath, std::string(backend) + "\n"))
            Log("could not write %s", kGfxConfigPath);
        const std::string what =
            s.join ? "the server " + Launcher_ServerAddress(s) : std::string(kLauncherMaps[s.map].label);
        Log("start: %s (extra \"%s\")", what.c_str(), extra.c_str());
        At(kStatusRow, 3);
        std::printf("\x1b[2K%s%s %s...%s", kColorSelected, s.join ? "Joining" : "Loading", what.c_str(),
                    kColorNormal);
        consoleUpdate(nullptr);
    }
    // Frees the console's framebuffer on the default window, which the renderer takes next. consoleExit leaves stdout
    // and stderr on the console, whose next character starts a frame on the closed framebuffer (framebufferBegin read
    // address 0 on Ryujinx at the first BootLog after Start): give them back the devices they had before consoleInit.
    consoleExit(nullptr);
    devoptab_list[STD_OUT] = stdoutDevice;
    devoptab_list[STD_ERR] = stderrDevice;
    return result;
}
