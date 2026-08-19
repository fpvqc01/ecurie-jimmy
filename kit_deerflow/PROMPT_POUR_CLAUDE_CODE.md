(Colle TOUT ce message comme premier message dans Claude Code sur le nouveau laptop)

Salut! Je suis Jimmy, francophone quebecois, debutant en programmation —
reponds toujours en francais, donne-moi des commandes pretes a coller, et
previens-moi clairement quand un fichier contient un espace a remplir
(placeholder) ou une cle secrete.

MISSION DE CETTE SESSION
Installer DeerFlow 2 (github.com/bytedance/deer-flow) sur CE laptop et lui
faire produire une ANALYSE INDEPENDANTE de mon systeme de trading. Le dossier
« Analyse_Externe_Ecurie » fourni avec ce kit contient tout : des COPIES des
robots, le README du systeme, et surtout MISSION_ANALYSE.md qui definit les
questions a poser. Ce laptop ne contient AUCUN systeme de trading actif —
DeerFlow ne doit jamais recevoir autre chose que ce dossier de copies.

ETAPES A SUIVRE
1. Verifie les prerequis : git, Docker Desktop (chemin recommande si ce
   laptop a 8 Go de RAM libres), sinon Node.js 22+, pnpm, uv. Installe ce
   qui manque avec mon accord (winget).
2. Clone le depot : git clone https://github.com/bytedance/deer-flow
3. Suis le fichier Install.md du depot — il est ecrit pour les agents comme
   toi. Cree config.yaml (make config ou copie de config.example.yaml).
4. Configuration du modele : je vais creer une cle API (DeepSeek recommande,
   ~2 $ de credit suffisent — guide-moi pour creer le compte moi-meme).
   La cle va dans une VARIABLE D'ENVIRONNEMENT (ex. DEEPSEEK_API_KEY),
   jamais en clair dans un fichier — montre-moi exactement ou et comment.
5. Demarre DeerFlow (make docker-start ou make dev selon le chemin) et
   verifie que l'interface repond.
6. Lance l'analyse : donne a DeerFlow le contenu du dossier
   Analyse_Externe_Ecurie en commencant par MISSION_ANALYSE.md, et
   demande-lui de repondre aux 5 questions de la mission.
7. Sauvegarde son rapport complet dans un fichier
   RAPPORT_DEERFLOW_<date>.md dans le dossier du kit.

REGLES DURES
- Analyse seulement : DeerFlow ne modifie rien, ne code rien dans mes
  projets, n'accede a aucun compte.
- Aucune cle ni mot de passe en clair dans les fichiers ou la conversation.
- Le rapport final me sera remis pour que je le rapporte a ma session
  Claude Code principale (sur mon laptop de trading), ou chaque suggestion
  sera backtestee avant toute adoption — standards du README : principe
  economique externe, net des frais reels, stable sur 2 moities et
  parametres voisins, ameliore le portefeuille sous plafond de 2 positions.
