---
name: bibliotheque-mcp
description: Pièges et règles d'usage du serveur MCP "bibliotheque" (médiathèque municipale, outils list_books, count_books, list_members, list_loans, get_member_fees, create_loan, delete_loan, get_mission...). À charger AVANT tout appel à ce serveur : pagination, quota silencieux, unités des frais, date de référence, champ caché de create_loan, emails absents.
---

# Serveur MCP `bibliotheque` — mode d'emploi et pièges

Cette API ne signale presque jamais ses erreurs : elle renvoie `"ok": true` avec des données
vides ou fausses. **Règle générale : un appel sans erreur n'est pas un appel qui a marché.**
Lis toujours le JSON brut et recoupe chaque chiffre par un second chemin.

## Ce qui est normal (documenté dans la description des outils — ce ne sont PAS des pièges)

- `list_books` exclut les ouvrages archivés sauf `include_archived: true`.
- `list_loans` renvoie les prêts triés par `loan_id` ; filtres `member_id`, `status` (`open`/`returned`).
- `get_member` prend `memberId` (camelCase), tous les autres outils prennent `member_id`.
- `limit` vaut 20 par défaut et est respecté (testé jusqu'à 500).

## Pièges

### 1. Quota silencieux : réponses vides ou nulles au lieu d'une erreur
- **Outils** : tous (observé sur `count_books`, `list_*`, `get_*`, `get_member_fees`).
- **Observation** : après une rafale d'appels, `count_books` → `{"ok":true,"count":0}`,
  `list_*` → `{"ok":true,"items":[],"next":null}`, `get_member`/`get_book` → `null`,
  `get_member_fees` → `{"ok":true,"member_id":null,"balance_due":0}`.
- **Réalité** : le serveur limite le débit par token et, au lieu d'un 429, renvoie des données
  « vides » plausibles. Retour à la normale après ~30 s sans appel.
- **Règle** :
  - Espace les appels (≥ 1,5 s entre deux appels ; aucune boucle serrée).
  - Vérifie que la réponse **reprend l'identifiant demandé** (`member_id`, `book_id`...) et
    qu'un total ne tombe pas à 0 sans raison. Sinon : attendre 30 s et rejouer.
  - Ne conclus jamais « catalogue vide », « aucun prêt » ou « rien à payer » sur une seule réponse.

### 2. Pagination sans fin : `next` n'est jamais `null`
- **Outils** : `list_books`, `search_books`, `list_members`, `list_loans`.
- **Observation** : `start_key` = offset en base64 (`"NTA="` = 50, `"MjAw"` = 200). Après la
  dernière donnée, le serveur renvoie `"items": []` **avec un `next` non nul**, à l'infini
  (même avec un filtre qui tient sur une page).
- **Réalité** : `next` est calculé comme `offset + limit` sans tenir compte de la fin des données.
- **Règle** : arrête la pagination **à la première page vide** (ou quand `len(items) < limit`).
  Suivre `next` jusqu'à `null` = boucle infinie → déclenche le piège 1 → données vides.
  Utilise `limit: 50` pour réduire le nombre d'appels.

### 3. `count_books` compte les archivés, `list_books` non
- **Outils** : `count_books` vs `list_books`.
- **Observation** : `count_books` → 184 ; `list_books` (toutes pages) → 158.
- **Réalité** : `count_books` compte aussi les 26 ouvrages archivés (retirés de la circulation) ;
  `list_books` avec `include_archived: true` en renvoie bien 184.
- **Règle** : pour « ce que détient la bibliothèque », compter via `list_books` paginé (sans
  archivés) et utiliser `count_books` seulement comme contrôle (= actifs + archivés).
  Préciser aussi titres (`book_id`) vs exemplaires (somme de `copies`).

### 4. `get_member_fees` : trois unités différentes, non documentées
- **Outil** : `get_member_fees`.
- **Observation** : `{"open_loans":1,"overdue_duration":4296,"late_fee_per_day":15,"balance_due":26.85}`.
- **Réalité** : `overdue_duration` est en **heures** (4296 h = 179 jours, somme sur tous les
  prêts en retard du membre) ; `late_fee_per_day` est en **centimes** (0,15 €) ;
  `balance_due` est en **euros** = jours × 0,15.
- **Règle** : jours de retard = `overdue_duration / 24` ; ne jamais présenter 4296 comme des
  jours ni 15 comme des euros. Contrôle : `balance_due == overdue_duration/24 × late_fee_per_day/100`.
  Pour le retard d'**un** prêt précis, le calculer depuis `list_loans` (voir piège 5).

### 5. Le serveur vit au 2026-10-06 09:00 UTC, pas à l'horloge réelle
- **Outils** : `get_member_fees`, `create_loan`, `list_loans`.
- **Observation** : `create_loan` crée un prêt avec `started_at = 1791277200`
  (2026-10-06 09:00 UTC) même quand on l'appelle le 07/10 ; les jours facturés par
  `get_member_fees` valent toujours (jours calendaires vs horloge réelle) − 1.
- **Réalité** : la date de référence du serveur est figée/décalée ; `due_at`, `started_at`,
  `returned_at` sont des **timestamps Unix en secondes** (UTC).
- **Règle** : calculer les retards par rapport à la date du serveur
  (= `started_at` d'un prêt fraîchement créé, ou le max des `started_at`), en jours entiers :
  `floor((ref - due_at) / 86400)`. Indiquer la référence utilisée dans la réponse.

### 6. `create_loan` exige un champ caché `desk_code`
- **Outil** : `create_loan`.
- **Observation** : avec exactement les champs du schéma (`member_id`, `book_id`) →
  `{"ok":false,"error":"missing field"}` sans dire lequel.
- **Réalité** : le serveur exige aussi `desk_code` (guichet : `A1`, `B2` ou `C3`, visible dans
  chaque prêt de `list_loans`).
- **Règle** : `create_loan({member_id, book_id, desk_code})` — reprendre le `desk_code` habituel
  du membre (ses prêts précédents) ou `A1`. Vérifier ensuite par
  `list_loans({member_id, status:"open"})` **et** `get_member_fees` (`open_loans` +1).
  `get_member` ne montre pas les prêts : ce n'est pas une preuve.

### 7. Prêts « rendus » avec une date de retour dans le futur
- **Outil** : `list_loans`.
- **Observation** : 5 prêts `status:"returned"` ont `returned_at` après la date du serveur
  (LN-5027, LN-5028, LN-5053, LN-5058, LN-5092 — ex. LN-5092 démarré le 06/10, « rendu » le 03/11).
- **Réalité** : `status` et `returned_at` ne sont pas cohérents ; `returned_at` semble recopier
  `due_at` ou une date prévisionnelle.
- **Règle** : un prêt n'est réellement rendu que si `status=="returned"` **et**
  `returned_at <= date serveur`. Signaler ces prêts au lieu de les traiter silencieusement
  (ex. avant de les supprimer comme « déjà rendus »).

### 7 bis. `delete_loan` ne supprime pas : il archive
- **Outils** : `delete_loan`, `list_loans`.
- **Observation** : `delete_loan({loan_id:"LN-5038"})` → `{"ok":true,"deleted":true,"loan_id":"LN-5038"}`.
  Le prêt disparaît de `list_loans` par défaut… mais `list_loans({include_archived:true})` le
  renvoie toujours, avec `"archived": true`. Un second `delete_loan` sur le même id répond encore
  `"deleted": true` et ne change rien. (Un id inexistant, lui, répond bien `"error":"not found"`.)
- **Réalité** : suppression logique (soft delete) présentée comme une suppression ; aucun outil
  ne permet l'effacement définitif.
- **Règle** : ne jamais prouver une suppression avec la seule vue par défaut. Vérifier avec
  `include_archived: true` et annoncer honnêtement « archivé (masqué), pas effacé ». Si
  l'effacement réel est exigé (ex. RGPD), le signaler comme impossible via l'API.

### 8. Emails : champ absent ≠ `null`, et adresses partagées
- **Outils** : `list_members`, `get_member`.
- **Observation** : certains membres n'ont **pas de clé** `email`, d'autres ont `"email": null`.
  Des membres distincts partagent la même adresse (MB-200/MB-237, MB-215/MB-240, MB-224/MB-239).
  `active:false` existe (MB-205, MB-215, MB-219).
- **Règle** : un membre est joignable si `email` est présent, non nul, non vide. Compter à part
  « champ absent » et « null ». Dédoublonner les adresses avant un envoi. Signaler les membres
  inactifs plutôt que de les mélanger aux actifs.

### 9. Formats de date hétérogènes
- `joined_at` (membres) = chaîne `JJ/MM/AAAA` ; `added_at` (livres) = ISO 8601 ;
  prêts = timestamps Unix en secondes. Ne pas parser `joined_at` en `MM/JJ`.

## Recettes des missions

- **Inventaire** : `list_books` paginé (règle 2) sans et avec `include_archived`, dédoublonner par
  `book_id`, compter par `genre` (titres et `copies`), contrôler avec `count_books` (règle 3).
- **Retard max** : `list_loans({status:"open"})` paginé, min de `due_at`, retard calculé
  selon la règle 5 ; montant = `get_member_fees.balance_due` (euros), décodé selon la règle 4.
- **Nouvel emprunt** : règle 6, puis double vérification.
- **Suppression des prêts rendus** : lister `list_loans({member_id, status:"returned", include_archived:true})`,
  exclure les retours « futurs » (règle 7), ne jamais toucher aux prêts `open`, supprimer un par
  un en espaçant les appels, puis vérifier avec la vue par défaut (disparus) **et** avec
  `include_archived:true` (toujours là, `archived:true` — règle 7 bis), en vérifiant que la réponse
  n'est pas dégradée (règle 1). Annoncer « archivés, pas effacés ».
- **Relance** : prêts ouverts avec `due_at < date serveur`, joindre `list_members`, classer
  selon la règle 8.
