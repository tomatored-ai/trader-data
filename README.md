# trade-data — veille automatique

GitHub lance tout seul les skills [trader-skill](https://github.com/tomatored-ai/trader-skill)
et dépose les résultats en **issues** (onglet *Issues*). L'appli GitHub te prévient sur ton téléphone.
Rien à installer sur ton ordinateur. **Aucun ordre n'est jamais passé ici.**

## Ce qui tourne

| Quand (heure de Paris) | Quoi | Skills |
| --- | --- | --- |
| Lundi à vendredi, 7h43 (8h43 l'été) | **Point du matin** : actualités et dépôts SEC de tes actions, nouvelles déclarations des élus suivis, nouveau rapport 13F des fonds suivis | trader-news, trader-pelosi, trader-copycat |
| Lundi à vendredi, toutes les heures de 14h17 à 22h17 | **Alertes de prix** | trader-alerts |

Une issue n'est créée que s'il y a du nouveau. Chaque article, déclaration et alerte n'apparaît qu'une fois.
Les horaires GitHub peuvent avoir quelques minutes (parfois plus) de retard.

## Changer ce que tu suis : `suivi.json`

Ouvre `suivi.json`, clique sur le crayon, modifie, puis *Commit changes*.

```json
{
  "actions": ["AAPL", "MSFT", "KO", "JNJ"],
  "elus": ["Pelosi"],
  "fonds": [{"nom": "Berkshire Hathaway", "cik": "0001067983"}],
  "alertes": [
    {"type": "ouverture"},
    {"action": "AAPL", "type": "descend_a", "prix": 250},
    {"action": "MSFT", "type": "monte_a", "prix": 600},
    {"action": "KO", "type": "bouge_de", "pourcent": 3}
  ]
}
```

- **actions** : symboles américains suivis pour les actualités (et marqués ⭐ dans les déclarations du Congrès).
- **elus** : noms de famille (ou « Prénom Nom ») des membres de la Chambre, ou `["tous"]` pour toutes les
  déclarations (celles des 3 derniers jours, puis chaque nouvelle). `[]` = aucun suivi.
- **fonds** : nom libre + numéro CIK de la SEC. Exemples : Pershing Square `0001336528`,
  ARK `0001697748`, Markel `0001096343`, Akre `0001112520`, Oaktree `0000949509`.
- **alertes** (`[]` = aucune), types possibles :
  - `monte_a` + `prix` : le cours atteint ce prix ou plus ;
  - `descend_a` + `prix` : le cours atteint ce prix ou moins (`stop` fait pareil) ;
  - `bouge_de` + `pourcent` : variation depuis la clôture d'hier, au plus une fois par jour ;
  - `ouverture` : ouverture de la bourse de New York.
  - Option `"rearmer": true` : l'alerte peut sonner à nouveau quand le prix est revenu en arrière.
    Sinon elle sonne une seule fois. Option `"note": "mon stop"` : texte ajouté au message.

Attention aux virgules et aux guillemets : une erreur dans le fichier arrête la veille
(l'onglet *Actions* affiche alors une croix rouge).

## Réglage obligatoire une fois

*Settings → Secrets and variables → Actions → New repository secret* :
nom `SEC_USER_AGENT`, valeur `Ton Nom ton@email.com` (vrais nom et e-mail, la SEC l'exige).
Sans lui, les dépôts SEC et les 13F ne sont pas lus.

## Lancer à la main

Onglet *Actions* → *Point du matin* ou *Alertes de séance* → *Run workflow*.

## Fichiers

- `veille.py` : lance les skills et écrit le rapport en français.
- `suivi.json` : ce que tu suis.
- `etat/` : la mémoire (ce qui a déjà été vu, derniers cours). Ne pas modifier à la main.
- `.github/workflows/` : les horaires.

Les skills sont utilisés dans une version figée (commit `5189e79`) pour que rien ne change sans toi.
