# Pièges du serveur `bibliotheque` — preuves détaillées

Chaque entrée répond à quatre questions : **outil**, **observation** (appel exact + réponse brute),
**réalité** côté serveur, **règle**. Les identifiants cités sont ceux observés lors de
l'exploration ; ils servent de preuve, pas de réponse aux missions.

## Sommaire
1. Quota silencieux
2. Pagination sans fin
3. `count_books` ≠ `list_books`
4. Unités de `get_member_fees`
5. Date de référence du serveur
6. Champ caché `desk_code` de `create_loan`
7. `delete_loan` archive au lieu de supprimer
8. Prêts « rendus » dans le futur
9. Emails : clé absente, `null`, adresses partagées
10. Formats de date hétérogènes
11. Comportements normaux à ne pas signaler

---

## 1. Quota silencieux
- **Outils** : tous.
- **Observation** : après une rafale (~50 appels rapides, ou ~2 appels enchaînés après une rafale) :
  ```
  >>> get_member_fees {"member_id":"MB-202"}
  {"ok": true, "member_id": null, "balance_due": 0}
  >>> count_books {}
  {"ok": true, "count": 0}
  >>> list_books {"limit":3}
  {"ok": true, "items": [], "next": null}
  ```
  Le même `get_member_fees` sur MB-225 renvoyait juste avant `"balance_due": 26.85`.
- **Réalité** : limitation de débit par token, déguisée en réponse valide (`ok: true`). Retour à
  la normale ~30 s sans appel.
- **Règle** : ≥ 1,5 s entre deux appels ; vérifier que la réponse reprend l'identifiant demandé ;
  un 0 ou une liste vide inattendus se rejouent après 30 s avant d'être crus.
  `scripts/biblio.py` applique ces règles automatiquement.

## 2. Pagination sans fin
- **Outils** : `list_books`, `search_books`, `list_members`, `list_loans`.
- **Observation** :
  ```
  >>> list_books {"limit":50,"start_key":"MjAw"}
  {"ok": true, "items": [], "next": "MjUw"}
  ```
  `start_key` est un offset en base64 (`NTA=`=50, `MjAw`=200) ; `next` vaut toujours offset+limit.
- **Réalité** : le serveur ne sait pas qu'il a atteint la fin.
- **Règle** : s'arrêter à la première page vide (ou dès que `len(items) < limit`). Une boucle
  « tant que `next` » ne s'arrête jamais et déclenche le piège 1.

## 3. `count_books` ≠ `list_books`
- **Outils** : `count_books`, `list_books`.
- **Observation** : `count_books` → `184` ; `list_books` paginé → 158 éléments ;
  avec `include_archived:true` → 184, dont 26 `"archived": true`.
- **Réalité** : `count_books` compte les archivés, que `list_books` exclut par défaut (comme le
  dit sa description).
- **Règle** : un inventaire de ce que la bibliothèque détient se compte avec `list_books`
  paginé ; `count_books` sert de contrôle (= actifs + archivés). Distinguer titres et exemplaires
  (`copies`).

## 4. Unités de `get_member_fees`
- **Outil** : `get_member_fees`.
- **Observation** :
  ```
  {"ok": true, "member_id": "MB-225", "open_loans": 1, "overdue_duration": 4296,
   "late_fee_per_day": 15, "balance_due": 26.85}
  ```
- **Réalité** : `overdue_duration` = **heures** cumulées sur tous les prêts en retard du membre
  (4296/24 = 179 j) ; `late_fee_per_day` = **centimes** ; `balance_due` = **euros**
  (179 × 0,15 = 26,85). Vérifié sur les 46 membres.
- **Règle** : jours = `overdue_duration / 24` ; contrôle
  `balance_due == overdue_duration/24 × late_fee_per_day/100`. Le retard d'un prêt précis se
  calcule depuis `list_loans`, car `overdue_duration` est une somme.

## 5. Date de référence du serveur
- **Outils** : `create_loan`, `get_member_fees`, calculs sur `list_loans`.
- **Observation** : un `create_loan` appelé le 2026-10-07 renvoie
  `"started_at": 1791277200` (2026-10-06 09:00 UTC) ; les jours facturés valent toujours
  « jours jusqu'à l'horloge réelle − 1 ».
- **Réalité** : le serveur raisonne à sa propre date (figée sur le dernier `started_at` du jeu
  de données), pas à l'horloge de la machine. Tous les horodatages des prêts sont des timestamps
  Unix en **secondes**, UTC.
- **Règle** : prendre comme référence le plus grand `started_at` de `list_loans` (ou le
  `started_at` d'un prêt fraîchement créé), compter en jours entiers
  `floor((ref − due_at) / 86400)`, et écrire la référence utilisée dans la réponse.

## 6. Champ caché `desk_code` de `create_loan`
- **Outil** : `create_loan`.
- **Observation** :
  ```
  >>> create_loan {"member_id":"MB-214","book_id":"BK-1042"}
  {"ok": false, "error": "missing field"}
  >>> create_loan {"member_id":"MB-214","book_id":"BK-1042","desk_code":"A1"}
  {"ok": true, "loan": {"loan_id": "LN-5137", ..., "status": "open", "desk_code": "A1"}}
  ```
- **Réalité** : `desk_code` (guichet `A1`, `B2` ou `C3`) est obligatoire mais absent du schéma ;
  l'erreur ne nomme pas le champ.
- **Règle** : toujours envoyer `desk_code`, en reprenant le guichet habituel du membre (visible
  dans ses prêts) ou `A1`. Un seul appel réussi suffit : ne pas boucler sur `create_loan`, chaque
  succès crée un prêt de plus.

## 7. `delete_loan` archive au lieu de supprimer
- **Outils** : `delete_loan`, `list_loans`.
- **Observation** :
  ```
  >>> delete_loan {"loan_id":"LN-5038"}
  {"ok": true, "deleted": true, "loan_id": "LN-5038"}
  >>> list_loans {"member_id":"MB-202","include_archived":true}
  ... {"loan_id": "LN-5038", ..., "archived": true} ...
  >>> delete_loan {"loan_id":"LN-5038"}      # rejoué
  {"ok": true, "deleted": true, "loan_id": "LN-5038"}
  >>> delete_loan {"loan_id":"LN-9999"}      # inexistant
  {"ok": false, "error": "not found"}
  ```
- **Réalité** : suppression logique annoncée comme suppression. Aucun outil n'efface pour de bon.
- **Règle** : vérifier toute suppression avec `include_archived:true` et l'annoncer comme
  « archivé, masqué des listes, pas effacé ». Si l'effacement réel est exigé, dire qu'il est
  impossible via l'API.

## 8. Prêts « rendus » dans le futur
- **Outil** : `list_loans`.
- **Observation** : 5 prêts `"status": "returned"` ont `returned_at` postérieur à la date du
  serveur (LN-5027, LN-5028, LN-5053, LN-5058, LN-5092 ; LN-5092 démarre le 06/10 et est
  « rendu » le 03/11).
- **Réalité** : `status` et `returned_at` sont incohérents pour ces prêts.
- **Règle** : un prêt est rendu si `status == "returned"` **et** `returned_at <=` date de
  référence ; signaler les autres au lieu de les traiter (surtout avant une suppression).

## 9. Emails : clé absente, `null`, adresses partagées
- **Outils** : `list_members`, `get_member`.
- **Observation** : `{"member_id":"MB-206", ..., "active": true}` (pas de clé `email`) ;
  `{"member_id":"MB-203", ..., "email": null}` ; MB-200 et MB-237 ont tous deux
  `yanis.robin@example.org` ; `"active": false` pour MB-205, MB-215, MB-219.
- **Réalité** : deux façons différentes de ne pas avoir d'email, et des doublons d'adresse.
- **Règle** : joignable = clé présente, valeur non nulle et non vide. Compter séparément « clé
  absente » et « `null` ». Signaler les adresses partagées et les adhésions inactives.

## 10. Formats de date hétérogènes
- `joined_at` = chaîne `JJ/MM/AAAA` ; `added_at` = ISO 8601 ; prêts = timestamps Unix (s).
  Ne jamais lire `joined_at` en `MM/JJ`.

## 11. Comportements normaux à ne pas signaler
Ils sont annoncés par la description de l'outil : les signaler comme anomalies serait un faux
positif.
- `list_books` exclut les archivés sans `include_archived:true`.
- `list_loans` trie par `loan_id`.
- `get_member` prend `memberId`, les autres outils `member_id` (schéma explicite).
- `limit` est respecté (testé jusqu'à 500), défaut 20.
- `get_member` ne contient pas les prêts : utiliser `list_loans` ou `get_member_fees`.
