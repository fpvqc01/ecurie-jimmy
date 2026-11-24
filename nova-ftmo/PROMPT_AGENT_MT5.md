# Prompt agent local — installer Nova sur MT5

Copie-colle **tout le bloc** dans un agent qui contrôle ton Windows (Cursor Agent / Computer Use) sur le PC où MetaTrader 5 est installé.

---

## PROMPT À COLLER

```
Tu contrôles mon ordinateur Windows. Objectif : installer et activer les robots Nova FTMO dans MetaTrader 5, sans toucher à l’ancienne écurie Jimmy.

Contexte repo (déjà cloné ou à cloner) :
- Dossier projet : cherche ecurie-jimmy (souvent Documents, Desktop, ou clone git)
- EA à installer :
  1) nova-ftmo/robots/Nova_ORB_XAUUSD_M5.mq5   ← PRIORITÉ (sprint ~30j, risqué)
  2) nova-ftmo/robots/Nova_XAUUSD_H4.mq5       ← option survie
  3) nova-ftmo/robots/Nova_US100_H4.mq5        ← option survie

Étapes obligatoires (dans l’ordre) :

1) Trouve le terminal MT5 utilisé pour FTMO (chemin typique :
   C:\Program Files\FTMO MetaTrader 5\
   ou C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\<ID>\
   Liste les terminaux si plusieurs).

2) Copie les 3 fichiers .mq5 dans :
   <Terminal>\MQL5\Experts\Nova\
   Crée le dossier Nova s’il n’existe pas.

3) Ouvre MetaEditor (metaeditor64.exe du même terminal) et compile chaque .mq5
   (ou F7). Vérifie qu’un .ex5 apparaît à côté. S’il y a des erreurs de compile,
   corrige-les ou rapporte-les clairement.

4) Ouvre MT5, connecte le compte FTMO (idéalement Free Trial / démo d’abord).
   Active : Outils → Options → Expert Advisors →
   - Autoriser le trading algorithmique
   - Autoriser le trading automatique DLL = OFF sauf besoin
   Bouton Algo Trading = ON (vert) dans la barre d’outils.

5) Mode SPRINT (par défaut maintenant) :
   - Ouvre un graphique XAUUSD période M5
   - Glisse Nova_ORB_XAUUSD_M5 sur le graphique
   - Inputs :
     RisquePct=1.8
     RangeBars=3
     TpR=1.8
     HaltJourPct=3.2
     ObjectifPhasePct=10   (phase 1 challenge) ; mettre 5 en phase 2 ; 0 si financé
     LondonOpenHour / NyOpenHour = heures UTC du terminal (ajuste si le broker n’est pas UTC)
   - Coche Allow live trading, OK
   - Vérifie smileynet / icône EA active (pas de smiley triste)

6) Ne lance PAS les EA H4 en même temps que l’ORB M5 sur le même compte
   (conflit de risque). H4 = seulement si on abandonne le mode sprint.

7) À la fin, envoie un rapport court :
   - chemin Terminal trouvé
   - compile OK/KO pour chaque EA
   - compte connecté (login masqué partiellement, ex. ***1234)
   - graphique + EA attaché
   - Algo Trading ON/OFF
   - éventuels warnings (fuseau horaire, symbole XAUUSD vs GOLD, etc.)

Règles :
- Ne partage pas de mots de passe.
- Ne désinstalle rien.
- Ne touche pas aux robots Jimmy L* déjà présents.
- Si MT5 n’est pas trouvé, demande le chemin exact une seule fois.
```

---

## Commande Cursor CLI (si tu as l’agent en local)

Depuis le dossier du repo, sur **ton** PC Windows :

```bash
agent "Lis nova-ftmo/PROMPT_AGENT_MT5.md et exécute le prompt d’installation MT5 Nova ORB sur ce PC."
```

Ou dans le chat Cursor Desktop (mode agent + accès ordinateur) :

```
Exécute exactement les instructions de nova-ftmo/PROMPT_AGENT_MT5.md
```
