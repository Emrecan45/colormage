import pygame
import asyncio
import core.temps as temps
import core.musique as musique
import sys
import os
import gc
import random
import math
from core.config import LARGEUR_ECRAN, HAUTEUR_ECRAN, FPS, TAILLE_CELLULE, HAUTEUR_GRILLE, LARGEUR_GRILLE, resource_path, EST_WEB, est_tactile, set_tactile, VERSION_JEU
from core.son import Son
from core.assets import police, position_centree
from entities.joueur import Joueur
from core.niveau import Niveau
from entities import etapes_prechargement
from ui.popup import Popup
from ui.virtual_gamepad import VirtualGamepad
from ui.pause import Pause
from ui.menu import Menu
from ui.parametres import Parametres
from core.config_manager import ConfigManager
from ui.menu_niveaux import MenuNiveaux
from ui.chronometre import Chronometre
from ui.profil import Profil
from ui.intro import Intro
from ui.alerte import Alerte
import core.i18n as i18n
from core.i18n import t


class TouchesActives:
    """Émule pygame.key.get_pressed() à partir des touches tenues et du gamepad tactile."""
    def __init__(self, actives, virtual_gamepad=None, controls=None):
        self.actives = actives
        self.virtual_gamepad = virtual_gamepad
        self.controls = controls

    def code(self, action):
        """Keycode associé à une action des contrôles, ou None."""
        nom = self.controls.get(action)
        if not nom:
            return None
        try:
            return pygame.key.key_code(nom)
        except (ValueError, TypeError):
            return None

    def __getitem__(self, keycode):
        if keycode in self.actives:
            return True
        gamepad = self.virtual_gamepad
        if gamepad is not None and gamepad.actif and self.controls:
            if gamepad.gauche_presse and keycode == self.code('gauche'):
                return True
            if gamepad.droite_presse and keycode == self.code('droite'):
                return True
            if gamepad.saut_presse and keycode == self.code('sauter'):
                return True
            if gamepad.tir_presse and keycode == self.code('tir'):
                return True
        return False


class Game:
    """Classe principale gérant le jeu"""

    def __init__(self):
        if EST_WEB:
            pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.init()
        pygame.mixer.init()

        # Touches actuellement tenues (suivi via KEYDOWN/KEYUP, utilisé sur le web)
        self.touches_actives = set()

        # Charger la configuration
        self.gestionnaire_config = ConfigManager()
        
        # Initialisation de la langue
        langue_choisie = self.gestionnaire_config.config.get("langue", "en")
        i18n.init(langue_choisie)
        
        # Créer l'écran
        self.plein_ecran = False
        try:
            icone = pygame.image.load(resource_path("assets/img/ui/logo.ico"))
            pygame.display.set_icon(icone)
        except Exception:
            pass
        # Pas de SCALED/RESIZABLE sur le web (ratio et clics corrects)
        if EST_WEB:
            self.ecran = pygame.display.set_mode((LARGEUR_ECRAN, HAUTEUR_ECRAN))
        else:
            self.ecran = pygame.display.set_mode((LARGEUR_ECRAN, HAUTEUR_ECRAN), pygame.SCALED | pygame.RESIZABLE)
        pygame.display.set_caption("ColorMage")


        # Annonce de boss (ex: enrage) affichée temporairement à l'écran
        self.boss_annonce = None
        self.boss_annonce_time = 0


        # Musique de boss
        self.musique_boss_active = False
        self.boss_music_niveau = None
        self.boss_music_existe = False

        # Séquence d'enrage (gèle le jeu, animation de grossissement + texte)
        self.enrage_actif = False
        self.enrage_start = 0
        self.enrage_boss = None
        self.enrage_grow_delay = 1000  # délai avant le début du grossissement (texte d'abord)
        self.enrage_grow_duree = 750   # durée de l'animation de grossissement (ms)
        self.enrage_duree = 2300       # durée totale du gel (ms)

        # Animation de portail au début du niveau
        self.portail_entree_actif = False
        self.portail_entree_animation = 0
        self.joueur_visible = False
        
        # Animation de portail de sortie
        self.portail_sortie_actif = False
        self.portail_sortie_animation = 0
        self.portail_sortie_x = 0
        self.portail_sortie_y = 0
        
        # Pièces collectées pendant le niveau en cours (sauvegardées seulement à la victoire)
        self.pieces_en_cours = []
        # Nombre de pièces gagnées au dernier niveau
        self.pieces_gagnees_niveau = 0
        
        # Animation d'explosion à la mort
        self.charger_frames_explosion()
        self.explosion_actif = False
        self.explosion_frame = 0
        self.explosion_x = 0
        self.explosion_y = 0
        self.explosion_timer = 0
        self.explosion_delai = 60  # ms par frame
        self.explosions_mob = []

        # Timer global pour les animations
        self.temps_global = 0
        
        # Sons pour slimes et pièces
        self.son_hurt = Son(resource_path(os.path.join("assets/audio", "hurt.wav")))
        self.son_slime_saut = Son(resource_path(os.path.join("assets/audio", "slime_saut.wav")))
        self.son_piece = Son(resource_path(os.path.join("assets/audio", "piece.wav")))

        # Son d'explosion
        self.son_explosion = Son(resource_path(os.path.join("assets/audio", "explosion.wav")))
        
        # Sons de pause/unpause
        self.son_pause = Son(resource_path(os.path.join("assets/audio", "pause.wav")))
        self.son_unpause = Son(resource_path(os.path.join("assets/audio", "unpause.wav")))

        # Son d'enragement du boss
        chemin_enrage = resource_path(os.path.join("assets/audio", "pyrolord_enrage.wav"))
        self.son_enrage = Son(chemin_enrage)
        

        # Appliquer le volume des effets sonores depuis les paramètres
        volumes = self.gestionnaire_config.obtenir_volumes()
        vol_effets = volumes.get("effets", 50) / 100
        self.son_hurt.set_volume(vol_effets)
        self.son_slime_saut.set_volume(vol_effets)
        self.son_piece.set_volume(vol_effets)
        self.son_pause.set_volume(vol_effets)
        self.son_unpause.set_volume(vol_effets)
        self.son_explosion.set_volume(vol_effets)
        self.son_enrage.set_volume(vol_effets)

    def preparer_ecran_chargement(self):
        """Prépare les ressources de l'écran de chargement."""
        try:
            logo = pygame.image.load(resource_path("assets/img/ui/logo.png")).convert_alpha()
            larg = 460
            ratio = larg / logo.get_width()
            self.logo_chargement = pygame.transform.smoothscale(logo, (larg, int(logo.get_height() * ratio)))
        except Exception:
            self.logo_chargement = None
        self.etoiles_chargement = []
        for i in range(150):
            self.etoiles_chargement.append([
                random.randint(0, LARGEUR_ECRAN), random.randint(0, HAUTEUR_ECRAN),
                random.randint(1, 3), random.randint(120, 255),
                random.uniform(0.02, 0.08), random.uniform(0, 2 * math.pi),
            ])
        self.font_chargement_pct = police(50)

    def dessiner_ecran_chargement(self, progres, temps):
        """Dessine l'écran de chargement : fond étoilé, logo, barre de progression + %."""
        ecran = self.ecran
        cx = LARGEUR_ECRAN // 2
        ecran.fill((10, 10, 28))

        # Étoiles
        for x, y, taille, brillance_base, vitesse, phase in self.etoiles_chargement:
            b = int(brillance_base * (0.5 + 0.5 * math.sin((temps * 60.0) * vitesse + phase)))
            b = max(50, min(255, b))
            pygame.draw.circle(ecran, (b, b, b), (x, y), taille)

        # Logo
        if self.logo_chargement is not None:
            ecran.blit(self.logo_chargement,
                       (cx - self.logo_chargement.get_width() // 2, HAUTEUR_ECRAN // 2 - 210))

        by = HAUTEUR_ECRAN // 2 + 90

        # Barre de progression
        barre_l, barre_h = 620, 44
        bx = cx - barre_l // 2
        pygame.draw.rect(ecran, (35, 35, 50), (bx, by, barre_l, barre_h), border_radius=8)
        rempli = int(barre_l * max(0.0, min(1.0, progres)))
        if rempli > 0:
            pygame.draw.rect(ecran, (255, 200, 60), (bx, by, rempli, barre_h), border_radius=8)
        pygame.draw.rect(ecran, (255, 255, 255), (bx, by, barre_l, barre_h), 3, border_radius=8)

        # Pourcentage sous la barre
        pct = int(max(0.0, min(1.0, progres)) * 100)
        pct_surf = self.font_chargement_pct.render(f"{pct}%", True, (255, 255, 255))
        ecran.blit(pct_surf, (cx - pct_surf.get_width() // 2, by + barre_h + 16))

    async def executer_prechargement(self, etapes):
        """Exécute les étapes de chargement une par une en affichant la barre de progression."""
        total = len(etapes)
        horloge = pygame.time.Clock()
        progres_affiche = 0.0
        idx = 0
        while idx < total or progres_affiche < 0.999:
            await asyncio.sleep(0)
            for evenement in pygame.event.get():
                if evenement.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                self.gerer_plein_ecran_event(evenement)

            cible = idx / total
            progres_affiche += (cible - progres_affiche) * 0.2
            if cible - progres_affiche < 0.004:
                progres_affiche = cible
            self.dessiner_ecran_chargement(progres_affiche, pygame.time.get_ticks() / 1000.0)
            pygame.display.flip()
            horloge.tick(FPS)

            if idx < total:
                fonction, arguments = etapes[idx]
                fonction(*arguments)
                idx += 1

    def creer_sous_systemes(self):
        """Crée les menus, le niveau, le joueur, etc.."""
        volumes = self.gestionnaire_config.obtenir_volumes()

        # Musique
        volume_musique = volumes.get("musique", 50) / 100
        musique.set_volume(volume_musique)

        self.horloge = pygame.time.Clock()

        # État du jeu
        self.etat = "menu"

        # Niveau
        self.niveau = Niveau(self.gestionnaire_config)

        # Joueur
        self.joueur = Joueur(None, None, self.gestionnaire_config)

        # Menu d'accueil
        self.menu = Menu(self.gestionnaire_config)

        # Pause
        self.pause = Pause(self.gestionnaire_config)
        self.pause.game = self

        # Parametres
        self.parametres = Parametres(self.joueur, self.gestionnaire_config, self.niveau, self)

        # Profil
        self.profil = Profil(self.gestionnaire_config)

        self.menu_niveaux = MenuNiveaux(self.gestionnaire_config)
        self.menu_niveaux.construire_cache_avatars_marche()
        self.niveau_actuel = self.gestionnaire_config.obtenir_niveau_actuel()

        # Chronomètre
        self.chrono = Chronometre()

        self.en_cours = True

        # Popups
        self.popup = Popup(self.gestionnaire_config)
        self.popup_actif = None
        self.est_record = False

        # Contrôles tactiles (mobile/tablette) : invisibles tant qu'aucun toucher
        joystick_fixe = self.gestionnaire_config.config.get("joystick_fixe", False)
        self.virtual_gamepad = VirtualGamepad(fixe=joystick_fixe)

    def charger_frames_explosion(self):
        """Charge les frames du spritesheet d'explosion"""
        chemin = resource_path(os.path.join("assets/img/entities", "explosion.png"))
        spritesheet = pygame.image.load(chemin).convert_alpha()
        frame_w, frame_h = 64, 59
        nb_frames = 9
        taille_affichage = 150
        self.explosion_frames = []
        for i in range(nb_frames):
            frame = spritesheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, frame_h))
            frame = pygame.transform.scale(frame, (taille_affichage, taille_affichage))
            self.explosion_frames.append(frame)

    def demarrer_explosion(self, x_centre, y_centre):
        """Déclenche l'explosion"""
        self.son_explosion.play()
        self.explosion_actif = True
        self.explosion_frame = 0
        self.explosion_timer = temps.obtenir_temps()
        taille = self.explosion_frames[0].get_width()
        self.explosion_x = x_centre - taille // 2
        self.explosion_y = y_centre - taille // 2
        self.joueur_visible = False

    def ajouter_explosion_mob(self, x_centre, y_centre):
        """Ajoute une explosion à l'endroit d'un mob tué par un tir de feu."""
        self.son_explosion.play()
        taille = self.explosion_frames[0].get_width()
        self.explosions_mob.append({
            "frame": 0,
            "x": x_centre - taille // 2,
            "y": y_centre - taille // 2,
            "timer": temps.obtenir_temps(),
        })

    def maj_explosions_mob(self):
        """Fait avancer les animations d'explosion des mobs tués par le feu."""
        maintenant = temps.obtenir_temps()
        for ex in list(self.explosions_mob):
            if maintenant - ex["timer"] >= self.explosion_delai:
                ex["timer"] = maintenant
                ex["frame"] += 1
                if ex["frame"] >= len(self.explosion_frames):
                    self.explosions_mob.remove(ex)

    def gerer_tirs_feu_vs_mobs(self):
        """Les tirs de feu du joueur tuent les mobs."""
        for pf in list(self.niveau.projectiles_joueur):
            if pf.state != "trail" or not pf.collidable:
                continue
            # Démons : 2 PV
            demon_touche = None
            for demon in self.niveau.demons:
                if not demon.en_train_de_mourir and pf.rect.colliderect(demon.rect):
                    demon_touche = demon
                    break
            if demon_touche is not None:
                mort = demon_touche.recevoir_degats()
                pf.alive = False
                if mort:
                    self.son_explosion.play()
                    self.niveau.appliquer_drop(demon_touche)
                else:
                    # le démon encaisse un coup sans mourir
                    self.son_hurt.play()
                continue
            cible = None
            liste_cible = None
            for sorcier in self.niveau.sorciers:
                if pf.rect.colliderect(sorcier.rect):
                    cible, liste_cible = sorcier, self.niveau.sorciers
                    break
            if cible is None:
                for squelette in self.niveau.squelettes:
                    if pf.rect.colliderect(squelette.rect):
                        cible, liste_cible = squelette, self.niveau.squelettes
                        break
            if cible is None:
                for slime in self.niveau.slimes:
                    if not slime.en_train_de_mourir and pf.rect.colliderect(slime.rect):
                        cible, liste_cible = slime, self.niveau.slimes
                        break
            if cible is not None:
                cx, cy = cible.rect.center
                self.niveau.appliquer_drop(cible)
                liste_cible.remove(cible)
                self.ajouter_explosion_mob(cx, cy)
                pf.alive = False
    def maj_volume_effets(self):
        """Met à jour le volume des effets sonores depuis la config"""
        volumes = self.gestionnaire_config.volumes
        vol_effets = volumes.get("effets", 50) / 100
        self.son_hurt.set_volume(vol_effets)
        self.son_slime_saut.set_volume(vol_effets)
        self.son_piece.set_volume(vol_effets)
        self.son_pause.set_volume(vol_effets)
        self.son_unpause.set_volume(vol_effets)
        self.son_explosion.set_volume(vol_effets)
        self.son_enrage.set_volume(vol_effets)
        self.niveau.maj_volume_sons()
        self.joueur.maj_volume_effets()
        self.menu.maj_volume()
        self.menu_niveaux.maj_volume()
        self.profil.maj_volume()
        self.pause.maj_volume()
        self.popup.maj_volume()
        self.alerte.maj_volume()

    def basculer_plein_ecran(self):
        """Bascule entre plein écran et fenêtré (désactivé sur le web)."""
        if EST_WEB:
            return
        self.plein_ecran = not self.plein_ecran
        pygame.display.quit()
        pygame.display.init()
        if self.plein_ecran:
            self.ecran = pygame.display.set_mode((LARGEUR_ECRAN, HAUTEUR_ECRAN), pygame.FULLSCREEN | pygame.SCALED)
        else:
            self.ecran = pygame.display.set_mode((LARGEUR_ECRAN, HAUTEUR_ECRAN), pygame.SCALED | pygame.RESIZABLE)
        pygame.display.set_caption("ColorMage")
        try:
            icone = pygame.image.load(resource_path("assets/img/ui/logo.ico"))
            pygame.display.set_icon(icone)
        except Exception:
            pass

    def gerer_plein_ecran_event(self, evenement):
        """Gère le basculement plein écran (désactivé sur le web)."""
        if EST_WEB:
            return
        if evenement.type == pygame.KEYDOWN:
            if evenement.key == pygame.K_F11:
                self.basculer_plein_ecran()
            elif evenement.key == pygame.K_RETURN and (evenement.mod & pygame.KMOD_ALT):
                self.basculer_plein_ecran()
        elif evenement.type == pygame.WINDOWMAXIMIZED and not self.plein_ecran:
            self.basculer_plein_ecran()

    async def gerer_evenements(self):
        """Gère les événements pygame"""
        for evenement in pygame.event.get():
            if EST_WEB:
                self.virtual_gamepad.gerer_evenement(evenement)
                # Bascule du mode d'entrée selon le dernier input (toucher vs souris/clavier)
                if evenement.type == pygame.FINGERDOWN:
                    set_tactile(True)
                elif evenement.type == pygame.MOUSEBUTTONDOWN and evenement.button == 1:
                    set_tactile(getattr(evenement, "touch", False))
                elif evenement.type == pygame.KEYDOWN:
                    set_tactile(False)
            # Suivi des touches tenues (pour la lecture clavier cohérente sur le web)
            if evenement.type == pygame.KEYDOWN:
                self.touches_actives.add(evenement.key)
            elif evenement.type == pygame.KEYUP:
                self.touches_actives.discard(evenement.key)
            elif evenement.type == pygame.WINDOWFOCUSLOST:
                self.touches_actives.clear()
                self.virtual_gamepad.reset()
            elif evenement.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                self.virtual_gamepad.reset()  # sortie de plein écran

            if evenement.type == pygame.QUIT:
                self.en_cours = False

            # F11 / Alt+Entrée
            self.gerer_plein_ecran_event(evenement)

            if self.popup_actif is not None:
                if evenement.type == pygame.MOUSEBUTTONDOWN and evenement.button == 1:
                    # Gérer les clics selon le type de popup
                    if self.popup_actif == "victoire":
                        action = self.popup.gerer_clic_victoire(evenement.pos, self.niveau_actuel)
                    elif self.popup_actif == "defaite":
                        action = self.popup.gerer_clic_defaite(evenement.pos)
                    else:
                        action = None
                    
                    if action:
                        await self.traiter_action_popup(action)
                        self.popup_actif = None
            else:
                # Gestion globale de la touche Échap
                if evenement.type == pygame.KEYDOWN and evenement.key == pygame.K_ESCAPE:
                    if self.etat == "jeu":
                        # En jeu, Échap met en pause
                        self.maj_volume_effets()
                        self.son_pause.play()
                        self.niveau.regler_ambiances(False)
                        self.chrono.pause()
                        temps.set_pause(True)
                        action = await self.pause.afficher_pause(self.ecran, self.joueur, self.niveau, self.niveau_actuel, self.chrono, draw_background=self.dessiner_fond_niveau, alerte=self.alerte)
                        temps.set_pause(False)
                        
                        # Reprendre le chronomètre
                        if action == "continuer":
                            self.maj_volume_effets()
                            self.son_unpause.play()
                            self.chrono.reprendre()
                        elif action == "recommencer":
                            # Déclencher l'animation de portail d'entrée
                            self.portail_entree_actif = True
                            self.portail_entree_animation = 0
                            self.etat = "jeu"
                            self.joueur_visible = False
                            self.explosion_actif = False
                            self.explosion_frame = 0
                            self.explosion_timer = 0
                            self.popup_actif = None
                            self.son_explosion.stop()
                            self.niveau.reset(self.niveau_actuel, self.ecran)
                            self.joueur.reset(self.niveau)
                            self.joueur.maj_controles()
                            self.joueur.son_spawn.play()
                            self.chrono.demarrer()
                            meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
                            self.chrono.definir_meilleur_temps(meilleur_temps)
                            self.est_record = False
                        elif action == "quitter":
                            self.chrono.arreter()
                            self.menu_niveaux.preparer_retour_niveau(self.niveau_actuel)
                            self.etat = "selection"
                    elif self.etat == "selection":
                        # Marché : Échap revient à l'accueil du marché, puis à la galaxie
                        if self.menu_niveaux.etat_menu == "marche":
                            self.menu_niveaux.son_select.play()
                            if self.menu_niveaux.marche_section is not None:
                                self.menu_niveaux.marche_section = None
                                self.menu_niveaux.achat_en_attente = None
                            else:
                                self.menu_niveaux.quitter_marche()
                                self.menu_niveaux.etat_menu = "galaxie"
                        # Dans la sélection de niveaux, Échap agit comme le bouton retour
                        # Mais bloquer si des animations sont en cours
                        elif self.menu_niveaux.mage_en_mouvement or self.menu_niveaux.teleportation_en_cours or self.menu_niveaux.transition_univers:
                            # Bloquer Échap pendant les animations
                            pass
                        # Si une animation de zoom est en cours, l'annuler
                        elif self.menu_niveaux.zoom_en_cours:
                            # Annuler l'animation et revenir à la galaxie
                            self.menu_niveaux.son_select.play()
                            self.menu_niveaux.zoom_en_cours = False
                            self.menu_niveaux.zoom_animation = 0
                            self.menu_niveaux.etat_menu = "galaxie"
                        elif self.menu_niveaux.etat_menu == "planete":
                            # Retour à la galaxie avec son de téléportation
                            random.choice(self.menu_niveaux.sons_teleport).play()
                            self.menu_niveaux.zoom_en_cours = True
                            self.menu_niveaux.zoom_direction = -1
                        else:
                            # Retour au menu principal
                            self.menu_niveaux.son_select.play()
                            self.etat = "menu"
                    elif self.etat in ["profil", "param"]:
                        # Dans les autres menus, Échap agit comme retour
                        if self.etat == "profil" and self.profil.edition_pseudo:
                            # Si en mode édition du pseudo, Échap annule juste l'édition (géré par profil.py)
                            # Ne pas quitter le profil
                            pass
                        else:
                            # Sinon, Échap quitte le menu avec son de clic
                            if self.etat == "profil":
                                self.profil.son_select.play()
                                self.profil.fermer_clavier()
                            elif self.etat == "param":
                                self.parametres.son_select.play()
                                self.parametres.champ_actif = None
                            self.etat = "menu"
                if self.etat == "menu":
                    if evenement.type == pygame.MOUSEBUTTONDOWN and evenement.button == 1:
                        action = self.menu.gerer_clic(evenement.pos)
                        if action == "jouer":
                            self.menu_niveaux.recharger_donnees()
                            self.etat = "selection"
                        elif action == "grimoire":
                            await self.popup.afficher_grimoire_complet(self.ecran, alerte=self.alerte)
                        elif action == "parametres":
                            self.parametres = Parametres(self.joueur, self.gestionnaire_config, self.niveau, self)
                            self.etat = "param"
                        elif action == "profil":
                            self.profil.recharger_donnees()
                            self.etat = "profil"
                        elif action == "quitter":
                            self.en_cours = False

                elif self.etat == "profil":
                    action = await self.profil.gerer_events(evenement, self.ecran)
                    if action == "quitter":
                        self.etat = "menu"
                    elif action == "reset_save":
                        # Afficher le popup de confirmation
                        confirmation = await self.popup.afficher_popup_confirmation_reset(self.ecran, self.profil, alerte=self.alerte)
                        if confirmation == "confirmer":
                            # Réinitialiser la sauvegarde (uniquement progression)
                            self.gestionnaire_config.reinitialiser_sauvegarde()
                            
                            # Recharger le menu des niveaux avec la nouvelle config
                            self.menu_niveaux = MenuNiveaux(self.gestionnaire_config)
                            self.menu_niveaux.alerte = self.alerte

                            # Recharger le profil (avec l'avatar par défaut)
                            self.profil.recharger_donnees()
                            self.profil.avatar_actuel = 0
                            self.profil.charger_avatar()

                elif self.etat == "param":
                    action = self.parametres.gerer_events(evenement)
                    if action == "quitter":
                        self.etat = "menu"
                    elif action == "demander_reset_param":
                        # Afficher popup de confirmation pour reset paramètres
                        resultat = await self.popup.afficher_popup_confirmation_reset(self.ecran, self.parametres, "parametres", alerte=self.alerte)
                        if resultat == "confirmer":
                            # Reset des paramètres
                            self.gestionnaire_config.reinitialiser_parametres()
                            # Recharger les paramètres
                            self.parametres = Parametres(self.joueur, self.gestionnaire_config, self.niveau, self)
                            # Appliquer le volume de la musique
                            musique.set_volume(0.5)
                            # Mettre à jour les contrôles du joueur
                            self.joueur.maj_controles()
                    elif action == "demander_import":
                        # Afficher popup de confirmation pour import
                        resultat = await self.popup.afficher_popup_confirmation_reset(self.ecran, self.parametres, "import", alerte=self.alerte)
                        if resultat == "confirmer":
                            resultat_import = self.parametres.importer_fichier()
                            if resultat_import == "import_ok":
                                # Redémarrer le jeu
                                pygame.quit()
                                os.execv(sys.executable, [sys.executable] + sys.argv)
                        else:
                            self.parametres.fichier_import_en_attente = None

                elif self.etat == "selection":
                    if evenement.type == pygame.MOUSEBUTTONDOWN and evenement.button == 1:
                        resultat = self.menu_niveaux.gerer_clic(evenement.pos)
                        if resultat == 0:
                            self.etat = "menu"
                        elif resultat == "marche":
                            self.menu_niveaux.etat_menu = "marche"
                        elif resultat is not None and resultat > 0:
                            await self.lancer_niveau(resultat)

                elif self.etat == "jeu":
                    if evenement.type == pygame.KEYDOWN and evenement.key == pygame.K_p:
                        # Mettre en pause le chronomètre
                        self.maj_volume_effets()
                        self.son_pause.play()
                        self.niveau.regler_ambiances(False)
                        self.chrono.pause()
                        temps.set_pause(True)
                        action = await self.pause.afficher_pause(self.ecran, self.joueur, self.niveau, self.niveau_actuel, self.chrono, draw_background=self.dessiner_fond_niveau, alerte=self.alerte)
                        temps.set_pause(False)
                        
                        # Reprendre le chronomètre
                        if action == "continuer":
                            self.maj_volume_effets()
                            self.son_unpause.play()
                            self.chrono.reprendre()
                        elif action == "recommencer":
                            # Déclencher l'animation de portail d'entrée
                            self.portail_entree_actif = True
                            self.portail_entree_animation = 0
                            self.etat = "jeu"
                            self.joueur_visible = False
                            self.explosion_actif = False
                            self.explosion_frame = 0
                            self.explosion_timer = 0
                            self.popup_actif = None
                            self.son_explosion.stop()
                            self.niveau.reset(self.niveau_actuel, self.ecran)
                            self.joueur.reset(self.niveau)
                            self.joueur.maj_controles()
                            self.joueur.son_spawn.play()
                            self.chrono.demarrer()
                            meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
                            self.chrono.definir_meilleur_temps(meilleur_temps)
                            self.est_record = False
                        elif action == "quitter":
                            self.chrono.arreter()
                            self.menu_niveaux.preparer_retour_niveau(self.niveau_actuel)
                            self.etat = "selection"
                    
                    # Gérer le clic sur le bouton pause
                    if evenement.type == pygame.MOUSEBUTTONDOWN and evenement.button == 1:
                        if self.pause.bouton_rect.collidepoint(evenement.pos):
                            # Mettre en pause le chronomètre
                            self.maj_volume_effets()
                            self.son_pause.play()
                            self.niveau.regler_ambiances(False)
                            self.chrono.pause()
                            temps.set_pause(True)
                            action = await self.pause.afficher_pause(self.ecran, self.joueur, self.niveau, self.niveau_actuel, self.chrono, draw_background=self.dessiner_fond_niveau, alerte=self.alerte)
                            temps.set_pause(False)
                            
                            # Reprendre le chronomètre
                            if action == "continuer":
                                self.maj_volume_effets()
                                self.son_unpause.play()
                                self.chrono.reprendre()
                            elif action == "recommencer":
                                # Déclencher l'animation de portail d'entrée
                                self.portail_entree_actif = True
                                self.portail_entree_animation = 0
                                self.etat = "jeu"
                                self.joueur_visible = False
                                self.pieces_en_cours = []
                                self.explosion_actif = False
                                self.explosion_frame = 0
                                self.explosion_timer = 0
                                self.popup_actif = None
                                self.son_explosion.stop()
                                self.niveau.reset(self.niveau_actuel, self.ecran)
                                self.joueur.reset(self.niveau)
                                self.joueur.maj_controles()
                                self.joueur.son_spawn.play()
                                self.chrono.demarrer()
                                meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
                                self.chrono.definir_meilleur_temps(meilleur_temps)
                                self.est_record = False
                            elif action == "quitter":
                                self.chrono.arreter()
                                self.menu_niveaux.preparer_retour_niveau(self.niveau_actuel)
                                self.etat = "selection"

    async def lancer_niveau(self, numero):
        """Lance un niveau avec l'animation de portail"""
        self.virtual_gamepad.reset()
        self.niveau_actuel = numero
        self.pieces_en_cours = []
        self.boss_annonce = None
        self.enrage_actif = False
        self.enrage_boss = None
        self.musique_boss_active = False
        musique.set_volume(self.volume_musique_config())
        self.explosions_mob = []
        self.niveau.reset(numero, self.ecran)
        self.joueur.maj_controles()
        self.niveau.charger_niveau(numero, self.ecran)
        self.joueur.reset(self.niveau)
        self.joueur.maj_controles()
        # Démarrer le chronomètre et charger le meilleur temps
        self.chrono.demarrer()
        meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(numero)
        self.chrono.definir_meilleur_temps(meilleur_temps)
        self.est_record = False
        # Popup page du grimoire (une seule fois par progression)
        if not self.gestionnaire_config.page_vue(numero):
            self.dessiner_fond_niveau(self.ecran)
            self.niveau.dessiner(self.ecran, self.temps_global, update_entities=False)
            for piece in list(self.niveau.pieces):
                piece.dessiner(self.ecran)
            await self.popup.afficher_popup_grimoire(self.ecran, numero, alerte=self.alerte)
            self.gestionnaire_config.marquer_page_vue(numero)
            self.chrono.demarrer()
            meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(numero)
            self.chrono.definir_meilleur_temps(meilleur_temps)

        # Activer l'animation de portail d'entrée
        self.portail_entree_actif = True
        self.portail_entree_animation = 0
        self.joueur_visible = False
        # Jouer le son de spawn
        self.joueur.son_spawn.play()
        self.etat = "jeu"
    
    async def traiter_action_popup(self, action):
        """Traite l'action sélectionnée dans un popup"""
        self.virtual_gamepad.reset()
        if action == "suivant":
            self.niveau_actuel += 1
            self.pieces_en_cours = []
            self.explosions_mob = []
            self.niveau.reset(self.niveau_actuel, self.ecran)
            self.joueur.reset(self.niveau)
            self.joueur.maj_controles()
            self.chrono.demarrer()
            meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
            self.chrono.definir_meilleur_temps(meilleur_temps)
            self.est_record = False
            # Popup page du grimoire (une seule fois par progression)
            if not self.gestionnaire_config.page_vue(self.niveau_actuel):
                self.dessiner_fond_niveau(self.ecran)
                self.niveau.dessiner(self.ecran, self.temps_global, update_entities=False)
                await self.popup.afficher_popup_grimoire(self.ecran, self.niveau_actuel, alerte=self.alerte)
                self.gestionnaire_config.marquer_page_vue(self.niveau_actuel)
                self.chrono.demarrer()
                meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
                self.chrono.definir_meilleur_temps(meilleur_temps)
            # Activer l'animation de portail d'entrée
            self.portail_entree_actif = True
            self.portail_entree_animation = 0
            self.joueur_visible = False
            # Jouer le son de spawn
            self.joueur.son_spawn.play()
            self.etat = "jeu"
        elif action == "planete_suivante":
            # Aller à la planète suivante avec animation de zoom
            self.niveau_actuel += 1
            # Calculer l'univers et la planète dans cet univers
            niveaux_par_univers = self.menu_niveaux.nombre_planetes_par_univers * self.menu_niveaux.niveaux_par_planete
            univers_idx = (self.niveau_actuel - 1) // niveaux_par_univers
            niveau_dans_univers = (self.niveau_actuel - 1) % niveaux_par_univers
            nouvelle_planete = niveau_dans_univers // self.menu_niveaux.niveaux_par_planete
            
            self.menu_niveaux.univers_actuel = univers_idx
            self.menu_niveaux.camera_x = univers_idx * LARGEUR_ECRAN
            self.menu_niveaux.camera_cible_x = self.menu_niveaux.camera_x
            self.menu_niveaux.planetes = self.menu_niveaux.univers[univers_idx]["planetes"]
            self.menu_niveaux.planete_selectionnee = nouvelle_planete
            
            # Charger la musique de la nouvelle planète
            planete = self.menu_niveaux.planetes[nouvelle_planete]
            nom_planete = planete["nom"].lower()
            chemin_musique = resource_path(os.path.join("assets/audio", nom_planete + ".ogg"))
            vol = self.gestionnaire_config.obtenir_volumes().get("musique", 50) / 100
            musique.set_volume(vol)
            musique.jouer(chemin_musique)

            self.menu_niveaux.etat_menu = "galaxie"
            self.menu_niveaux.zoom_en_cours = True
            self.menu_niveaux.zoom_direction = 1
            self.menu_niveaux.zoom_animation = 0
            self.menu_niveaux.recharger_donnees()
            self.etat = "selection"
        elif action == "univers_suivant":
            # Aller à l'univers suivant avec animation de swipe
            self.niveau_actuel += 1
            # Calculer le nouvel univers
            niveaux_par_univers = self.menu_niveaux.nombre_planetes_par_univers * self.menu_niveaux.niveaux_par_planete
            nouvel_univers = (self.niveau_actuel - 1) // niveaux_par_univers
            
            # Restaurer la musique principale
            vol = self.gestionnaire_config.obtenir_volumes().get("musique", 50) / 100
            musique.set_volume(vol)
            musique.jouer(resource_path(os.path.join("assets/audio", "main_theme.ogg")))
            
            # Revenir à la vue galaxie de l'univers précédent
            self.menu_niveaux.etat_menu = "galaxie"
            # Démarrer l'animation de swipe vers le nouvel univers
            self.menu_niveaux.changer_univers(1)  # +1 pour aller vers la droite
            self.menu_niveaux.recharger_donnees()
            self.etat = "selection"
        elif action == "rejouer":
            self.pieces_en_cours = []
            self.explosions_mob = []
            self.niveau.reset(self.niveau_actuel, self.ecran)
            self.joueur.reset(self.niveau)
            self.joueur.maj_controles()
            self.chrono.demarrer()
            meilleur_temps = self.gestionnaire_config.obtenir_meilleur_temps(self.niveau_actuel)
            self.chrono.definir_meilleur_temps(meilleur_temps)
            # Activer l'animation de portail d'entrée
            self.portail_entree_actif = True
            self.portail_entree_animation = 0
            self.joueur_visible = False
            self.est_record = False
            self.joueur.son_spawn.play()
            self.etat = "jeu"
        elif action == "quitter":
            self.chrono.arreter()
            self.est_record = False
            self.menu_niveaux.preparer_retour_niveau(self.niveau_actuel)
            self.etat = "selection"
    
    def nom_planete_actuelle(self):
        """Nom de la planète du niveau courant."""
        planetes = ["terra", "pyros", "aquaris", "nebula", "cryon", "solara", "vortex", "obscura"]
        idx = (self.niveau_actuel - 1) // 5
        if 0 <= idx < len(planetes):
            return planetes[idx]
        return "terra"

    def chemin_musique_planete(self):
        return resource_path(os.path.join("assets/audio", self.nom_planete_actuelle() + ".ogg"))

    def chemin_musique_boss(self):
        return resource_path(os.path.join("assets/audio", self.nom_planete_actuelle() + "_boss.ogg"))

    def volume_musique_config(self):
        """Volume musique réglé dans les paramètres."""
        return self.gestionnaire_config.obtenir_volumes().get("musique", 50) / 100

    def jouer_musique(self, chemin):
        """Charge et joue une musique en boucle. Ne fait rien si le fichier est absent."""
        musique.set_volume(self.volume_musique_config())
        return musique.jouer(chemin)

    def maj_musique_boss(self):
        """Bascule sur la musique de boss quand le Pyrolord se transforme et restaure la musique de planète à la fin du combat. Reste inerte tant que le fichier."""
        boss = self.niveau.boss
        if self.boss_music_niveau != self.niveau_actuel:
            self.boss_music_niveau = self.niveau_actuel
            self.boss_music_existe = musique.existe(self.chemin_musique_boss())
        if not self.boss_music_existe:
            if boss is not None:
                boss.consommer_event_couper_musique()
            return

        # La musique 
        if boss is not None:
            boss.consommer_event_couper_musique()

        # lance la musique de boss dès la fin de la transformation
        veut_boss = (self.etat == "jeu" and boss is not None and boss.alive
                     and not boss.finished and boss.doit_jouer_musique_boss())
        if veut_boss and not self.musique_boss_active:
            if self.jouer_musique(self.chemin_musique_boss()):
                self.musique_boss_active = True
        elif not veut_boss and self.musique_boss_active:
            self.jouer_musique(self.chemin_musique_planete())
            self.musique_boss_active = False

    def maj_ambiances(self):
        """Active les boucles d'ambiance."""
        en_jeu = (self.etat == "jeu")
        actif = (en_jeu and self.popup_actif is None and not self.portail_sortie_actif and not self.explosion_actif)
        # Pendant les popups/explosions, le monde continue (mort/victoire) :
        # le démon garde son ambiance de vol et les sons du boss finissent.
        self.niveau.regler_ambiances(actif, feu_actif=en_jeu, demon_actif=en_jeu, boss_actif=en_jeu)

    def maj_passif(self):
        """Fait tourner le monde pendant la mort/victoire du joueur.

        Les projectiles continuent d'avancer, les animations et les sons des
        ennemis se terminent, mais ceux-ci n'agissent plus et ne se déplacent
        plus (cerveau désactivé). Aucune collision n'affecte le joueur.
        """
        couleur = self.joueur.couleur

        # Démons : animation/tir en cours continuent, pas de déplacement ni IA
        for demon in list(self.niveau.demons):
            proj = demon.update(self.joueur, self.niveau, passif=True)
            if proj is not None:
                self.niveau.projectiles_demon.append(proj)
                self.niveau.son_demon_tir.play()
            if not demon.alive:
                self.niveau.demons.remove(demon)

        # Boss : finit son animation en cours puis reste en idle
        if self.niveau.boss is not None:
            nouveaux = self.niveau.boss.update(self.joueur, passif=True)
            if nouveaux:
                self.niveau.projectiles_boss.extend(nouveaux)
            if self.niveau.boss.finished:
                self.niveau.boss = None

        # Projectiles du boss
        for bp in list(self.niveau.projectiles_boss):
            bp.update()
            if not bp.alive:
                self.niveau.projectiles_boss.remove(bp)
                continue
            if bp.collidable and self.niveau.collision_projectile_boss(bp, couleur):
                bp.start_explosion()

        # Projectiles des démons
        for dp in list(self.niveau.projectiles_demon):
            dp.update()
            if not dp.alive:
                self.niveau.projectiles_demon.remove(dp)
                continue
            if dp.state == "explosion":
                continue
            if self.niveau.collision_projectile_demon(dp, couleur):
                dp.start_explosion()

        # Tirs du joueur continuent d'infliger des dégâts même mort
        for pf in list(self.niveau.projectiles_joueur):
            if pf.state == "trail" and pf.collidable:
                if self.niveau.collision_projectile_mur(pf, couleur):
                    pf.start_explosion()
        self.gerer_tirs_feu_vs_mobs()
        self.maj_explosions_mob()

        boss = self.niveau.boss
        if boss is not None:
            if boss.est_slime():
                if boss.state == "slime":
                    for pf in list(self.niveau.projectiles_joueur):
                        if pf.state == "trail" and pf.collidable and boss.touche_par_rect(pf.rect):
                            pf.start_explosion()
                            self.son_slime_saut.play()
                            boss.stomp()
                            break
            elif boss.state != "dying" and boss.peut_etre_blesse():
                for pf in list(self.niveau.projectiles_joueur):
                    if pf.state == "trail" and pf.collidable and boss.touche_par_rect(pf.rect):
                        pf.start_explosion()
                        boss.encaisser(1)

    async def maj(self):
        """Met à jour la logique du jeu"""
        # Incrémenter le timer global
        self.temps_global += 1
        self.maj_ambiances()
        self.maj_musique_boss()

        # Vérifier si un niveau doit être lancé depuis le menu
        if self.etat == "selection":
            niveau = self.menu_niveaux.verifier_niveau_a_lancer()
            if niveau is not None:
                await self.lancer_niveau(niveau)
                return
            self.menu_niveaux.maj()
            return

        # Popup actif (mort/victoire) : le joueur ne joue plus, mais le monde
        # continue (projectiles, animations, sons) avec les ennemis en passif.
        if self.popup_actif is not None:
            self.maj_passif()
            return None
        
        # Animation de portail d'entrée
        if self.portail_entree_actif:
            self.portail_entree_animation += 1
            if self.portail_entree_animation >= 30:
                self.joueur_visible = True
            if self.portail_entree_animation >= 60:
                self.portail_entree_actif = False
            if self.niveau.boss is not None:
                self.niveau.boss.update(self.joueur)
            for demon in list(self.niveau.demons):
                demon.update(self.joueur, self.niveau)
            return  # Ne pas mettre à jour le jeu pendant l'animation
        
        # Animation de portail de sortie
        if self.portail_sortie_actif:
            self.portail_sortie_animation += 1
            if self.portail_sortie_animation == 30:
                # Le joueur disparaît dans le portail
                self.joueur.son_finish.play()
                self.joueur_visible = False
            elif self.portail_sortie_animation >= 60:
                # Fin de l'animation, montrer le popup de victoire
                self.portail_sortie_actif = False
                self.popup_actif = "victoire"
                self.chrono.arreter()
                
                # Jouer le son de victoire maintenant
                self.joueur.son_victoire.play()
                
                # Créditer les pièces ramassées pendant ce niveau à la victoire)
                self.pieces_gagnees_niveau = len(self.pieces_en_cours)
                self.gestionnaire_config.ajouter_pieces_gagnees(self.pieces_gagnees_niveau)
                self.pieces_en_cours = []
                
                # Sauvegarder le temps et vérifier si c'est un record
                temps_final = self.chrono.obtenir_temps()
                self.est_record = self.gestionnaire_config.maj_meilleur_temps(self.niveau_actuel, temps_final)
                
                # Débloquer le niveau suivant si c'était pas déjà le cas
                niveau_max = self.gestionnaire_config.obtenir_niveau_actuel()
                if self.niveau_actuel == niveau_max:
                    self.gestionnaire_config.maj_niveau_actuel(self.niveau_actuel + 1)
                    
                    # Vérifier si de nouveaux avatars sont débloqués pour le marché (première victoire uniquement)
                    for avatar in self.profil.avatars:
                        niv = avatar.get("niveau_associe")
                        if niv is not None and niv == self.niveau_actuel:
                            self.alerte.afficher("alerte.nouvel_avatar")
                            break
            return  # Ne pas mettre à jour le jeu pendant l'animation
        
        # Animation d'explosion
        if self.explosion_actif:
            temps_actuel = temps.obtenir_temps()
            if temps_actuel - self.explosion_timer >= self.explosion_delai:
                self.explosion_timer = temps_actuel
                self.explosion_frame += 1
                if self.explosion_frame >= len(self.explosion_frames):
                    self.explosion_actif = False
                    if self.etat == "jeu":
                        self.popup_actif = "defaite"
                    self.joueur.son_mort.play()
                    self.chrono.arreter()
                    self.est_record = False
            # Le monde continue pendant l'explosion (projectiles, animations, sons)
            self.maj_passif()
            return

        # Séquence d'enrage : gèle le jeu pendant l'animation de grossissement + le texte
        if self.enrage_actif:
            self.maj_enrage_cutscene()
            return

        if self.etat == "jeu":
            # Lecture clavier via event.key sur le web (cohérent AZERTY), get_pressed sinon
            if EST_WEB:
                touches = TouchesActives(self.touches_actives, self.virtual_gamepad, self.joueur.controls)
            else:
                touches = pygame.key.get_pressed()
            resultat = None
            resultat_deplacement = self.joueur.deplacer(touches, self.niveau)

            self.joueur.pousse_plateforme = False
            self.niveau.maj_plateformes(self.temps_global)
            rc = self.niveau.appliquer_pousse_plateforme(self.joueur)
            if rc == "mort":
                # Écrasement
                self.pieces_en_cours = []
                cx = self.joueur.x + self.joueur.largeur // 2
                cy = self.joueur.y + self.joueur.hauteur // 2
                self.demarrer_explosion(cx, cy)
                return
            if resultat_deplacement == "mort":
                resultat = "mort"
            # tomber dans le vide
            mort_vide = False
            if self.joueur.y > (HAUTEUR_GRILLE * TAILLE_CELLULE):
                mort_vide = True
                resultat = "mort"
            self.joueur.animer()
            # Mise à jour du tir et du pouvoir de feu
            self.joueur.maj_tir()
            avait_pouvoir_feu = self.joueur.peut_tirer_feu
            self.joueur.maj_pouvoir_feu()
            # Si le pouvoir de feu vient de se terminer, faire apparaître un cristal immédiatement
            if avait_pouvoir_feu and not self.joueur.peut_tirer_feu:
                self.niveau.forcer_spawn_cristal_feu()

            # Tir de feu avec la touche configurable
            touche_tir = self.joueur.controls.get("tir", "e")
            code_tir = None
            if touche_tir:
                try:
                    code_tir = pygame.key.key_code(touche_tir)
                except (ValueError, TypeError):
                    code_tir = None
            if code_tir is not None and touches[code_tir]:
                proj_feu = self.joueur.tenter_tir()
                if proj_feu is not None:
                    self.niveau.projectiles_joueur.append(proj_feu)

            # Collision projectiles feu vs murs
            for pf in list(self.niveau.projectiles_joueur):
                if pf.state == "trail" and pf.collidable:
                    if self.niveau.collision_projectile_mur(pf, self.joueur.couleur):
                        pf.start_explosion()

            self.gerer_tirs_feu_vs_mobs()
            self.maj_explosions_mob()


            # Stocke l'interaction du joueur
            inter_result = self.joueur.interagir_avec_blocs(self.niveau)
            if inter_result is not None:
                if inter_result == "mort":
                    resultat = "mort"
                elif resultat is None:
                    resultat = inter_result

            # Vérifier collision projectiles -> joueur
            player_hitbox = pygame.Rect(
                self.joueur.x + self.joueur.marge_x,
                self.joueur.y + self.joueur.marge_y_haut,
                self.joueur.largeur - 2 * self.joueur.marge_x,
                self.joueur.hauteur - self.joueur.marge_y_haut - self.joueur.marge_y_bas,
            )
            player_img = self.joueur.obtenir_image_courante()
            player_mask = self.joueur.obtenir_masque_courant()

            proj_iter = list(self.niveau.projectiles)
            # toucher un sorcier tue
            sorcier_list = list(self.niveau.sorciers)
            for sorcier in sorcier_list:
                draw_x = sorcier.current_draw_x
                draw_y = sorcier.current_draw_y
                frame_rect = pygame.Rect(draw_x, draw_y, sorcier.width, sorcier.height)
                if not player_hitbox.colliderect(frame_rect):
                    continue
                sor_mask = sorcier.current_mask
                if sor_mask is not None and player_mask is not None:
                    offset = (int(self.joueur.x - draw_x), int(self.joueur.y - draw_y))
                    if sor_mask.overlap(player_mask, offset) is not None:
                        resultat = "mort"
                        break
                elif player_hitbox.colliderect(sorcier.rect):
                    resultat = "mort"
                    break

            # toucher un squelette (fumer tue)
            squelette_list = self.niveau.squelettes
            for squelette in list(squelette_list):
                draw_x = int(squelette.current_draw_x)
                draw_y = int(squelette.current_draw_y)
                frame_w = int(squelette.width)
                frame_h = int(squelette.height)
                frame_rect = pygame.Rect(draw_x, draw_y, frame_w, frame_h)
                if not player_hitbox.colliderect(frame_rect):
                    continue

                # Utiliser les masques pour la collision
                squ_mask = squelette.current_mask
                if squ_mask is not None and player_mask is not None:
                    offset = (int(self.joueur.x - squelette.current_draw_x),
                              int(self.joueur.y - squelette.current_draw_y))
                    if squ_mask.overlap(player_mask, offset) is not None:
                        resultat = "mort"
                        break
                    else:
                        # pour éviter que le joueur ne meurt en touchant juste le rectangle de collision du squelette on vérifie aussi la collision par masque
                        continue
                else:
                    # si pas de masque
                    resultat = "mort"
                    break

            # Collision avec les feux
            for feu in list(self.niveau.feux):
                if not feu.alive:
                    continue
                if not player_hitbox.colliderect(feu.rect):
                    continue
                feu_mask = feu.obtenir_masque(self.niveau.frames_feu, self.temps_global, TAILLE_CELLULE)
                if feu_mask is not None and player_mask is not None:
                    offset = (int(self.joueur.x - feu.x), int(self.joueur.y - feu.y))
                    if feu_mask.overlap(player_mask, offset) is not None:
                        resultat = "mort"
                        break
                elif player_hitbox.colliderect(feu.rect):
                    resultat = "mort"
                    break

            # Collision avec les pics
            for pic in list(self.niveau.pics):
                if not pic.alive:
                    continue
                if not player_hitbox.colliderect(pic.rect):
                    continue
                pic_mask = pic.obtenir_masque(self.niveau.image_pic)
                if pic_mask is not None and player_mask is not None:
                    offset = (int(self.joueur.x - pic.x), int(self.joueur.y - pic.y))
                    if pic_mask.overlap(player_mask, offset) is not None:
                        resultat = "mort"
                        break
                elif player_hitbox.colliderect(pic.rect):
                    resultat = "mort"
                    break

            # Collision avec les slimes
            for slime in list(self.niveau.slimes):
                if slime.en_train_de_mourir:
                    continue
                if not player_hitbox.colliderect(slime.rect):
                    continue
                # Vérifier si le joueur tombe sur le slime (pieds du joueur au dessus du milieu du slime)
                pieds_joueur = player_hitbox.bottom
                milieu_slime = slime.rect.top + slime.rect.height // 2
                joueur_descend = self.joueur.vitesse_y > 0
                if joueur_descend and pieds_joueur <= milieu_slime + 15:
                    # Le joueur saute sur le slime
                    self.son_slime_saut.play()
                    slime.recevoir_degats()
                    # Rebond du joueur
                    self.joueur.vitesse_y = -17
                    self.joueur.au_sol = False
                else:
                    resultat = "mort"
                    break

            # Collision avec les pièces
            for piece in list(self.niveau.pieces):
                if not piece.alive:
                    continue
                if player_hitbox.colliderect(piece.rect):
                    self.son_piece.play()
                    piece.alive = False
                    # Stocker temporairement la piece collectee
                    cx = piece.cell_x
                    cy = piece.cell_y
                    if cx is None or cy is None:
                        cx = int(piece.x // TAILLE_CELLULE)
                        cy = int(piece.y // TAILLE_CELLULE)
                    self.pieces_en_cours.append([cx, cy])


            # power ups feu
            for pu in list(self.niveau.cristaux_feu):
                if not pu.alive:
                    continue
                # obtenir ou creer le masque du cristal
                pu_mask = pu.current_mask
                if pu_mask is None:
                    pf = pu.frames[pu.frame_index]
                    pu_mask = pygame.mask.from_surface(pf)
                # joueur doit avoir un masque
                if player_mask is None:
                    continue
                # Offset
                offset = (int(self.joueur.x - pu.rect.left), int(self.joueur.y - pu.rect.top))
                if pu_mask.overlap(player_mask, offset) is not None:
                    pu.alive = False
                    self.joueur.activer_pouvoir_feu()
                    self.niveau.dernier_collecte_cristal = temps.obtenir_temps()

            for proj in proj_iter:
                rect = proj.rect

                if not proj.collidable:
                    continue

                shrink_x = int(rect.width * 0.5)
                shrink_y = int(rect.height * 0.5)
                contracted_rect = rect.inflate(-shrink_x, -shrink_y)
                if not contracted_rect.colliderect(player_hitbox):
                    continue

                proj_frame_index = proj.frame_index
                proj_frames = proj.frames
                proj_masks = proj.masks

                collided = False
                if player_mask is not None and proj_masks:
                    if proj_frame_index < len(proj_masks):
                        mask_pair = proj_masks[proj_frame_index]
                    else:
                        mask_pair = (None, None)
                    if mask_pair[0] is None:
                        if proj_frames:
                            pf = proj_frames[proj_frame_index]
                            if proj.direction == -1:
                                pf = pygame.transform.flip(pf, True, False)
                            proj_mask = pygame.mask.from_surface(pf)
                        else:
                            proj_mask = None
                    else:
                        if proj.direction == 1:
                            proj_mask = mask_pair[0]
                        else:
                            proj_mask = mask_pair[1]

                    if proj_mask is not None:
                        offset = (int(self.joueur.x - proj.x), int(self.joueur.y - proj.y))
                        if proj_mask.overlap(player_mask, offset) is not None:
                            collided = True

                if not collided and rect.colliderect(player_hitbox):
                    collided = True

                if collided:
                    proj.alive = False
                    resultat = "mort"
                    break

            # Démons volants
            for demon in list(self.niveau.demons):
                projectile_demon = demon.update(self.joueur, self.niveau)
                if projectile_demon is not None:
                    self.niveau.projectiles_demon.append(projectile_demon)
                    self.niveau.son_demon_tir.play()
                if not demon.alive:
                    self.niveau.demons.remove(demon)
                    continue
                if demon.en_train_de_mourir:
                    continue
                # Contact avec un démon
                frame_rect = pygame.Rect(demon.current_draw_x, demon.current_draw_y, demon.width, demon.height)
                if not player_hitbox.colliderect(frame_rect):
                    continue
                dm = demon.current_mask
                if dm is not None and player_mask is not None:
                    offset = (int(self.joueur.x - demon.current_draw_x), int(self.joueur.y - demon.current_draw_y))
                    if dm.overlap(player_mask, offset) is not None:
                        resultat = "mort"
                elif player_hitbox.colliderect(demon.rect):
                    resultat = "mort"

            # Boss (porte de sortie + éjection des pièces à la mort)
            boss = self.niveau.boss
            if boss is not None:
                nouveaux = boss.update(self.joueur)
                if nouveaux:
                    self.niveau.projectiles_boss.extend(nouveaux)
                if boss.finished:
                    # mort : la porte de sortie apparaît.
                    if self.niveau.porte_boss is not None:
                        px, py = self.niveau.porte_boss
                    else:
                        px = int(boss.hitbox.centerx // TAILLE_CELLULE)
                        py = int(boss.hitbox.bottom // TAILLE_CELLULE) - 1
                    self.niveau.boss = None
                    if 0 <= py < HAUTEUR_GRILLE and 0 <= px < LARGEUR_GRILLE:
                        self.niveau.grille[py][px] = "porte"
                        
                    # Éjection des pièces de boss
                    from entities.objets import Piece

                    y_sol = boss.hitbox.bottom

                    for i in range(4):
                        piece = Piece(boss.hitbox.centerx, boss.hitbox.centery)
                        piece.cell_x = "boss"
                        piece.cell_y = i
                        piece.y_sol = y_sol
                        piece.v_x = random.uniform(-4, 4)
                        piece.v_y = random.uniform(-8, -4)
                        self.niveau.pieces.append(piece)

                elif boss.est_slime():
                    # Forme slime
                    if boss.state == "slime":
                        for pf in list(self.niveau.projectiles_joueur):
                            if pf.state == "trail" and pf.collidable and boss.touche_par_rect(pf.rect):
                                pf.start_explosion()
                                self.son_slime_saut.play()
                                boss.stomp()
                                break
                    if boss.state == "slime" and player_hitbox.colliderect(boss.hitbox):
                        pieds = player_hitbox.bottom
                        milieu = boss.hitbox.top + boss.hitbox.height // 2
                        if self.joueur.vitesse_y > 0 and pieds <= milieu + 20:
                            self.son_slime_saut.play()
                            boss.stomp()
                            self.joueur.vitesse_y = -17
                            self.joueur.au_sol = False
                        elif boss.touche_par_masque(player_mask, (self.joueur.x, self.joueur.y)):
                            resultat = "mort"
                elif boss.state != "dying":
                    # Forme boss
                    if boss.touche_par_masque(player_mask, (self.joueur.x, self.joueur.y)):
                        resultat = "mort"
                    if boss.peut_etre_blesse():
                        for pf in list(self.niveau.projectiles_joueur):
                            if pf.state == "trail" and pf.collidable and boss.touche_par_rect(pf.rect):
                                pf.start_explosion()
                                boss.encaisser(1)

                # Annonce
                txt = boss.consommer_annonce_enrage()
                if txt and boss.alive and not boss.finished:
                    self.boss_annonce = txt
                    self.boss_annonce_time = temps.obtenir_temps()
                    self.enrage_actif = True
                    self.enrage_start = temps.obtenir_temps()
                    self.enrage_boss = boss
                    boss.render_scale = 1.0
                    self.son_enrage.play()
                    # baisse la musique le temps de l'enragement pour entendre le bruitage
                    musique.set_volume(self.volume_musique_config() * 0.3)

            # Projectiles du boss
            for bp in list(self.niveau.projectiles_boss):
                bp.update()
                if not bp.alive:
                    self.niveau.projectiles_boss.remove(bp)
                    continue
                if not bp.collidable:
                    continue
                # se casse sur un bloc
                if self.niveau.collision_projectile_boss(bp, self.joueur.couleur):
                    bp.start_explosion()
                    continue
                if bp.rect.colliderect(player_hitbox):
                    bp.start_explosion()
                    resultat = "mort"

            # Projectiles des démons
            for dp in list(self.niveau.projectiles_demon):
                dp.update()
                if not dp.alive:
                    self.niveau.projectiles_demon.remove(dp)
                    continue
                if dp.state == "explosion":
                    continue
                # explose sur un obstacle (mur / plateforme)
                if self.niveau.collision_projectile_demon(dp, self.joueur.couleur):
                    dp.start_explosion()
                    continue
                # touche le joueur : le tue
                proj_mask = dp.masque_courant()
                px, py = dp.offset_dessin()
                if player_mask is not None:
                    offset = (int(self.joueur.x - px), int(self.joueur.y - py))
                    if proj_mask.overlap(player_mask, offset) is not None:
                        dp.alive = False
                        resultat = "mort"

            # Cas de téléportation (quand on touche le portail jaune)
            if resultat == "teleportation":
                # Démarrer l'animation de sortie
                self.portail_sortie_actif = True
                self.portail_sortie_animation = 0
                self.portail_sortie_x = self.joueur.x + self.joueur.largeur // 2
                self.portail_sortie_y = self.joueur.y + self.joueur.hauteur // 2
                self.joueur.son_finish.play()

            # Cas de défaite
            elif resultat == "mort":
                # Les pièces collectées pendant cette tentative sont perdues
                self.pieces_en_cours = []
                if mort_vide:
                    self.popup_actif = "defaite"
                    self.joueur.son_mort.play()
                    self.chrono.arreter()
                    self.est_record = False
                else:
                    cx = self.joueur.x + self.joueur.largeur // 2
                    cy = self.joueur.y + self.joueur.hauteur // 2
                    self.demarrer_explosion(cx, cy)

    def afficher(self):
        """Dessine tous les éléments"""
        if self.etat == "menu":
            self.menu.afficher_menu(self.ecran)
            
        elif self.etat == "selection": 
            self.menu_niveaux.afficher_selection(self.ecran)
            
        elif self.etat == "jeu":
            self.dessiner_fond_niveau(self.ecran)
            self.niveau.dessiner(self.ecran, self.temps_global, update_entities=not self.enrage_actif)
            
            # Dessiner le portail d'entrée si actif
            if self.portail_entree_actif:
                self.dessiner_portail_jeu(self.joueur.x + self.joueur.largeur // 2, self.joueur.y + self.joueur.hauteur // 2)
            
            # Dessiner le portail de sortie si actif
            if self.portail_sortie_actif:
                self.dessiner_portail_jeu(self.portail_sortie_x, self.portail_sortie_y, "sortie")
            
            # Dessiner le joueur seulement s'il est visible ET pas d'animation de portail ET si aucun popup n'est affiché
            if self.joueur_visible and not self.portail_entree_actif and not self.portail_sortie_actif and self.popup_actif is None:
                self.joueur.dessiner(self.ecran)
            
            # Dessiner l'explosion
            if self.explosion_actif and self.explosion_frame < len(self.explosion_frames):
                self.ecran.blit(self.explosion_frames[self.explosion_frame], (self.explosion_x, self.explosion_y))

            # Dessiner les explosions des mobs tués
            for ex in self.explosions_mob:
                if ex["frame"] < len(self.explosion_frames):
                    self.ecran.blit(self.explosion_frames[ex["frame"]], (ex["x"], ex["y"]))
            
            if self.popup_actif is None:
                self.pause.dessiner_bouton(self.ecran)
                if est_tactile():
                    if self.joueur:
                        self.virtual_gamepad.peut_tirer_active = self.joueur.peut_tirer_feu
                    self.virtual_gamepad.dessiner(self.ecran)
            self.chrono.dessiner(self.ecran)
            
            hud_y_offset = 0

            # Barre de vie du boss
            if self.niveau.boss is not None and self.niveau.boss.barre_visible():
                self.dessiner_barre_vie_boss(self.ecran)
                hud_y_offset = 56

            # Afficher le timer de feu en haut
            if self.joueur.peut_tirer_feu:
                self.dessiner_timer_feu(self.ecran, hud_y_offset)

            # Annonce de boss
            self.dessiner_annonce_boss(self.ecran)

            # Afficher le popup s'il y en a un
            if self.popup_actif == "victoire":
                temps_final = self.chrono.obtenir_temps()
                self.popup.dessiner_popup_victoire(self.ecran, self.niveau_actuel, temps_final, self.est_record, self.pieces_gagnees_niveau)
            elif self.popup_actif == "defaite":
                self.popup.dessiner_popup_defaite(self.ecran, self.niveau_actuel)

        elif self.etat == "param":
            self.parametres.afficher_parametres(self.ecran)
        
        elif self.etat == "profil":
            self.profil.afficher_profil(self.ecran)
        
        # Alerte par-dessus tout
        self.alerte.dessiner(self.ecran)
        
        pygame.display.flip()
    
    def dessiner_fond_niveau(self, ecran):
        """Dessine le fond du niveau basé sur la planète actuelle"""
        info_planete = self.menu_niveaux.obtenir_info_planete(self.niveau_actuel)
        couleur = info_planete.get("couleur", (100, 100, 100))
        self.niveau.dessiner_fond(ecran, couleur, self.temps_global)
    
    def dessiner_portail_jeu(self, x, y, type_portail="entree"):
        """Dessine un portail de téléportation jaune/doré dans le jeu"""
        
        # Choisir l'animation selon le type de portail
        if type_portail == "sortie":
            animation_timer = self.portail_sortie_animation
        else:
            animation_timer = self.portail_entree_animation
        
        # Effet de rotation et pulsation
        pulse = 1 + 0.2 * math.sin(animation_timer * 0.3)
        taille = 50
        rayon = int(taille * pulse)
        
        # Cercles concentriques pour l'effet de portail
        for i in range(5):
            alpha = 180 - i * 35
            r = rayon - i * (rayon // 6)
            if r > 0:
                # Couleur jaune/dorée avec variation
                teinte = 200 + int(55 * math.sin(animation_timer * 0.2 + i))
                surface = pygame.Surface((r * 2 + 10, r * 2 + 10), pygame.SRCALPHA)
                pygame.draw.circle(surface, (255, teinte, 50, alpha), (r + 5, r + 5), r)
                self.ecran.blit(surface, (x - r - 5, y - r - 5))
        
        # Particules tourbillonnantes
        for i in range(8):
            angle = animation_timer * 0.15 + i * (math.pi / 4)
            dist = rayon * 0.7
            px = x + int(math.cos(angle) * dist)
            py = y + int(math.sin(angle) * dist)
            particle_size = 3 + int(2 * math.sin(animation_timer * 0.4 + i))
            pygame.draw.circle(self.ecran, (255, 255, 150), (px, py), particle_size)
        
        # Centre brillant
        pygame.draw.circle(self.ecran, (255, 255, 200), (x, y), rayon // 4)

    def dessiner_timer_feu(self, ecran, y_offset=0):
        """Affiche le compteur du pouvoir de feu en haut de l'écran."""
        secondes = self.joueur.temps_feu_restant / 1000
        # Barre de fond
        bar_w = 200
        bar_h = 20
        bar_x = LARGEUR_ECRAN // 2 - bar_w // 2
        bar_y = 10 + y_offset
        pygame.draw.rect(ecran, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
        # Remplissage
        ratio = max(0, self.joueur.temps_feu_restant / self.joueur.duree_feu)
        if secondes > 5:
            couleur_barre = (255, 100, 30)
        else:
            couleur_barre = (255, 50, 50)
        pygame.draw.rect(ecran, couleur_barre, (bar_x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(ecran, (200, 200, 200), (bar_x, bar_y, bar_w, bar_h), 1)
        # Texte
        font = police(22)
        txt = font.render(t("popup.feu") + "  " + str(round(secondes, 1)) + "s", True, (255, 255, 255))
        ecran.blit(txt, position_centree(txt, font, bar_x + bar_w // 2, bar_y + bar_h // 2))

    def dessiner_barre_vie_boss(self, ecran):
        """Dessine la barre de vie du boss en haut de l'écran (HUD)."""
        boss = self.niveau.boss
        if boss is None:
            return
        if boss.pv_max > 0:
            ratio = max(0.0, boss.pv / boss.pv_max)
        else:
            ratio = 0.0

        bar_w = 600
        bar_h = 24
        bar_x = LARGEUR_ECRAN // 2 - bar_w // 2
        bar_y = 22

        pygame.draw.rect(ecran, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            pygame.draw.rect(ecran, (220, 40, 40), (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(ecran, (200, 200, 200), (bar_x, bar_y, bar_w, bar_h), 1)

        nom = boss.nom
        font = police(30)
        txt = font.render(nom, True, (255, 255, 255))
        ecran.blit(txt, position_centree(txt, font, bar_x + bar_w // 2, bar_y + bar_h // 2))

    def maj_enrage_cutscene(self):
        """Met à jour la séquence d'enrage (jeu gelé) : grossissement animé puis maintien."""
        boss = self.enrage_boss
        if boss is None or boss is not self.niveau.boss:
            self.enrage_actif = False
            self.enrage_boss = None
            musique.set_volume(self.volume_musique_config())
            return
        now = temps.obtenir_temps()
        elapsed = now - self.enrage_start
        if boss is not None:
            t = (elapsed - self.enrage_grow_delay) / max(1, self.enrage_grow_duree)
            t = min(1.0, max(0.0, t))
            ease = 1 - (1 - t) ** 3
            boss.render_scale = 1.0 + (boss.enrage_scale - 1.0) * ease
        if elapsed >= self.enrage_duree:
            if boss is not None:
                boss.render_scale = 1.0
                boss.grandir(boss.enrage_scale)
            self.enrage_actif = False
            self.enrage_boss = None
            # restaure le volume de la musique à la fin de l'enragement
            musique.set_volume(self.volume_musique_config())

    def dessiner_annonce_boss(self, ecran):
        """Affiche l'annonce de boss (ex: enrage) en grand au centre de l'écran."""
        if not self.boss_annonce:
            return
        elapsed = temps.obtenir_temps() - self.boss_annonce_time
        fondu = 700
        duree = self.enrage_duree + fondu   # reste affiché tant que le jeu est gelé
        if elapsed >= duree:
            self.boss_annonce = None
            return
        if elapsed < 200:
            alpha = int(255 * elapsed / 200)
        elif elapsed > duree - fondu:
            alpha = int(255 * (duree - elapsed) / fondu)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))
        font = police(90)
        txt = font.render(self.boss_annonce, True, (255, 255, 255))
        ombre = font.render(self.boss_annonce, True, (0, 0, 0))
        txt.set_alpha(alpha)
        ombre.set_alpha(alpha)
        x = LARGEUR_ECRAN // 2 - txt.get_width() // 2
        y = int(HAUTEUR_ECRAN * 0.40)
        ecran.blit(ombre, (x + 4, y + 4))
        ecran.blit(txt, (x, y))

    async def run(self):
        """Boucle principale du jeu"""
        # Lancer l'intro
        intro = Intro(self.ecran, self.gestionnaire_config, self)
        resultat_intro = await intro.lancer()
        if resultat_intro == "quitter":
            pygame.quit()
            sys.exit()

        # Précharger tout le jeu derrière l'écran de chargement
        self.preparer_ecran_chargement()
        etapes = etapes_prechargement()
        etapes.append((self.creer_sous_systemes, ()))
        await self.executer_prechargement(etapes)

        # Alerte
        self.alerte = Alerte(self.gestionnaire_config)
        self.menu_niveaux.alerte = self.alerte

        # Affiche le menu puis lance la musique (evite la musique pendant l'ecran de chargement)
        self.menu.afficher_menu(self.ecran)
        pygame.display.flip()
        musique.jouer(resource_path(os.path.join("assets/audio", "main_theme.ogg")))

        # Vérifier si la sauvegarde est corrompue et réinitialiser si nécessaire
        if self.gestionnaire_config.sauvegarde_corrompue:
            self.alerte.afficher("alerte.sauvegarde_corrompue_reset")
            self.gestionnaire_config.sauvegarde_corrompue = False

        # Afficher les patch notes si c'est la première fois sur cette version
        if not self.gestionnaire_config.version_vue(VERSION_JEU):
            self.menu.afficher_menu(self.ecran)
            pygame.display.flip()
            await self.popup.afficher_patch_notes(self.ecran, VERSION_JEU, alerte=self.alerte)
            self.gestionnaire_config.marquer_version_vue(VERSION_JEU)

        gc.collect()
        gc.freeze()

        temps.init()
        duree_frame = 1000.0 / FPS
        dernier_tick = pygame.time.get_ticks()
        while self.en_cours:
            maintenant = pygame.time.get_ticks()
            dt = maintenant - dernier_tick
            dernier_tick = maintenant

            await self.gerer_evenements()

            nb_maj = int(round(dt / duree_frame))
            if nb_maj < 1:
                nb_maj = 1
            if nb_maj > 4:
                nb_maj = 4
            for _ in range(nb_maj):
                if self.etat == "jeu":
                    temps.set_pause(False)
                else:
                    temps.set_pause(True)
                temps.avancer(duree_frame)
                await self.maj()

            self.afficher()
            self.horloge.tick(FPS)
            await asyncio.sleep(0)
        if EST_WEB:
            import platform
            platform.window.colormage_stop_all_audio()
        pygame.quit()
        return

if __name__ == "__main__":
    jeu = Game()
    asyncio.run(jeu.run())
