"""French texts of ZmClient (zmadmin/i18n.py)."""

FR = {
    # rows, values and editors
    "a whole number": "un nombre entier",
    "between {lo} and {hi}": "entre {lo} et {hi}",
    "({first}-{last} of {total}: Up/Down, wheel)": "({first}-{last} sur {total} : Haut/Bas, molette)",
    "No effect here: {why}": "Sans effet ici : {why}",
    "{label}: no effect here ({why}).": "{label} : sans effet ici ({why}).",
    "yes": "oui",
    "no": "non",
    "WIDTHxHEIGHT, e.g. 1280x720": "LARGEURxHAUTEUR, ex. 1280x720",
    "WIDTHxHEIGHT, e.g. 1920x1080": "LARGEURxHAUTEUR, ex. 1920x1080",
    "game default (500)": "ceux du jeu (500)",
    "beyond {n}": "au-delà de {n}",
    "game default": "celle du jeu",
    "{n} times faster": "{n} fois plus vite",
    '1 to 15 letters, digits, "_", "-" or "."': "1 à 15 lettres, chiffres, « _ », « - » ou « . »",
    "Player name": "Nom du joueur",
    "(from config.cfg)": "(celui de config.cfg)",
    "Name": "Nom",
    "empty: the one in config.cfg": "vide : celui de config.cfg",

    # view titles and key hints (drawn by app.py)
    "Play": "Jouer",
    "Servers": "Serveurs",
    "Launch": "Lancement",
    "Game config": "Config du jeu",
    "Free dvars": "Dvars libres",
    "Setup": "Installation",
    "Log": "Journal",
    "Enter edit  L launch  S stop game  K stop local server  ? help  q quit":
        "Entrée modifier  L lancer  S arrêter le jeu  K arrêter le serveur local  ? aide  q quitter",
    "Enter join  a add  e edit  x remove  f favorite  r refresh  ? help":
        "Entrée rejoindre  a ajouter  e modifier  x retirer  f en favori  r actualiser  ? aide",
    "Enter/Space edit  ? help  q quit": "Entrée/Espace modifier  ? aide  q quitter",
    "Enter edit  Ctrl+S save  u undo  n other dvar  b keys  r reload  ? help":
        "Entrée modifier  Ctrl+S sauvegarder  u annuler  n autre dvar  b touches  r relire  ? aide",
    "a add  e edit  x remove  Space toggle  ? help": "a ajouter  e modifier  x retirer  Espace activer  ? aide",
    "c choose the install  v videos  z zones  s Vulkan shaders  i install  Esc cancel  r refresh  ? help":
        "c choisir l'installation  v vidéos  z zones  s shaders Vulkan  i installer  Échap annuler  r actualiser  "
        "? aide",

    # Play
    "Map and mods are chosen in the Solo view (F3): Enter goes there.":
        "La map et les mods se choisissent dans la vue Solo (F3) : Entrée y va.",
    "Solo view (F3).": "Vue Solo (F3).",
    "(none: Servers view, F2)": "(aucun : vue Serveurs, F2)",
    "Server": "Serveur",
    "Detect the server's mods": "Détecter les mods du serveur",
    "Only when the server does not answer: the server tells what it loads itself (Detect the server's mods).":
        "Sans réponse du serveur seulement : le serveur dit lui-même ce qu'il charge (Détecter les mods).",
    "Black Ops II weapons": "Armes de Black Ops II",
    "no mods/bo2weapons/mod.ff: build it from your Black Ops II":
        "pas de mods/bo2weapons/mod.ff : à construire depuis votre Black Ops II",
    "Local server map": "Map du serveur local",
    "Local server mods": "Mods du serveur local",
    "Local server port": "Port du serveur local",
    "3074 by default": "3074 par défaut",
    "Launch game": "Lancer",
    "Stop game": "Arrêter le jeu",
    "Stop local server": "Arrêter le serveur local",
    "No game folder: ZmClient must sit next to BO1Zombies (a make_dist.sh folder), or be started with --dist.":
        "Pas de dossier du jeu : ZmClient doit être posé à côté de BO1Zombies (un dossier de make_dist.sh), ou lancé "
        "avec --dist.",
    "Game files installed": "Fichiers du jeu installés",
    "Game files: {missing} (Setup view, F7)": "Fichiers du jeu : {missing} (vue Installation, F7)",
    "● Game running (PID {pid})": "● Jeu en cours (PID {pid})",
    "○ Game stopped": "○ Jeu arrêté",
    "● Player 2 window running (PID {pid})": "● Fenêtre du joueur 2 en cours (PID {pid})",
    "● Local server running: PID {pid}, port {port}, {map}":
        "● Serveur local en marche : PID {pid}, port {port}, {map}",
    "! {path} exists: the game adds its content before this command line.":
        "! {path} existe : le jeu ajoute son contenu avant cette ligne de commande.",
    "Command line:": "Ligne de commande :",
    "Player {player} command line:": "Ligne de commande du joueur {player} :",

    # Servers
    "Address": "Adresse",
    "Players": "Joueurs",
    'No server: "a" adds a favorite. Servers on the local network show up by themselves.':
        "Aucun serveur : « a » pour ajouter un favori. Les serveurs du réseau local apparaissent seuls.",
    "searching…": "recherche…",
    "Join": "Rejoindre",
    "Add": "Ajouter",
    "Edit": "Modifier",
    "Remove": "Retirer",
    "Favorite": "En favori",
    "Refresh": "Actualiser",
    "Players: {list}": "Joueurs : {list}",
    "Local network: getstatus broadcast on ports 3074 to 3083, every 3 seconds. An internet server is added by hand; "
    "the client joins it with cl_allowWanConnect 1.":
        "Réseau local : broadcast getstatus sur les ports 3074 à 3083, toutes les 3 secondes. Un serveur sur internet "
        "s'ajoute à la main ; le client le rejoint avec cl_allowWanConnect 1.",
    "Added to favorites.": "Ajouté aux favoris.",
    "Remove {name} from favorites?": "Retirer {name} des favoris ?",
    "Querying servers…": "Interrogation des serveurs…",
    'address: an IP or a host name (letters, digits, ".", "-")':
        "adresse : une IP ou un nom de machine (lettres, chiffres, « . », « - »)",
    "port: {why}": "port : {why}",
    'password: no space, no quote, no ";", no "+"': "mot de passe : ni espace, ni guillemet, ni « ; », ni « + »",
    "Add a favorite": "Ajouter un favori",
    "Edit the favorite": "Modifier le favori",
    "to find it again (empty: the name the server gives)": "pour s'y retrouver (vide : le nom que le serveur donne)",
    "IP or host name, e.g. 192.168.1.20": "IP ou nom de la machine, ex. 192.168.1.20",
    "the server's net_port (3074 by default)": "net_port du serveur (3074 par défaut)",
    "Password": "Mot de passe",
    "the players' one (g_password); empty if there is none": "celui des joueurs (g_password) ; vide s'il n'y en a pas",
    "Saved in profile.json (ZmClient's config folder, readable by you only).":
        "Enregistré dans profile.json (dossier de configuration de ZmClient, lisible par vous seul).",

    # Solo
    "{map}  (not installed)": "{map}  (non installée)",
    "{zone}: no zone in zone/, your Black Ops does not have this DLC":
        "{zone} : pas de zone dans zone/, votre Black Ops n'a pas ce DLC",
    "horde mode is off": "le mode horde est désactivé",
    "not on a Mapkit map (Kino and Five only)": "pas sur une map Mapkit (Kino et Five seulement)",
    "Shangri-La has them already": "Shangri-La les a d'origine",
    "Kino and Five only": "Kino et Five seulement",
    "the mode (F1) is not Solo: these settings are for the next solo game":
        "le mode (F1) n'est pas Solo : ces réglages servent à la prochaine partie solo",
    "Zombie counter (Tab)": "Compteur de zombies (Tab)",
    "No perk machines": "Sans machines à atouts",
    "R restarts after game over": "R relance après la fin",
    "Unlimited Pack-a-Punch": "Pack-a-Punch illimité",
    "no mods/unlimitedpap/maps/_zombiemode_perks.gsc: write it from your zones (tools/unlimitedpap/make_perks.py)":
        "pas de mods/unlimitedpap/maps/_zombiemode_perks.gsc : à écrire depuis vos zones "
        "(tools/unlimitedpap/make_perks.py)",
    "Zombie spawning": "Apparition des zombies",
    "Sprint to the barricades": "Sprint jusqu'aux barricades",
    "zombie spawning: game default": "apparition des zombies : celle du jeu",
    "Game start": "Départ",
    "Starting points": "Points de départ",
    "Power on from the start": "Courant dès le départ",
    "Pack-a-Punch from the start": "Pack-a-Punch au départ",
    "Bring far zombies closer": "Zombies éloignés rapprochés",
    "no perk machines (noperks): nothing to give": "sans machines à atouts (noperks) : rien à donner",
    "Perk: {name}": "Atout : {name}",
    "Horde mode": "Mode horde",
    "Zombies at once": "Zombies en même temps",
    "Number": "Nombre",
    "24 to 1024; above 300 it gets heavy": "24 à 1024 ; au-delà de 300 c'est lourd",
    "Starting round": "Manche de départ",
    "Round": "Manche",
    "1 to 255": "1 à 255",
    "Napalm zombies": "Zombies napalm",
    "Shrieker zombies": "Zombies hurleurs",
    "Spawn from every window": "Sortir de toutes les fenêtres",
    "Unstick the zombies": "Décoincer les zombies",
    "Next round: all dead": "Manche suivante : tous morts",
    "Difficulty": "Difficulté",
    "the original game": "le jeu d'origine",
    "special enemies from several maps from round 1": "ennemis spéciaux de plusieurs maps dès la manche 1",
    "several of each at once": "plusieurs de chaque à la fois",
    "Mod flags:": "Drapeaux des mods :",
    "(no flag)": "(aucun)",
    "no mods/bo2weapons/mod.ff: build it from your Black Ops II (docs/BO2_WEAPONS.md)":
        "pas de mods/bo2weapons/mod.ff : à construire depuis votre Black Ops II (docs/BO2_WEAPONS.md)",
    "Dead Ops Arcade has no box": "Dead Ops Arcade n'a pas de boîte",
    "the local server is already running: it took its mods when it started":
        "le serveur local tourne déjà : il a pris ses mods au lancement",
    'no mods/dualwield/mod.ff: build it from the "Relaxing Dual Wield" mod (mods/dualwield)':
        "pas de mods/dualwield/mod.ff : à construire depuis le mod « Relaxing Dual Wield » (mods/dualwield)",
    "Dual-wield weapons (Pack-a-Punch)": "Armes doublées (Pack-a-Punch)",
    "Split screen (2 players)": "Écran partagé (2 joueurs)",
    "Split screen": "Écran partagé",
    "not in Solo: choose the Local server mode (Play view, F1)":
        "pas en Solo : choisir le mode Serveur local (vue Jouer, F1)",

    # Launch
    "game setting": "réglage du jeu",
    "nothing is added to the command line": "rien n'est ajouté à la ligne de commande",
    "upscaling off": "agrandissement désactivé",
    "supersampling does not need it": "le suréchantillonnage n'en a pas besoin",
    "aim assist is off": "l'aide à la visée est désactivée",
    "split screen places both windows itself": "l'écran partagé place lui-même les deux fenêtres",
    "not in Solo": "pas en Solo",
    "split screen off": "écran partagé désactivé",
    "Language": "Langue",
    "Language of ZmClient. The game itself is not affected.": "Langue de ZmClient. Le jeu lui-même n'est pas concerné.",
    "Display": "Affichage",
    "Resolution": "Résolution",
    "Size": "Taille",
    "Borderless takes the screen's size": "Sans bordure prend la taille de l'écran",
    "Port's FPS counter": "Compteur FPS du portage",
    "Shader warming": "Préchauffage des shaders",
    "Speedrun info": "Infos speedrun",
    "Graphics API": "API graphique",
    "Upscaling": "Agrandissement",
    "with the Vulkan graphics API only": "avec l'API graphique Vulkan seulement",
    "Upscaling method": "Méthode d'agrandissement",
    "Sharpness": "Netteté",
    "Models drawn per frame": "Modèles affichés par image",
    "imported maps (Nuketown): more scenery in the distance": "maps importées (Nuketown) : plus de décor au loin",
    "imported maps: all the scenery; a little heavier": "maps importées : tout le décor ; un peu plus lourd",
    "Split screen: 2 players on this PC": "Écran partagé : 2 joueurs sur ce PC",
    "Layout": "Disposition",
    "Layout of the two windows": "Disposition des deux fenêtres",
    "Player 2 name": "Nom du joueur 2",
    "empty: {name}": "vide : {name}",
    "Player 2 sound": "Son du joueur 2",
    "Controller: aim assist": "Manette : aide à la visée",
    "Aim assist": "Aide à la visée",
    "Slow down on a zombie": "Ralentir sur un zombie",
    "Follow a zombie": "Suivre un zombie",
    "Auto-aim (ADS)": "Visée automatique (ADS)",
    "Auto-aim": "Visée automatique",
    "Local server (Local server mode)": "Serveur local (mode Serveur local)",
    "Game": "Partie",
    "{map}; {mods}": "{map} ; {mods}",
    "rcon password": "Mot de passe rcon",
    "(no folder)": "(aucun dossier)",
    "no game folder": "pas de dossier du jeu",
    'no space, no quote, no ";", no "+"': "ni espace, ni guillemet, ni « ; », ni « + »",
    "Local server rcon password": "Mot de passe rcon du serveur local",
    "shared with ZmAdmin; used at the next start of the server":
        "partagé avec ZmAdmin ; pris en compte au prochain démarrage du serveur",

    # Game config
    "No game folder": "Pas de dossier du jeu",
    "ZmClient is not next to BO1Zombies": "ZmClient n'est pas à côté de BO1Zombies",
    "0 (no)": "0 (non)",
    "1 (yes)": "1 (oui)",
    "(game default)": "(défaut du jeu)",
    "{name}: {help}": "{name} : {help}",
    "Other changes": "Autres modifications",
    'Current value in the file: "{value}".': "Valeur actuelle dans le fichier : « {value} ».",
    "* key {key}": "* touche {key}",
    "(removed)": "(retirée)",
    'Current command: "{command}".': "Commande actuelle : « {command} ».",
    "Save": "Sauvegarder",
    "Undo the changes": "Annuler les modifications",
    "Other dvar": "Autre dvar",
    "Keys": "Touches",
    "Reload": "Relire",
    "(no effect: Borderless)": "(sans effet : Sans bordure)",
    "Resolution (Launch view)": "Résolution (vue Lancement)",
    "The same as the Launch view (F4), given to the game on the command line at every launch: r_mode in Full screen, "
    "r_customMode in Window. Current display: {mode}; in Borderless, the game takes the screen's size. Saved at "
    "once, not in config.cfg.":
        "La même que la vue Lancement (F4), donnée au jeu en ligne de commande à chaque lancement : r_mode en Plein "
        "écran, r_customMode en Fenêtre. Affichage actuel : {mode} ; en Sans bordure, le jeu prend la taille de "
        "l'écran. Enregistrée tout de suite, pas dans config.cfg.",
    "{path} (not created yet: the game writes it when it quits)":
        "{path} (pas encore créé : le jeu l'écrit en quittant)",
    "The game is running: it will rewrite this file when it quits. Quit it before saving.":
        "Le jeu tourne : il réécrira ce fichier en quittant. Quittez-le avant de sauvegarder.",
    "Value": "Valeur",
    "text, without quotes": "texte, sans guillemet",
    'a dvar name: letters, digits, "_"': "un nom de dvar : lettres, chiffres, « _ »",
    "e.g. cg_fov_default, r_aspectRatio": "ex. cg_fov_default, r_aspectRatio",
    'written as: seta name "value"': "écrit en « seta nom \"valeur\" »",
    "{n} dvars in the file. A missing dvar is added.": "{n} dvars dans le fichier. Un dvar absent est ajouté.",
    "no quotes": "pas de guillemet",
    "Key {key}": "Touche {key}",
    "Command": "Commande",
    "e.g. +attack, weapnext; empty: remove the key": "ex. +attack, weapnext ; vide : retirer la touche",
    "(another key…)": "(une autre touche…)",
    "type its name: F1, KP_ENTER, MOUSE4, a…": "taper son nom : F1, KP_ENTER, MOUSE4, a…",
    'a key name: letters, digits, "_"': "un nom de touche : lettres, chiffres, « _ »",
    "New key": "Nouvelle touche",
    "Key": "Touche",
    "its name for the game, e.g. F5, MOUSE4": "son nom pour le jeu, ex. F5, MOUSE4",
    "Nothing to save.": "Rien à sauvegarder.",
    "The game is running: it would rewrite config.cfg when it quits. Quit it, then save.":
        "Le jeu tourne : il réécrirait config.cfg en quittant. Quittez-le, puis sauvegardez.",
    "config.cfg not written: {error}": "config.cfg non écrit : {error}",
    "config.cfg saved ({n} change(s)).": "config.cfg sauvegardé ({n} modification(s)).",
    "Changes undone.": "Modifications annulées.",
    "config.cfg reloaded.": "config.cfg relu.",
    "Reload config.cfg and lose the changes?": "Relire config.cfg et perdre les modifications ?",

    # Free dvars
    "Commands added to the command line, in order, before the map or the connection:":
        "Commandes ajoutées à la ligne de commande, dans l'ordre, avant la map ou la connexion :",
    'None: "a" adds one (e.g. "set bo1_frameperf 200").':
        "Aucune : « a » pour en ajouter une (ex. « set bo1_frameperf 200 »).",
    "Toggle": "Activer/désactiver",
    'Each line becomes "+line". No "+" inside a line: the game cuts its command line at each "+" and keeps only 63 '
    'of them; ZmClient refuses to launch beyond that.':
        "Chaque ligne devient « +ligne ». Pas de « + » dans une ligne : le jeu coupe sa ligne de commande à chaque "
        "« + » et n'en garde que 63 ; ZmClient refuse de lancer au-delà.",
    "Add a command": "Ajouter une commande",
    "Edit the command": "Modifier la commande",
    'without the "+": "set r_fog 0", "set bo1_frameperf 200"':
        "sans le « + » : « set r_fog 0 », « set bo1_frameperf 200 »",
    "(a free command…)": "(une commande libre…)",
    "any command or dvar, typed in full": "n'importe quelle commande ou dvar, tapée en entier",
    'Remove "+{command}"?': "Retirer « +{command} » ?",

    # Setup
    "No game folder: ZmClient must be next to BO1Zombies (or --dist).":
        "Pas de dossier du jeu : ZmClient doit être à côté de BO1Zombies (ou --dist).",
    "Black Ops install:": "Installation de Black Ops :",
    '(none found: "c" to type it)': "(aucune trouvée : « c » pour la taper)",
    "read only, never modified": "lue seulement, jamais modifiée",
    "not an install (zone/, main/*.iwd, localization.txt expected)":
        "pas une installation (zone/, main/*.iwd, localization.txt attendus)",
    "Package folder:": "Dossier du paquet :",
    "zone/ (converted)": "zone/ (converties)",
    "copy the videos (cutscenes, ~1 GB)": "copier les vidéos (cinématiques, ~1 Go)",
    "convert the zones (ffconv, ~6 minutes)": "convertir les zones (ffconv, ~6 minutes)",
    "compile the Vulkan shaders (shaders.spv, 5 to 15 minutes)":
        "compiler les shaders Vulkan (shaders.spv, 5 à 15 minutes)",
    "Cancel the install": "Annuler l'installation",
    "Choose the install": "Choisir l'installation",
    "Install": "Installer",
    "Copy: {done} / {total} MB ({pct}%)": "Copie : {done} / {total} Mo ({pct} %)",
    "Conversion: zone {at} / {count}": "Conversion : zone {at} / {count}",
    "Vulkan shaders: {at} / {count}": "Shaders Vulkan : {at} / {count}",
    "Failed: {error}": "Échec : {error}",
    "Install finished, except Vulkan: {warning}": "Installation terminée, sauf Vulkan : {warning}",
    "Install finished.": "Installation terminée.",
    "not a Black Ops install (zone/, main/*.iwd, localization.txt)":
        "pas une installation de Black Ops (zone/, main/*.iwd, localization.txt)",
    "Black Ops install": "Installation de Black Ops",
    "Folder": "Dossier",
    "the folder that holds BlackOps.exe": "le dossier qui contient BlackOps.exe",
    "Choose the Black Ops folder": "Choisir le dossier de Black Ops",
    "found in a Steam library": "trouvée dans une bibliothèque Steam",
    "(browse the folders…)": "(parcourir les dossiers…)",
    "move through the folders with the arrows": "naviguer dans les dossiers avec les flèches",
    "(type the path…)": "(taper le chemin…)",
    "another folder": "un autre dossier",
    "Cancelling…": "Annulation…",
    "An install is running.": "Une installation est en cours.",

    # Log
    "No game folder: nothing to follow.": "Pas de dossier du jeu : rien à suivre.",
    "Nothing yet: the log shows up when the game writes its console_mp.log.":
        "Rien encore : le journal apparaît quand le jeu écrit son console_mp.log.",
    'filter "{filter}": {n} lines': "filtre « {filter} » : {n} lignes",
    "PAUSED (Space to resume)": "EN PAUSE (Espace pour reprendre)",
    "{n} lines further down (End)": "{n} lignes plus bas (Fin)",
    "Filter": "Filtrer",
    "Resume": "Reprendre",
    "End": "Fin",
}
