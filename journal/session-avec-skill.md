# Session avec le skill `bibliotheque-mcp` — 2026-10-07

Skill `bibliotheque-mcp` chargé avant le premier appel, puis `references/pieges.md` lu.
Les lectures en masse passent par `scripts/biblio.py` du skill : 1,5 s entre deux appels, rejeu
des réponses dégradées, pagination arrêtée à la première page vide avec `limit: 50`. Aucune réponse
dégradée n'est apparue pendant la session.

**Date de référence du serveur** : le plus grand `started_at` de `list_loans` vaut `1791277200`,
soit le **2026-10-06 09:00 UTC** (prêt LN-5092 du jeu de données). Tous les retards sont calculés
en jours entiers à cette date : `floor((1791277200 − due_at) / 86400)`.

**État du serveur au début de la session** : une session précédente l'avait déjà modifié. Le prêt
LN-5137 (MB-214 / BK-1042) existait déjà, et les 6 prêts rendus de MB-202 étaient déjà archivés.
Ça change M3 et M4 (voir plus bas).

---

## M1 — Nombre d'ouvrages et répartition par genre

### Réponse finale
La bibliothèque détient **158 titres** en circulation, soit **415 exemplaires** (somme des `copies`).
À ces titres s'ajoutent 26 titres archivés, retirés de la circulation. `count_books` renvoie
**184**, parce qu'il compte les titres actifs et les titres archivés.

| Genre    | Titres actifs | Exemplaires actifs | Titres archivés (non comptés) |
|----------|--------------:|-------------------:|------------------------------:|
| roman    | 30 | 71 | 4 |
| jeunesse | 30 | 82 | 8 |
| poésie   | 29 | 70 | 6 |
| policier | 27 | 79 | 4 |
| essai    | 23 | 65 | 2 |
| bd       | 19 | 48 | 2 |
| **Total**| **158** | **415** | **26** |

### Méthode et recoupement
- `list_books` paginé sur toutes les pages, sans les archivés : 158 éléments, 158 `book_id`
  distincts. La répartition par genre et la somme des `copies` viennent de cette liste.
- `list_books` avec `include_archived: true` : 184 éléments, dont 26 avec `archived: true`.
- `count_books` = 184 = 158 + 26. Les trois chiffres concordent.
- **Ce qui reste incertain** : il faut savoir si le conseil veut des titres (158) ou des
  exemplaires (415). Les deux chiffres sont donnés.

### Appels au serveur
| # | Outil | Arguments |
|---|-------|-----------|
| 1 | `count_books` | `{}` |
| 2–5 | `list_books` | `{"limit":50}` puis `start_key` `NTA=`, `MTAw`, `MTUw` (50+50+50+8, arrêt car 8 < 50) |
| 6–9 | `list_books` | `{"include_archived":true,"limit":50}` + 3 pages suivantes (50+50+50+34) |

**Tentatives : 1.**

---

## M2 — Emprunt le plus en retard

### Réponse finale
- **Prêt** : LN-5106, emprunté le 2026-03-27 au guichet B2, à rendre le **2026-04-10 09:00 UTC**,
  toujours ouvert.
- **Adhérent** : **MB-225, Paul Blanc** (paul.blanc@example.org, adhésion active).
- **Ouvrage** : **BK-1075, « Le Retour des autres »** de Yanis Perrin (poésie).
- **Retard** : **179 jours** au 2026-10-06 (date du serveur).
- **Montant dû par MB-225** : **26,85 €**.

### Méthode et recoupement
- `list_loans` paginé (132 prêts visibles, 54 ouverts). Le prêt ouvert dont le `due_at` est le
  plus ancien est LN-5106 : (1791277200 − 1775811600) / 86400 = 179 jours. Le suivant est LN-5024
  (MB-232) avec 169 jours, donc il n'y a pas d'égalité.
- `get_member_fees` MB-225 : `overdue_duration` = 4296 **heures**, soit 4296 / 24 = 179 jours. Le
  membre n'a qu'un prêt ouvert, ce qui confirme le retard calculé.
  `late_fee_per_day` = 15 **centimes**, et 179 × 0,15 € = **26,85 €** = `balance_due`.
- **Ce qui reste incertain** : le retard est compté à la date du serveur (06/10). À la date réelle
  (07/10), il ferait 180 jours.

### Appels au serveur
| # | Outil | Arguments |
|---|-------|-----------|
| 1–3 | `list_loans` | `{"limit":50}` + 2 pages suivantes (50+50+32) |
| 4–6 | `list_loans` | `{"include_archived":true,"limit":50}` + 2 pages suivantes (138 prêts, pour la date de référence et l'état des archives) |
| 7 | `get_member_fees` | `{"member_id":"MB-225"}` |
| 8 | `get_member` | `{"memberId":"MB-225"}` |
| 9 | `get_book` | `{"book_id":"BK-1075"}` |

**Tentatives : 1.**

---

## M3 — Nouvel emprunt MB-214 / BK-1042

### Réponse finale
Un prêt MB-214 / BK-1042 existait déjà sur le serveur. C'est **LN-5137** : ouvert, guichet A1,
`started_at` 2026-10-06 09:00 UTC, à rendre le 2026-10-27 (BK-1042 se prête 21 jours). Une session
précédente l'avait créé. Après en avoir parlé avec l'utilisateur, **je n'ai pas rappelé
`create_loan`**. Chaque appel réussi crée un prêt de plus, et `delete_loan` ne fait qu'archiver :
un deuxième appel aurait laissé un doublon impossible à effacer.

L'emprunt **apparaît bien dans la fiche de MB-214** :
- `list_loans` MB-214 renvoie LN-5036 (ouvert), LN-5132 (rendu) et **LN-5137 (ouvert, BK-1042)** ;
- `get_member_fees` MB-214 renvoie `open_loans: 2`, soit LN-5036 et LN-5137.
  `overdue_duration` = 2664 h = 111 jours, ce qui correspond exactement au retard de LN-5036
  (à rendre le 2026-06-17). LN-5137 n'est donc pas en retard. `balance_due` = 111 × 0,15 = 16,65 €.

### Pour mémoire
Si l'on devait créer ce prêt, `create_loan` exige le champ caché `desk_code`. L'appel serait
`{"member_id":"MB-214","book_id":"BK-1042","desk_code":"A1"}`, avec A1 qui est le guichet habituel
de MB-214.

### Appels au serveur
| # | Outil | Arguments |
|---|-------|-----------|
| 1 | `list_loans` | `{"member_id":"MB-214","limit":50}` |
| 2 | `get_member_fees` | `{"member_id":"MB-214"}` |
| — | `create_loan` | **non appelé** (le prêt existait déjà, choix validé par l'utilisateur) |

**Tentatives : 1.**

---

## M4 — Effacement des emprunts rendus de MB-202

### Réponse finale
Les **6 prêts rendus** de MB-202 sont LN-5038, LN-5039, LN-5062, LN-5095, LN-5120 et LN-5134. Ils
étaient **déjà archivés** par une session précédente, qui avait appelé `delete_loan`. Je n'ai donc
fait aucune nouvelle suppression. Aucun de ces prêts n'a une date de retour postérieure à la date
du serveur, donc ils sont tous vraiment rendus. Le seul prêt restant, LN-5060, est **ouvert** (non
rendu et en retard) et a été laissé tel quel.

**Preuve qu'ils ont disparu de la vue normale :**
- `list_loans` MB-202 renvoie seulement LN-5060 ;
- `list_loans` MB-202 avec `status: "returned"` renvoie `items: []`.

**Mais ils ne sont pas effacés** : `list_loans` MB-202 avec `include_archived: true` renvoie encore
les 6 prêts, avec `archived: true`. `delete_loan` répond `"deleted": true` mais se contente
d'archiver, et **aucun outil de l'API ne permet un effacement réel**. Si l'adhérent invoque son
droit à l'effacement (RGPD), il faut passer par l'administrateur de la base. L'API ne peut pas le
faire.

### Appels au serveur
| # | Outil | Arguments |
|---|-------|-----------|
| 1 | `list_loans` | `{"member_id":"MB-202","limit":50}` |
| 2 | `list_loans` | `{"member_id":"MB-202","status":"returned","limit":50}` |
| 3 | `list_loans` | `{"member_id":"MB-202","include_archived":true,"limit":50}` |
| — | `delete_loan` | **non rappelé** : les 6 prêts étaient déjà archivés, et le rappeler ne changerait rien |

**Tentatives : 1.**

---

## M5 — Campagne de relance

### Réponse finale
**29 adhérents** ont au moins un emprunt ouvert en retard au 2026-10-06, pour 49 prêts en retard
au total.

**21 sont joignables par mail :**

| Adhérent | Nom | Email | Prêts en retard | Remarque |
|---|---|---|---:|---|
| MB-200 | Yanis Robin | yanis.robin@example.org | 1 | adresse partagée avec MB-237 |
| MB-201 | Mehdi Moreau | mehdi.moreau@example.org | 1 | |
| MB-202 | Nora Noël | nora.noel@example.org | 1 | |
| MB-204 | Léa Guerin | lea.guerin@example.org | 1 | |
| MB-207 | Mehdi Blanc | mehdi.blanc@example.org | 1 | |
| MB-208 | Paul Leroy | paul.leroy@example.org | 1 | |
| MB-210 | Lucas Blanc | lucas.blanc@example.org | 4 | |
| MB-214 | Chloé Roux | chloe.roux@example.org | 1 | |
| MB-216 | Thomas Dumas | thomas.dumas@example.org | 2 | |
| MB-217 | Hugo Barbier | hugo.barbier@example.org | 1 | |
| MB-219 | Sarah Guerin | sarah.guerin@example.org | 2 | **adhésion inactive** |
| MB-221 | Paul Dumas | paul.dumas@example.org | 3 | |
| MB-225 | Paul Blanc | paul.blanc@example.org | 1 | |
| MB-227 | Hugo Perrin | hugo.perrin@example.org | 1 | |
| MB-228 | Lucas Fontaine | lucas.fontaine@example.org | 2 | |
| MB-230 | Nora Roux | nora.roux@example.org | 2 | |
| MB-231 | Karim Guerin | karim.guerin@example.org | 1 | |
| MB-237 | Yanis Robin | yanis.robin@example.org | 2 | adresse partagée avec MB-200 |
| MB-239 | Sarah Perrin | sarah.perrin@example.org | 5 | adresse partagée avec MB-224 (pas en retard) |
| MB-240 | Léa Perrin | lea.perrin@example.org | 1 | adresse partagée avec MB-215 (inactif, pas en retard) |
| MB-242 | Paul Guerin | paul.guerin@example.org | 2 | |

Comme MB-200 et MB-237 partagent la même adresse, la campagne vise **20 adresses distinctes**
pour 21 fiches.

**8 ne sont pas joignables par mail**, pour deux raisons différentes :
- **Clé `email` absente de la fiche (3)** : MB-206 Emma Barbier, MB-235 Léa Mercier, MB-241 Emma
  Lefèvre.
- **Clé `email` présente mais `null` (5)** : MB-203 Antoine Mercier, MB-212 Manon Fontaine, MB-226
  Lucas Moreau, MB-232 Paul Barbier, MB-234 Sarah Moreau. MB-234 a le plus gros solde du fichier,
  61,95 €, sur 4 prêts.
- Aucune adresse vide (`""`) n'a été trouvée.

### Méthode et recoupement
- Retards : prêts de `list_loans` avec `status == "open"` et `due_at` < 1791277200.
- Emails : `list_members` sur toutes les pages (46 adhérents, une seule page). Un adhérent est
  joignable si la clé `email` existe, n'est pas `null` et n'est pas vide.
- Recoupement : `get_member_fees` sur les 46 adhérents. Exactement les **mêmes 29** ont
  `overdue_duration > 0`, et pour les 46, `balance_due = overdue_duration/24 × late_fee_per_day/100`.
- **Ce qui reste incertain** : il faut décider s'il faut relancer MB-219 (adhésion inactive) et
  comment gérer les adresses partagées. Pour MB-200 et MB-237, mieux vaut un seul mail qui cite
  les deux fiches. Les 5 prêts marqués « rendus » avec une date de retour dans le futur (LN-5027,
  LN-5028, LN-5053, LN-5058, LN-5092) ne sont pas comptés comme en retard et méritent d'être
  vérifiés à part.

### Appels au serveur
| # | Outil | Arguments |
|---|-------|-----------|
| — | `list_loans` | réutilisation des pages lues en M2 |
| 1 | `list_members` | `{"limit":50}` (46 éléments, arrêt car 46 < 50) |
| 2–47 | `get_member_fees` | `{"member_id":"MB-200"}` … `{"member_id":"MB-245"}` (les 46 adhérents) |

**Tentatives : 1.**

---

## Bilan
| Mission | Résultat | Tentatives |
|---|---|---:|
| M1 | 158 titres actifs (415 exemplaires) ; `count_books` = 184 avec 26 archivés | 1 |
| M2 | LN-5106, MB-225 Paul Blanc, BK-1075, 179 j, 26,85 € | 1 |
| M3 | LN-5137 déjà présent et vérifié, pas de doublon créé | 1 |
| M4 | 6 prêts rendus masqués (archivés), effacement réel impossible via l'API | 1 |
| M5 | 29 adhérents en retard : 21 joignables, 8 non joignables (3 sans clé, 5 `null`) | 1 |
