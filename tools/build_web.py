import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
RACINE = TOOLS.parent
STAGING = RACINE / "build" / "ColorMage"
TEMPLATE = TOOLS / "web.tmpl"  # template HTML custom (correctif HiDPI)

FICHIERS_RACINE_WEB = [
    RACINE / "assets" / "video" / "video_intro.mp4",
    RACINE / "assets" / "img" / "ui" / "logo.ico",
]

# Seuls ces elements sont embarques dans le paquet web
A_COPIER = ["main.py", "src", "assets", "levels"]

# Dossiers et extensions exclus du paquet (inutiles sur le web)
DOSSIERS_EXCLUS = {"__pycache__", "video"}
EXTENSIONS_EXCLUES = (".pyc", ".ico")
PREFIXES_EXCLUS = ("placeholder_planet", "screenshot")


def ignorer(dossier, noms):
    """Filtre passe a shutil.copytree pour ne pas copier le superflu."""
    exclus = []
    for nom in noms:
        if nom in DOSSIERS_EXCLUS:
            exclus.append(nom)
        elif nom.lower().endswith(EXTENSIONS_EXCLUES):
            exclus.append(nom)
        elif nom.lower().startswith(PREFIXES_EXCLUS):
            exclus.append(nom)
    return exclus


def stager():
    """Copie le strict necessaire dans un dossier de staging propre."""
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)

    for nom in A_COPIER:
        source = RACINE / nom
        cible = STAGING / nom
        if source.is_dir():
            shutil.copytree(source, cible, ignore=ignorer)
        elif source.exists():
            shutil.copy2(source, cible)
        else:
            print(f"  ! introuvable, ignore : {nom}")

    print(f"Fichiers prepares dans : {STAGING}")


def builder():
    """Lance pygbag sur le dossier de staging."""
    # Options transmises telles quelles a pygbag (--archive, --build, ...)
    options = sys.argv[1:]

    # --disable-sound-format-error : nos bruitages .wav (PCM) sont lus par SDL_mixer
    args = [sys.executable, "-m", "pygbag", "--disable-sound-format-error", "--template", str(TEMPLATE)]
    for option in options:
        args.append(option)
    args.append(str(STAGING / "main.py"))

    print("Lancement de pygbag...\n")

    sert = "--build" not in options and "--archive" not in options
    if sert:
        # serveur bloquant : on copie l'intro des que le dossier web existe
        import threading
        import time

        def copier_quand_pret():
            web = STAGING / "build" / "web"
            for _ in range(180):
                if (web / "index.html").exists():
                    time.sleep(1)
                    ajouter_fichiers_racine(options)
                    print("\nServeur de test : ouvre http://localhost:8000 dans ton navigateur.")
                    return
                time.sleep(1)

        threading.Thread(target=copier_quand_pret, daemon=True).start()
        subprocess.run(args, check=True)
        return

    subprocess.run(args, check=True)
    ajouter_fichiers_racine(options)
    restructurer_landing()

    if "--archive" in options:
        print(f"\nPaquet pret a uploader : {STAGING / 'build' / 'web.zip'}")
    else:
        print(f"\nBuild genere dans : {STAGING / 'build' / 'web'} (landing a la racine, jeu dans /game/)")


def ajouter_fichiers_racine(options):
    """Place l'intro (video + son) a la racine du site, et dans le zip si --archive."""
    web = STAGING / "build" / "web"
    if web.exists():
        for source in FICHIERS_RACINE_WEB:
            if source.exists():
                shutil.copy2(source, web / source.name)
            else:
                print(f"  ! intro introuvable, ignore : {source.name}")

    archive = STAGING / "build" / "web.zip"
    if "--archive" in options and archive.exists():
        with zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED) as zf:
            for source in FICHIERS_RACINE_WEB:
                if source.exists():
                    zf.write(source, source.name)

    web_audio = STAGING / "build" / "web" / "assets" / "audio"
    web_audio.mkdir(parents=True, exist_ok=True)
    audio_src = RACINE / "assets" / "audio"
    if audio_src.exists():
        zf = None
        if "--archive" in options and archive.exists():
            zf = zipfile.ZipFile(archive, "a", zipfile.ZIP_DEFLATED)
            
        for f in audio_src.iterdir():
            if f.suffix in [".wav", ".ogg"]:
                webaudio_name = f.name.replace(".wav", ".webaudio").replace(".ogg", ".webaudio")
                shutil.copy2(f, web_audio / webaudio_name)
                if zf:
                    zf.write(f, f"assets/audio/{webaudio_name}")
        
        if zf:
            zf.close()


IMAGES_LANDING = [
    RACINE / "assets" / "img" / "ui" / "logo.png",
    RACINE / "assets" / "img" / "ui" / "logo.ico",
    RACINE / "assets" / "img" / "screenshot_menu.png",
    RACINE / "assets" / "img" / "screenshot_game.png",
]


def restructurer_landing():
    """Deplace le jeu dans web/game/ et place la landing (meme origine) a la racine."""
    web = STAGING / "build" / "web"
    if not web.exists():
        return

    game = web / "game"
    if game.exists():
        shutil.rmtree(game)
    game.mkdir()
    for item in list(web.iterdir()):
        if item != game:
            shutil.move(str(item), str(game / item.name))

    landing = TOOLS / "landing"
    for source in sorted(landing.iterdir()):
        if source.is_file():
            shutil.copy2(source, web / source.name)

    for source in IMAGES_LANDING:
        if source.exists():
            shutil.copy2(source, web / source.name)
        else:
            print(f"  ! image landing introuvable, ignore : {source.name}")


if __name__ == "__main__":
    stager()
    builder()
