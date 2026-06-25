<div align="center">

![logo](assets/img/ui/logo.png)

**ColorMage** est un jeu de plateforme-puzzle développé en **Python** avec **Pygame**.

Vous incarnez un Mage capable de changer de couleur pour naviguer dans des niveaux remplis de plateformes, de pièges et d'ennemis.  
La clé du succès : vous ne pouvez interagir qu'avec les éléments qui correspondent à **votre couleur**.

![Version](https://img.shields.io/badge/version-v2.4-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-yellow)
![Pygame](https://img.shields.io/badge/pygame-latest-green)
![Licence](https://img.shields.io/badge/licence-tous%20droits%20r%C3%A9serv%C3%A9s-lightgrey)

</div>



## 📷 Screenshots

| Menu principal | Gameplay |
|:-:|:-:|
| ![Menu](assets/img/screenshot_menu.png) | ![Gameplay](assets/img/screenshot_game.png) |



## 🎮 Gameplay

Le joueur doit résoudre des parcours en changeant sa couleur pour utiliser les plateformes et atteindre le portail de sortie jaune.

- **Blocs colorés** : le Mage marche sur les blocs de sa couleur et **traverse** les autres.
- **Potions de couleur** : ramasser une potion change la couleur du Mage (ex : potion verte → Mage vert).
- **Portail de sortie** : le portail jaune termine le niveau.
- **Pièces** : collectables cachés dans chaque niveau.
- **Pièges** : pics, ennemis mobiles, projectiles.

### Ennemis

| Ennemi | Description |
|--|-|
| 🧙 Sorcier | Tire des projectiles dans sa portée |
| 💀 Garde d'os | Patrouille sur une zone définie |
| 🟢 Slime | Ennemi coloré, dangereux au contact (rebond sur la tête) |
| 👹 Démon volant | Te poursuit, fonce et tire des projectiles |
| 🔥 Pyrolord | Boss de feu : se révèle après son réveil et enchaîne ses attaques |

> Certains ennemis lâchent un **butin** (pièce, potion ou cristal) à leur mort.

### Blocs spéciaux & objets

| Bloc / Objet | Effet |
|------|-------|
| Bloc mobile | Se déplace horizontalement ou verticalement |
| Potion de couleur | Change la couleur du Mage |
| Pic | Mort instantanée au contact |
| Feu | Brasier mortel au contact, ne peut être éteint |
| Cristal de feu | Confère temporairement le pouvoir de tirer des flammes |
| Pièce | +1 au compteur de pièces (re-collectable à chaque partie) |


## 🗺️ Niveaux

**10 niveaux** sont actuellement jouables, répartis sur les planètes **Terra** et **Pyros** (cette dernière s'achevant par un **combat de boss**). Les autres planètes (Aquaris, Nebula, Cryon, Solara, Vortex, Obscura) sont **à venir** dans de prochaines mises à jour.  
Chaque niveau possède un **meilleur temps** enregistré, et un **Grimoire** se complète au fil de l'aventure - à vous de le découvrir.


## 👤 Profil

- Pseudo personnalisable
- Avatar sélectionnable (débloqués en battant des ennemis, puis achetés au marché)
- Statistiques : niveau max atteint, pièces gagnées, temps de jeu total
- Réinitialisation de la progression


## 🛒 Marché

Dépense les pièces gagnées en terminant les niveaux :

- **Avatars** : nouvelles apparences débloquées au fil de la progression.
- **Pouvoirs** : améliorations permanentes du cristal de feu - *cristal prolongé* (durée allongée) et *cristal accéléré* (projectiles plus rapides), débloqués à certains niveaux.



## 🎮 Téléchargement

Pour jouer, télécharge la dernière version dans l'onglet [**Releases**](https://github.com/Emrecan45/ColorMage/releases) : l'exécutable est **autonome**, aucune installation requise.



## 🌐 Jouer dans le navigateur

**▶ Jouer maintenant : [emrecan45.github.io/colormage](https://emrecan45.github.io/colormage/)**

Une version **web** (zéro installation) est jouable directement dans le navigateur, compilée en WebAssembly avec [pygbag](https://github.com/pygame-web/pygbag). Elle fonctionne aussi sur **mobile et tablette** grâce à un pad tactile (joystick + boutons). La procédure de génération est décrite dans [BUILD.md](BUILD.md).



## ⚙️ Installation depuis les sources

> Pour les développeurs souhaitant lancer le jeu depuis le code.

**Prérequis :** Python 3.8 ou supérieur

**Linux / macOS :**
```bash
git clone https://github.com/Emrecan45/ColorMage.git
cd ColorMage
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 src/main.py
```

**Windows (PowerShell) :**
```powershell
git clone https://github.com/Emrecan45/ColorMage.git
cd ColorMage
pip install -r requirements.txt
python src/main.py
```



## 🕹️ Contrôles

| Action | Touche (défaut) |
|--|--|
| Aller à droite | `→` |
| Aller à gauche | `←` |
| Sauter | `↑` |
| Tirer (avec le Cristal de feu) | `E` |
| Pause | `P` ou `Échap` |

> Les touches sont **reconfigurables** depuis le menu Paramètres.



## 🔧 Paramètres

- Remappage des touches (droite, gauche, sauter, tirer)
- Volume musique et effets sonores indépendants
- Langue : français ou anglais
- Export / Import de sauvegarde



## 📝 Notes de version

À la première ouverture d'une nouvelle version, une popup résume les nouveautés. L'information est mémorisée dans la sauvegarde pour ne s'afficher qu'une seule fois.


## 📁 Structure du projet

```
ColorMage/
├── main.py                 # Point d'entrée (bureau + web)
├── src/                    # Code source Python
│   ├── main.py             # Boucle principale du jeu (classe Game)
│   ├── core/               # Cœur : config, sauvegarde, niveaux, temps, assets
│   │   ├── config.py       # Constantes et configuration globale
│   │   ├── config_manager.py # Gestion de la sauvegarde
│   │   ├── niveau.py       # Chargement et rendu des niveaux
│   │   ├── assets.py       # Chargement des ressources
│   │   └── temps.py        # Gestion du temps de jeu
│   ├── entities/           # Joueur, ennemis, boss, projectiles, objets
│   │   ├── joueur.py
│   │   ├── monstres.py
│   │   ├── objets.py
│   │   ├── projectiles.py
│   │   ├── obstacles.py
│   │   └── boss/           # Boss (Pyrolord...)
│   └── ui/                 # Interfaces : menus, profil, marché, popups...
│       ├── menu.py, menu_niveaux.py, profil.py, parametres.py
│       ├── pause.py, popup.py, chronometre.py, alerte.py, intro.py
├── levels/                 # Fichiers JSON des niveaux (par planète) + guide
├── assets/                 # Ressources du jeu
│   ├── audio/              # Sons et musiques
│   └── img/                # Images, avatars, sprites, UI
├── tools/                  # Outils de build web (build_web.py, web.tmpl)
├── LICENSE                 # Licence du projet (tous droits réservés)
├── CREDITS.md              # Crédits et sources des assets
├── BUILD.md                # Génération des builds (bureau + web)
├── .gitignore              # Fichiers à ignorer par Git
├── README.md               # Ce fichier
└── requirements.txt        # Dépendances (jeu + build web pygbag)
```



## 🧠 Conception

**ColorMage** explore une mécanique de jeu où **couleur et stratégie** sont indissociables.  
Chaque niveau est un puzzle de déplacement : anticiper les changements de couleur nécessaires pour progresser sans tomber dans le vide ou se faire tuer.



## 🎨 Crédits

Ce projet utilise des ressources graphiques originales et des contributions externes. La liste des auteurs et des sources associées est disponible dans le fichier [`CREDITS.md`](CREDITS.md).



## 📄 Licence

Ce projet est publié **tous droits réservés**. Le code est visible à titre de démonstration : copier, modifier, redistribuer ou héberger le jeu ailleurs, ou en faire un usage commercial, est interdit sans mon accord explicite. Voir le fichier [`LICENSE`](LICENSE) pour plus de détails.

