import os
from core.config import EST_WEB

MUSIQUES = {
    "main_theme.ogg", "market.ogg",
    "terra.ogg", "pyros.ogg", "aquaris.ogg", "nebula.ogg",
    "cryon.ogg", "solara.ogg", "vortex.ogg", "obscura.ogg",
    "pyros_boss.ogg",
}

volume_courant = 0.5


def existe(chemin):
    """Vrai si la musique est disponible (apk sur bureau, liste servie sur le web)."""
    if EST_WEB:
        return os.path.basename(chemin) in MUSIQUES
    return os.path.exists(chemin)


def jouer(chemin):
    """Joue une musique en boucle. False si absente."""
    if not existe(chemin):
        return False
    if EST_WEB:
        import platform
        base = os.path.basename(chemin).replace(".wav", ".webaudio").replace(".ogg", ".webaudio")
        chemin_relatif = "assets/audio/" + base
        platform.window.colormage_play_music(chemin_relatif)
        return True
    import pygame
    pygame.mixer.music.stop()
    pygame.mixer.music.load(chemin)
    pygame.mixer.music.set_volume(volume_courant)
    pygame.mixer.music.play(-1)
    return True


def stop():
    if EST_WEB:
        import platform
        platform.window.colormage_stop_music()
        return
    import pygame
    pygame.mixer.music.stop()


def set_volume(vol):
    global volume_courant
    volume_courant = vol
    if EST_WEB:
        import platform
        platform.window.colormage_set_music_volume(vol)
        return
    import pygame
    pygame.mixer.music.set_volume(vol)
