---
name: bibliotheque-mcp
description: Mode d'emploi du serveur MCP "bibliotheque" (médiathèque municipale) et de ses pièges non documentés. Utilise ce skill dès qu'une tâche touche à ce serveur ou à ses outils (list_books, count_books, search_books, list_members, get_member, list_loans, get_member_fees, create_loan, delete_loan, list_missions, get_mission), ou dès qu'on parle d'inventaire du catalogue, d'emprunts, de retards, d'amendes, d'adhérents à relancer, de création ou de suppression de prêts à la médiathèque, même si le serveur n'est pas cité. Le charger avant le premier appel, car l'API renvoie ok:true avec des données fausses ou vides.
---

# Serveur MCP `bibliotheque`

Cette API a une douzaine d'années et aucune documentation. Son défaut principal est de **ne
jamais avouer un échec** : quota dépassé, pagination terminée, suppression partielle, tout
revient avec `"ok": true`. Une réponse sans erreur n'est donc pas une réponse juste. Ce skill
liste ce qu'elle fait réellement, pour que tu réussisses du premier coup au lieu de conclure sur
des données vides.

Le détail de chaque piège (appel exact, réponse brute, explication) est dans
`references/pieges.md`. Lis-le dès qu'une réponse te surprend, et avant toute écriture
(`create_loan`, `delete_loan`).

## Les réflexes qui évitent presque tous les pièges

**1. Va lentement, et vérifie que la réponse n'est pas vide « par politesse ».**
Au-delà d'environ un appel par seconde, le serveur ne renvoie pas d'erreur : il renvoie des
données vides (`count: 0`, `items: []`, `member_id: null`, `balance_due: 0`). Laisse au moins
1,5 s entre deux appels. Si un total tombe à 0 ou si la réponse ne reprend pas l'identifiant que
tu as demandé, attends 30 s et rejoue avant de croire le résultat. Sinon, tu risques de dire à
quelqu'un qu'il ne doit rien ou que le catalogue est vide.

**2. Arrête la pagination à la première page vide.**
`next` n'est jamais `null`. C'est un simple décalage en base64 qui continue de grandir après la
dernière donnée. Une boucle « tant qu'il y a un `next` » ne s'arrête jamais et déclenche le
réflexe 1. Utilise `limit: 50` et arrête-toi dès que `items` est vide ou plus court que `limit`.

**3. Recoupe chaque chiffre par un deuxième chemin.**
Les outils ne comptent pas tous la même chose : `count_books` inclut les archivés, alors que
`list_books` les exclut. Les frais de `get_member_fees` se recalculent à partir de
`list_loans`. Les prêts créés se vérifient avec `list_loans` **et** `get_member_fees`
(`open_loans`). Quand deux chemins ne donnent pas le même chiffre, c'est là que se cache le
piège.

**4. Lis les unités, pas seulement les nombres.**
Dans `get_member_fees`, `overdue_duration` est en **heures** (cumulées sur tous les prêts en
retard), `late_fee_per_day` en **centimes** et `balance_due` en **euros**. Contrôle :
`balance_due = overdue_duration/24 × late_fee_per_day/100`.

**5. Raisonne à la date du serveur, pas à la tienne.**
Le serveur vit à la date de son jeu de données : un prêt créé aujourd'hui reçoit le
`started_at` du dernier jour du jeu. Les horodatages des prêts sont des timestamps Unix en
secondes (UTC). Pour un retard, prends comme référence le plus grand `started_at` de
`list_loans`, compte en jours entiers et indique cette référence dans ta réponse.

## Avant une écriture

- **`create_loan`** exige un champ `desk_code` (`A1`, `B2` ou `C3`) absent de son schéma.
  Sans lui, la réponse est `missing field`, sans dire lequel. Reprends le guichet habituel de
  l'adhérent (visible dans ses prêts), sinon `A1`. N'appelle `create_loan` qu'une seule fois :
  chaque succès crée un prêt de plus.
- **`delete_loan`** répond `"deleted": true` mais se contente d'**archiver** le prêt : il
  disparaît de la vue par défaut et reste visible avec `include_archived: true`. Aucun outil
  n'efface pour de bon. Vérifie toujours avec `include_archived: true` et dis honnêtement
  « archivé, pas effacé ». Si l'utilisateur veut un vrai effacement (droit à l'oubli), dis-lui
  que l'API ne le permet pas.
- Un prêt est rendu si `status == "returned"` **et** si son `returned_at` n'est pas postérieur à
  la date du serveur. Certains prêts portent une date de retour dans le futur : signale-les
  plutôt que de les supprimer.

## Données des adhérents

Un adhérent sans email apparaît sous deux formes : la clé `email` est **absente**, ou elle vaut
**`null`**. Compte ces deux cas séparément quand on te demande de « distinguer les cas ».
Certaines adresses sont partagées par plusieurs fiches, et certaines adhésions sont inactives
(`active: false`) : signale-le. `joined_at` est au format `JJ/MM/AAAA`.

## Ce qui est normal (à ne pas signaler comme anomalie)

Ces comportements sont annoncés dans la description des outils. Les dénoncer serait une erreur :
- `list_books` exclut les archivés sans `include_archived: true` ;
- `list_loans` trie par `loan_id` ;
- `get_member` prend `memberId` alors que les autres outils prennent `member_id` ;
- `limit` vaut 20 par défaut et il est respecté ;
- `get_member` ne contient pas les prêts.

## Outil d'appoint pour les lectures en masse

Pour lire tout le catalogue ou les frais de tous les adhérents, `scripts/biblio.py` applique déjà
les réflexes 1 et 2 : appels espacés, réponses dégradées rejouées, pagination arrêtée à la
première page vide. Il lit le token dans `BIBLIO_TOKEN`, ou dans `.env`.

```bash
python .claude/skills/bibliotheque-mcp/scripts/biblio.py all list_loans '{"status":"open"}'
python .claude/skills/bibliotheque-mcp/scripts/biblio.py call get_member_fees '{"member_id":"MB-225"}'
```

## Rendre compte

Pour chaque résultat, donne :
1. le chiffre ou l'action ;
2. le chemin suivi (outils et filtres) ;
3. le recoupement fait ;
4. ce qui reste incertain.

Une phrase du type « N titres actifs (`list_books`, toutes pages), confirmés par
`count_books` = N + archivés » vaut mieux qu'un chiffre seul.
