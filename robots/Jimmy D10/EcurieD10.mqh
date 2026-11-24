//+------------------------------------------------------------------+
//| EcurieD10.mqh                                                    |
//| Identite commune des 5 robots Jimmy D10.                         |
//|                                                                  |
//| UN SEUL numero de base. Chaque robot prend base + son rang :     |
//|   +1 cassure BTC, +2 EMA BTC, +3 Nasdaq, +4 petrole, +5 or.      |
//| Le plafond de positions et l'exclusion or/Nasdaq reconnaissent   |
//| toute la plage ]base ; base+NB]. Creer une generation suivante : |
//| copier le dossier et changer MAGIC_ECURIE_D10 ici. Plus de liste |
//| de magics recopiee (c'est ce qui a laisse D9 sur les magics L13).|
//|                                                                  |
//| Le magic saisi dans les proprietes doit rester dans la plage.    |
//| Sinon OnInit refuse de demarrer : un magic orphelin rendrait     |
//| le plafond et la correlation aveugles, sans message.             |
//+------------------------------------------------------------------+
#ifndef ECURIE_D10_MQH
#define ECURIE_D10_MQH

#define MAGIC_ECURIE_D10  20262100
#define NB_ROBOTS_ECURIE  5

#define MAGIC_D10_CASSURE (MAGIC_ECURIE_D10 + 1)   // 20262101
#define MAGIC_D10_EMA     (MAGIC_ECURIE_D10 + 2)   // 20262102
#define MAGIC_D10_NASDAQ  (MAGIC_ECURIE_D10 + 3)   // 20262103
#define MAGIC_D10_PETROLE (MAGIC_ECURIE_D10 + 4)   // 20262104
#define MAGIC_D10_OR      (MAGIC_ECURIE_D10 + 5)   // 20262105

//+------------------------------------------------------------------+
bool MagicAppartientEcurie(const long m)
  {
   return(m > MAGIC_ECURIE_D10 && m <= MAGIC_ECURIE_D10 + NB_ROBOTS_ECURIE);
  }

//+------------------------------------------------------------------+
bool MagicEcurieAccepte(const long m)
  {
   if(MagicAppartientEcurie(m))
      return(true);
   Print("D10 REFUSE : magic ", m, " hors plage ",
         MAGIC_ECURIE_D10 + 1, "..", MAGIC_ECURIE_D10 + NB_ROBOTS_ECURIE,
         ". Le plafond et la correlation ne verraient pas ce robot.");
   return(false);
  }

//+------------------------------------------------------------------+
//| turboChallenge : vrai seulement si PhaseActuelle est PHASE_1 ou  |
//| PHASE_2. L'appelant fait le test sur l'enum (pas de chiffre en   |
//| dur ici). En compte finance le message dit que le facteur vaut 1.|
//+------------------------------------------------------------------+
void AnnoncerPolitiqueD10(const long magic, const bool turboChallenge)
  {
   string turbo = turboChallenge
                   ? "actif (phase challenge, jusqu'au coussin)"
                   : "coupe (compte finance, facteur 1)";
   Print("D10 | magic=", magic,
         " plage=", MAGIC_ECURIE_D10 + 1, "..", MAGIC_ECURIE_D10 + NB_ROBOTS_ECURIE,
         " | turbo ", turbo);
  }

#endif
