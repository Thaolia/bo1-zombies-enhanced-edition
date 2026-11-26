"""French texts of ZmClient (zmadmin/i18n.py): app.py, profile.py, gamecfg.py, gamesetup.py, browser.py, client.py and
dirbrowser.py."""

FR = {
    # app.py
    'The game files are missing: choose your Black Ops install, then "Install".':
        "Les fichiers du jeu manquent : choisissez votre installation de Black Ops et « Installer ».",
    "Help: {title}": "Aide : {title}",
    "profile.json not written: {error}": "profile.json non écrit : {error}",
    "no game folder": "pas de dossier du jeu",
    "ZmAdmin's servers.json not written: {error}": "servers.json de ZmAdmin non écrit : {error}",
    "server mods: no answer (an older version?), manual choices":
        "mods du serveur : pas de réponse (version plus ancienne ?), choix manuels",
    "server mods: {error}, manual choices": "mods du serveur : {error}, choix manuels",
    "server mods: password refused, manual choices": "mods du serveur : mot de passe refusé, choix manuels",
    "none": "aucun",
    "server mods: {mods}, map {world}": "mods du serveur : {mods}, carte {world}",
    "server mods: {mods}": "mods du serveur : {mods}",
    "horde {max}, round {round}": "horde {max}, manche {round}",
    "R restart": "R relance",
    "{n} perks": "{n} atouts",
    "{n} perk": "{n} atout",
    "power": "courant",
    "far zombies brought back > {distance}": "zombies rapprochés > {distance}",
    "BO2 weapons": "armes BO2",
    "BO2 weapons only": "armes BO2 seules",
    "dual wield": "armes doublées",
    "No game folder: put ZmClient next to BO1Zombies.":
        "Pas de dossier du jeu : posez ZmClient à côté de BO1Zombies.",
    "Cannot launch: {missing}. Setup view (F7).": "Impossible de lancer : {missing}. Vue Installation (F7).",
    "The game is already running (PID {pid}).": "Le jeu tourne déjà (PID {pid}).",
    "Cannot launch: {error} ({note})": "Impossible de lancer : {error} ({note})",
    "Cannot launch: {error}": "Impossible de lancer : {error}",
    "Local server not started: {error}": "Serveur local non lancé : {error}",
    "Local server started (PID {pid}) on port {port}.": "Serveur local lancé (PID {pid}) sur le port {port}.",
    "Player 2's window does not start: {error}": "La fenêtre du joueur 2 ne démarre pas : {error}",
    "The game does not start: {error}": "Le jeu ne démarre pas : {error}",
    "joins {host}:{port}; {note}": "rejoint {host}:{port} ; {note}",
    "joins {host}:{port}": "rejoint {host}:{port}",
    "joins the local server ({map})": "rejoint le serveur local ({map})",
    "Split screen started (PID {pid} and {pid2}): {what}.": "Écran partagé lancé (PID {pid} et {pid2}) : {what}.",
    "Game started (PID {pid}): {what}.": "Jeu lancé (PID {pid}) : {what}.",
    "address: an IP or a host name": "adresse : une IP ou un nom de machine",
    "port: a number": "port : un nombre",
    "port: between 1 and 65535": "port : entre 1 et 65535",
    'password: no blank, quote, ";" or "+"': "mot de passe : ni espace, ni guillemet, ni « ; », ni « + »",
    "Server to join": "Serveur à rejoindre",
    "Address": "Adresse",
    "IP or host name": "IP ou nom de la machine",
    "3074 by default": "3074 par défaut",
    "Password": "Mot de passe",
    "the players' one (g_password), empty if none": "celui des joueurs (g_password), vide s'il n'y en a pas",
    "The game is not running.": "Le jeu ne tourne pas.",
    "Force-close both game windows?": "Fermer les deux fenêtres du jeu de force ?",
    "Force-close the game?": "Fermer le jeu de force ?",
    "Stop the game": "Arrêter le jeu",
    "A game in progress is lost; config.cfg is not rewritten.":
        "Une partie en cours est perdue ; config.cfg n'est pas réécrit.",
    "The local server is not running.": "Le serveur local ne tourne pas.",
    "Stop the local server": "Arrêter le serveur local",
    "Stop the local server?": "Arrêter le serveur local ?",
    "Players are disconnected and the game is lost.": "Les joueurs sont déconnectés et la partie est perdue.",
    "Stopping the local server…": "Arrêt du serveur local…",
    "The game has closed.": "Le jeu s'est fermé.",
    "Player 2's window has closed.": "La fenêtre du joueur 2 s'est fermée.",
    "Local server stopped.": "Serveur local arrêté.",
    "The server would not stop: forced stop.": "Le serveur ne s'arrêtait pas : arrêt forcé.",
    "The local server has stopped: {line}": "Le serveur local s'est arrêté : {line}",
    "The local server has stopped.": "Le serveur local s'est arrêté.",
    "Close the game and the local server before installing: they read these files.":
        "Fermez le jeu et le serveur local avant d'installer : ils lisent ces fichiers.",
    'First choose your Black Ops install ("c").': "Choisissez d'abord votre installation de Black Ops (« c »).",
    "Setup started.": "Installation lancée.",
    "Setup: {error}": "Installation : {error}",
    "Setup done, except Vulkan: {warning}": "Installation terminée, sauf Vulkan : {warning}",
    "Setup done: the game can start (F1).": "Installation terminée : le jeu peut démarrer (F1).",
    "Window too small ({w}x{h}): at least {min_w}x{min_h} needed.":
        "Fenêtre trop petite ({w}x{h}) : il faut au moins {min_w}x{min_h}.",
    "[ Help ]": "[ Aide ]",
    "[ Quit ]": "[ Quitter ]",
    "no server chosen": "aucun serveur choisi",
    "● game running (PID {pid})": "● jeu en cours (PID {pid})",
    "● player 2 (PID {pid})": "● joueur 2 (PID {pid})",
    "● local server, port {port}": "● serveur local, port {port}",
    "setup: {phase}…": "installation : {phase}…",
    "Quit ZmClient": "Quitter ZmClient",
    "A setup is in progress.": "Une installation est en cours.",
    "Quitting cancels it (the files already copied stay).": "Quitter l'annule (les fichiers déjà copiés restent).",
    "Quit ZmClient? The game keeps running.": "Quitter ZmClient ? Le jeu continue de tourner.",
    "So does the local server, unless the box below is ticked. ZmClient and ZmAdmin find it again later.":
        "Le serveur local aussi, sauf si la case ci-dessous est cochée. ZmClient et ZmAdmin le retrouvent ensuite.",
    "Also stop the local server": "Arrêter aussi le serveur local",

    # profile.py
    "the line is empty": "la ligne est vide",
    'no "+": the game cuts its command line at each "+"':
        "pas de « + » : le jeu coupe sa ligne de commande à chaque « + »",
    "no quote or line break": "pas de guillemet ni de retour à la ligne",
    'player name: 1 to 15 letters, digits, "_", "-" or "."':
        "nom du joueur : 1 à 15 lettres, chiffres, « _ », « - » ou « . »",
    'player 2\'s name: 1 to 15 letters, digits, "_", "-" or "."':
        "nom du joueur 2 : 1 à 15 lettres, chiffres, « _ », « - » ou « . »",
    "server address missing or invalid (Servers view, F2)": "adresse du serveur absente ou invalide (vue Serveurs, F2)",
    "server port outside 1-65535": "port du serveur hors de 1-65535",
    'server password: no blank, quote, ";" or "+"':
        "mot de passe du serveur : ni espace, ni guillemet, ni « ; », ni « + »",
    "local server port outside 1-65535": "port du serveur local hors de 1-65535",
    "{map} is not installed (no zone {bsp}.ff: your Black Ops lacks this DLC)":
        "{map} n'est pas installée (pas de zone {bsp}.ff : votre Black Ops n'a pas ce DLC)",
    "{map}: {files} missing (your extraction of Black Ops II, docs/BO2_MAPS.md)":
        "{map} : il manque {files} (votre extraction de Black Ops II, docs/BO2_MAPS.md)",
    "Black Ops II weapons: no mods/bo2weapons/mod.ff (to build from your Black Ops II, docs/BO2_WEAPONS.md)":
        "armes de Black Ops II : pas de mods/bo2weapons/mod.ff (à construire depuis votre Black Ops II, "
        "docs/BO2_WEAPONS.md)",
    "the server loads {files}, missing from this folder": "le serveur charge {files}, absent(s) de ce dossier",
    "unlimited Pack-a-Punch: no mods/unlimitedpap/maps/_zombiemode_perks.gsc (to write from your zones: "
    "tools/unlimitedpap/make_perks.py)":
        "Pack-a-Punch illimité : pas de mods/unlimitedpap/maps/_zombiemode_perks.gsc (à écrire depuis vos zones : "
        "tools/unlimitedpap/make_perks.py)",
    'dual-wield weapons: no mods/dualwield/mod.ff (to build from the "Relaxing Dual Wield" mod, '
    "mods/dualwield/README.md)":
        "armes doublées : pas de mods/dualwield/mod.ff (à construire depuis le mod « Relaxing Dual Wield », "
        "mods/dualwield/README.md)",
    "resolution: WIDTHxHEIGHT, e.g. 1280x720": "résolution : LARGEURxHAUTEUR, ex. 1280x720",
    'free dvar "{text}": {why}': "dvar libre « {text} » : {why}",
    'the game folder\'s path holds a "+": the game would cut its command line':
        "le chemin du dossier du jeu contient un « + » : le jeu couperait sa ligne de commande",
    "no split screen": "pas d'écran partagé",
    '{count} "+" commands: the game reads only {max} (remove free dvars)':
        "{count} commandes « + » : le jeu n'en lit que {max} (retirer des dvars libres)",

    # gamecfg.py: SETTINGS labels and help (shown by the Config view), then validate()
    "Mouse sensitivity": "Sensibilité de la souris",
    "Speed of mouse aiming. Default 5.": "Vitesse de la visée à la souris. Défaut 5.",
    "Mouse acceleration": "Accélération de la souris",
    "0: none (default). Higher: a quick move turns further.":
        "0 : aucune (défaut). Plus haut : un geste rapide tourne plus loin.",
    "Controller enabled": "Manette activée",
    "1: the controller plays (XInput). Default 0 on PC.": "1 : la manette joue (XInput). Défaut 0 sur PC.",
    "Controller: invert Y axis": "Manette : axe vertical inversé",
    "1: pushing the stick up makes you look down.": "1 : pousser le stick vers le haut fait baisser le regard.",
    "Controller: rumble": "Manette : vibrations",
    "1: rumble on.": "1 : vibrations activées.",
    "Field of view (FOV)": "Champ de vision (FOV)",
    "0: the game's own (65). 65 to 120: wider. One setting for every mode (also written to players/bo1_shared.cfg, "
    "which the game reads after config.cfg).":
        "0 : celui du jeu (65). 65 à 120 : plus large. Un seul réglage pour tous les modes (aussi écrit dans "
        "players/bo1_shared.cfg, que le jeu lit après config.cfg).",
    "Screen refresh rate": "Fréquence de l'écran",
    'E.g. "60 Hz", "144 Hz" (fullscreen).': "Ex. « 60 Hz », « 144 Hz » (plein écran).",
    "Vertical sync": "Synchronisation verticale",
    "1: no screen tearing, FPS capped at the screen's refresh rate. At the next launch.":
        "1 : pas de déchirure d'image, FPS limités à la fréquence de l'écran. Au prochain lancement.",
    "Maximum FPS": "FPS maximum",
    "0: no limit. Default 85.": "0 : sans limite. Défaut 85.",
    "Brightness (gamma)": "Luminosité (gamma)",
    "Default 0.9; higher: brighter.": "Défaut 0.9 ; plus haut : plus clair.",
    "Anti-aliasing (MSAA)": "Anticrénelage (MSAA)",
    "Samples per pixel; 1: off. At the next launch.":
        "Échantillons par pixel ; 1 : désactivé. Au prochain lancement.",
    "Anisotropic filtering": "Filtrage anisotrope",
    "Sharpness of textures seen at an angle; 16: the best.": "Netteté des textures vues de biais ; 16 : la meilleure.",
    "Texture quality": "Qualité des textures",
    "auto: the game chooses; 0: the best; 3: the lowest (less video memory). Also writes r_picmip_manual, "
    "r_picmip_bump and r_picmip_spec.":
        "auto : le jeu choisit ; 0 : la meilleure ; 3 : la plus basse (moins de mémoire vidéo). Écrit aussi "
        "r_picmip_manual, r_picmip_bump et r_picmip_spec.",
    "Shadows": "Ombres",
    "1: dynamic shadows (heavier).": "1 : ombres dynamiques (plus lourd).",
    "Depth of field": "Profondeur de champ",
    "1: distant objects blur while aiming.": "1 : flou des objets lointains en visant.",
    "Blood": "Sang",
    "1: blood effects.": "1 : effets de sang.",
    "Subtitles": "Sous-titres",
    "1: dialogue subtitles.": "1 : sous-titres des dialogues.",
    "Game's FPS counter": "Compteur FPS du jeu",
    "The game's original counter (the port's counter is in Launch, F4).":
        "Le compteur d'origine du jeu (le compteur du portage est dans Lancement, F4).",
    "Quit game from pause menu": "Quitter le jeu depuis le menu pause",
    '1 (default): "Quit" in the pause menu (Esc, Start) closes the game; 0: back to BO1\'s main menu. A game over '
    "never closes the game.":
        "1 (défaut) : « Quitter » dans le menu pause (Échap, Start) ferme le jeu ; 0 : retour au menu principal de "
        "BO1. Un game over ne ferme jamais le jeu.",
    "no quote": "pas de guillemet",
    "0 or 1": "0 ou 1",
    "a whole number": "un nombre entier",
    "a number": "un nombre",
    "between {low} and {high}": "entre {low} et {high}",
    "one of: {choices}": "une de : {choices}",
    "0, or between 65 and 120": "0, ou entre 65 et 120",

    # gamesetup.py
    "missing: no Vulkan (the game takes its usual renderer)":
        "absent : Vulkan indisponible (le jeu prend le rendu habituel)",
    "older than shaders.pack: to redo (Install)": "plus ancien que shaders.pack : à refaire (Installer)",
    "present (Vulkan)": "présent (Vulkan)",
    "present": "présent",
    "missing": "absent",
    "{n} .iwd files": "{n} fichiers .iwd",
    "no .iwd": "aucun .iwd",
    "{n} files": "{n} fichiers",
    "missing (the cinematics do not play)": "absentes (les cinématiques ne jouent pas)",
    "not converted": "non converties",
    "{n} zones from another ffconv: to convert again": "{n} zones d'un autre ffconv : à reconvertir",
    "{n} zones converted on {when}": "{n} zones converties le {when}",
    "{n} zones (shipped with the package)": "{n} zones (livrées avec le paquet)",
    "missing (comes with the zones)": "absent (vient avec les zones)",
    "missing (comes with the zones); Vulkan only": "absent (vient avec les zones) ; Vulkan seulement",
    "the .iwd files": "les .iwd",
    "the converted zones": "les zones converties",
    "missing {parts}": "manque {parts}",
    "{tool}: {error}": "{tool} : {error}",
    "no conversion on OpenBSD (ffconv is a 32-bit Windows program): convert on a Windows or Linux PC (ZmClient, "
    "Setup view), copy zone/ and shaders.pack here, then untick the conversion (z)":
        "pas de conversion sur OpenBSD (ffconv est un programme Windows 32 bits) : convertissez sur un PC Windows ou "
        "Linux (ZmClient, vue Installation), copiez zone/ et shaders.pack ici, puis décochez la conversion (z)",
    "no {ffconv} in the folder: this package cannot convert the zones":
        "pas de {ffconv} dans le dossier : ce paquet ne sait pas convertir les zones",
    "ffconv is a Windows program: install wine, or convert on a Windows PC (ZmClient, Setup view) and copy zone/ "
    "and shaders.pack here":
        "ffconv est un programme Windows : installez wine, ou convertissez sur un PC Windows (ZmClient, vue "
        "Installation) et copiez zone/ et shaders.pack ici",
    # Setup.phase values
    "preparing": "préparation",
    "copying": "copie",
    "converting zones": "conversion des zones",
    "Vulkan shaders": "shaders Vulkan",
    "putting in place": "mise en place",
    "done": "terminé",
    "failed: {error}": "échec : {error}",
    "{path} is not a Black Ops install (zone/, main/*.iwd, localization.txt)":
        "{path} n'est pas une installation de Black Ops (zone/, main/*.iwd, localization.txt)",
    "the game's folder and the package's are the same": "le dossier du jeu et celui du paquet sont le même",
    "--- setup from {path} ({time}) ---": "--- installation depuis {path} ({time}) ---",
    "not enough room: {need} MB needed, {free} MB free":
        "pas assez de place : {need} Mo nécessaires, {free} Mo libres",
    "{n} files to copy ({size} MB), the others are up to date":
        "{n} fichiers à copier ({size} Mo), les autres sont à jour",
    "cancelled": "annulé",
    "copied {path}": "copié {path}",
    "no shaders.pack (converting the zones makes it): no Vulkan":
        "pas de shaders.pack (convertir les zones le fait) : Vulkan indisponible",
    "no glslang: no Vulkan (Linux: install glslang-tools, OpenBSD: doas pkg_add glslang, then Install again)":
        "pas de glslang : Vulkan indisponible (Linux : installez glslang-tools, OpenBSD : doas pkg_add glslang, puis "
        "Installer à nouveau)",
    "not enough room for shaders.spv ({need} MB, {free} free): no Vulkan":
        "pas assez de place pour shaders.spv ({need} Mo, {free} libres) : Vulkan indisponible",
    "shaders.spv: {glslang}, {n} at a time": "shaders.spv : {glslang}, {n} à la fois",
    "shaders.spv not compiled ({error}): no Vulkan": "shaders.spv non compilé ({error}) : Vulkan indisponible",
    "shaders.spv: {good} shaders, {size} MB, {refused} refused":
        "shaders.spv : {good} shaders, {size} Mo, {refused} refusés",
    "  {shader}: {error}": "  {shader} : {error}",
    "{n} shaders refused by glslang: some objects will be missing under Vulkan":
        "{n} shaders refusés par glslang : des objets manqueront sous Vulkan",
    "ffconv: {command}": "ffconv : {command}",
    "ffconv failed (code {code}): the previous zones are kept; details in {log}":
        "ffconv a échoué (code {code}) : les zones précédentes sont gardées ; détails dans {log}",
    "{n} zones in place": "{n} zones en place",

    # browser.py, client.py
    "address not found ({error})": "adresse introuvable ({error})",
    "no answer": "pas de réponse",
    "the game is already running (PID {pid})": "le jeu tourne déjà (PID {pid})",

    # dirbrowser.py
    "unreadable: {error}": "illisible : {error}",
    "Computer (drives)": "Ordinateur (lecteurs)",
    '{mark} this folder is a Black Ops install: "Choose this folder"':
        "{mark} ce dossier est une installation de Black Ops : « Choisir ce dossier »",
    "Enter the folder that holds BlackOps.exe (zone/, main/).":
        "Entrez dans le dossier qui contient BlackOps.exe (zone/, main/).",
    "(no subfolder)": "(aucun sous-dossier)",
    "..  (parent folder)": "..  (dossier parent)",
    "({first}-{last} of {count})": "({first}-{last} sur {count})",
    "[ Open ]": "[ Ouvrir ]",
    "[ Parent folder ]": "[ Dossier parent ]",
    "[ Choose this folder ]": "[ Choisir ce dossier ]",
    " Enter/→ open  ←/Backspace parent  Space choose  letter: go to  Esc ":
        " Entrée/→ ouvrir  ←/Retour arrière parent  Espace choisir  lettre : aller à  Échap ",
    "choose a folder, not the list of drives": "choisissez un dossier, pas la liste des lecteurs",
}
