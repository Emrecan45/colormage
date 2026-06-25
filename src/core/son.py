import os
import pygame
from core.config import EST_WEB

class Son:
    def __init__(self, chemin):
        base = os.path.basename(chemin)
        if EST_WEB:
            base = base.replace(".wav", ".webaudio").replace(".ogg", ".webaudio")
        self.nom = base
        self.chemin_relatif = "assets/audio/" + self.nom
        self.volume = 1.0
        self.boucle = False
        if EST_WEB:
            import platform
            platform.window.colormage_load_sfx(self.chemin_relatif)
            self.sound = None
        else:
            self.sound = pygame.mixer.Sound(chemin)

    def play(self, loops=0):
        if not EST_WEB:
            self.sound.play(loops)
            return
        if loops == -1:
            self.boucle = True
        else:
            self.boucle = False
        import platform
        import json
        args = json.dumps({"nom": self.chemin_relatif, "volume": float(self.volume), "boucle": self.boucle})
        platform.window.colormage_play_sfx(args)

    def set_volume(self, valeur):
        self.volume = valeur
        if not EST_WEB:
            self.sound.set_volume(valeur)
            return
        if self.boucle:
            import platform
            import json
            args = json.dumps({"nom": self.chemin_relatif, "volume": float(valeur)})
            platform.window.colormage_set_sfx_volume(args)

    def stop(self):
        if not EST_WEB:
            self.sound.stop()
            return
        import platform
        platform.window.colormage_stop_sfx(self.chemin_relatif)
