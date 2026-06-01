# Research Agenda — dev-fingerprint

> **Question centrale** :
> Peut-on estimer P(activité compatible avec assistance IA | historique Git observé)
> de façon statistiquement défendable, sans ground truth massif ?

Ce document formalise les hypothèses, les signaux prometteurs, les expériences
à conduire et les risques d'échec. Il correspond à la Partie 8 du protocole
de recherche initial.

---

## 1. Hypothèses de travail

Les hypothèses sont ordonnées par testabilité décroissante et falsifiabilité croissante.

### H1 — Changement de granularité des commits *(Niveau A, testable)*

**Mécanisme** : un assistant IA abaisse le coût cognitif de la génération de code.
Le développeur soumet des batchs plus grands (plus de fichiers, plus de lignes nettes)
parce que la barrière "écrire ce morceau de code" a été levée.

**Signal** : `large_commit_ratio` ↑, `median_files_per_commit` ↑,
`cross_module_ratio` ↑.

**Falsifiabilité** : si un développeur utilisant massivement Copilot depuis 3 ans
ne montre aucun changement dans ces signaux par rapport à sa baseline pré-IA,
H1 est falsifié pour ce profil. Deux falsifications indépendantes invalident H1
comme signal universel.

**Confondants principaux** : changement de rôle (lead → core contributor),
migration vers un nouveau framework (coûts d'adaptation initiaux),
passage d'une phase d'exploration à une phase de stabilisation.

---

### H2 — Changement de vélocité et de rythme *(Niveau A, testable)*

**Mécanisme** : l'assistance IA réduit le temps de latence cognitive entre
"identifier le problème" et "avoir le code". La vitesse d'itération augmente,
mais le pattern temporel peut aussi devenir moins régulier (sessions longues
d'utilisation intensive alternant avec des périodes sans IA).

**Signal** : `commits_per_week` ↑, `median_inter_commit_hours` ↓ ou pattern
bimodal (très courts + très longs inter-commit).

**Prédiction différenciée** : l'assistant IA ne produit pas nécessairement plus de
commits — il peut produire des commits plus rares et plus volumineux (H1 et H2
ne sont pas contradictoires). La combinaison est ce qui est discriminant.

**Falsifiabilité** : si `median_inter_commit_hours` ne change pas de façon
cohérente dans un groupe de développeurs déclarés (ground truth positif),
H2 est rejeté comme signal universel.

---

### H3 — Disparition du refactoring organique *(Niveau A, hypothèse forte)*

**Mécanisme** : le refactoring spontané (réécrire ce qu'on vient d'écrire parce
qu'on a eu une meilleure idée) diminue avec l'IA, car le LLM produit souvent
une version déjà "propre" dès la première génération. En revanche, le refactoring
assisté par IA (prompt "refactore ce module") peut augmenter.

**Signal complexe** : `refactor_ratio` peut augmenter ou diminuer selon le workflow.
Ce signal nécessite une décomposition plus fine :
- Refactoring de petite taille (< 50 lignes de churn) : probablement humain
- Refactoring de grande taille (> 200 lignes de churn, net ≈ 0) : compatible IA

**À développer** : distinguer `refactor_small_ratio` et `refactor_large_ratio`
comme signaux séparés dans `BehaviorWindow`.

---

### H4 — Changement du ratio test-code *(Niveau B)*

**Mécanisme** : les workflows TDD strictement humains produisent des commits
test-avant-code. Les assistants IA génèrent souvent du code + tests en un seul
bloc, ou génèrent les tests après si on le demande explicitement.

**Prédiction** : `test_touch_ratio` ne change pas nécessairement, mais le
**délai** entre le premier commit d'un feature et l'apparition des tests associés
pourrait changer. Ce signal est non disponible sans analyse de la structure
commit-par-commit d'une PR.

**Limitation actuelle** : `test_touch_ratio` mesure si des tests sont touchés
dans un commit, pas l'ordre de création. Ce signal est donc un proxy très indirect.

---

### H5 — Homogénéisation du style entre projets *(Niveau C, hypothèse faible)*

**Mécanisme** : sans IA, un développeur produit du code dont le style varie
selon le projet (conventions d'équipe, phase du projet, type de tâche).
Avec IA, le LLM impose sa propre distribution stylistique, réduisant la variance
inter-projet.

**Problème** : cette hypothèse est difficilement testable sans comparer plusieurs
repos du même développeur. Elle relève du Niveau C (style) et souffre des mêmes
biais de confondant.

**Décision** : ne pas implémenter H5 comme signal primaire. Garder comme
expérience exploratoire uniquement.

---

## 2. Signaux à développer (feuille de route)

### Priorité 1 — Signaux de processus haute valeur (Niveau A)

| Signal | Description | Motivation |
|--------|-------------|------------|
| `refactor_large_ratio` | Fraction de commits : churn > 200 et |net| < 10% | Distingue le refactoring IA-scale du micro-refactoring |
| `session_commit_burst` | Fraction de commits en rafale (< 30 min inter-commit) | Signature d'une session intensive IA |
| `commit_time_entropy` | Entropie de la distribution des heures de commit | IA tend à normaliser les horaires de travail |
| `pr_size_gini` | Coefficient de Gini sur les tailles de PRs | IA produit des PRs plus uniformes |
| `issue_to_first_commit_hours` | Latence issue-ouverte → premier commit | Réduction possible avec IA |

**Note** : `session_commit_burst` et `commit_time_entropy` nécessitent des données
horodatées à la minute, disponibles dans l'API GitHub. Non disponibles dans les
données actuelles (`reports/real/`).

### Priorité 2 — Signaux de cohérence cross-commit (Niveau B)

| Signal | Description | Motivation |
|--------|-------------|------------|
| `hunk_self_containment` | Fraction de hunks qui constituent des unités logiques complètes | IA génère des hunks complets ; les humains patchent de façon fragmentée |
| `boilerplate_ratio` | Fraction de lignes ajoutées correspondant à des patterns récurrents | IA reproduit des patterns boilerplate fréquents |
| `import_churn_ratio` | Ratio imports ajoutés / lignes de code ajoutées | IA inclut souvent des imports non utilisés |

**Limitation** : ces signaux nécessitent une analyse AST du diff, coûteuse en temps.
Les implémenter dans `style.py` avec un flag `--deep-analysis` pour ne pas
ralentir le pipeline principal.

### Priorité 3 — Méta-signaux (Niveau B, expérimental)

| Signal | Description | Motivation |
|--------|-------------|------------|
| `review_cycle_count` | Nombre de rounds de revue par PR | L'IA peut réduire ou augmenter selon la qualité |
| `reviewer_comment_density` | Commentaires de revue par ligne modifiée | Proxy de qualité perçue |
| `revert_ratio` | Fraction de commits qui revertent un commit précédent | L'IA peut produire plus de code nécessitant un revert |

**Note** : ces signaux nécessitent des données de PR (GitHub Reviews API), pas
seulement des commits. Implémenter une couche `GitHubReviewFetcher` séparée.

---

## 3. Expériences de validation

### E1 — Validation par ground truth déclaré *(immédiat, données existantes)*

**Protocole** :
1. Identifier les développeurs dans `declared.yaml` avec `type = "no_ai"`.
2. Vérifier que le modèle NE détecte PAS de drift significatif pour ces profils.
3. Spécification de succès : `combined_p_value > 0.10` pour au moins 70% des
   développeurs `no_ai` dans la période couverte.

**Limites** : seulement 2 développeurs avec une déclaration non-ambiguë (DHH, Torvalds).
Ce n'est pas suffisant pour une validation statistiquement robuste.

**Action** : étendre `declared.yaml` à partir de sources publiques vérifiables
(tweets, interviews, articles de blog, commit metadata avec `[generated]` tag).

---

### E2 — Étude de sensibilité aux hyperparamètres *(court terme)*

**Protocole** :
1. Faire varier `recent_n` ∈ {3, 4, 5, 6} et `min_historical` ∈ {4, 6, 8}.
2. Pour chaque combinaison, calculer le taux de signalement positif sur les
   9 profils existants.
3. Identifier les zones de stabilité (résultats invariants) vs. zones de sensibilité.

**Critère d'acceptation** : les conclusions (drift / pas de drift) doivent rester
stables pour ±1 fenêtre dans `recent_n`.

**Objectif** : identifier les paramètres qui maximisent la robustesse,
pas la sensibilité.

---

### E3 — Validation croisée LODO *(court terme, implémentée)*

**Protocole** : voir `validation/cross_validate.py`.
Leave-One-Developer-Out sur les 9 profils — vérifier que les seuils calibrés sur
N-1 profils restent cohérents sur le N-ième.

**Limite** : avec N=9, LODO donne 9 folds de 8 profils d'entraînement.
C'est insuffisant pour une calibration numérique rigoureuse, mais utile pour
détecter les outliers (un profil qui contredit tous les autres).

---

### E4 — Expérience contrôlée sur données synthétiques *(moyen terme)*

**Protocole** :
1. Prendre un développeur actif disposé à participer.
2. Période A (6 mois) : développement sans outil IA, commits enregistrés.
3. Période B (6 mois) : adoption d'un outil IA, commits enregistrés.
4. Appliquer le pipeline en aveugle (analyste ne sait pas quelle période est laquelle).
5. Vérifier que le point de rupture détecté correspond à la transition A→B.

**Puissance statistique** : avec 6 mois de données trimestrielles, on n'a que
2 fenêtres par période — insuffisant. Il faut soit des fenêtres mensuelles
(n_hist=6, n_recent=2), soit une période de 18 mois.

**Effort** : nécessite le recrutement actif de développeurs. C'est la seule
expérience qui permettrait une validation causale, pas seulement corrélative.

---

### E5 — Test de robustesse adversariale *(moyen terme)*

**Question** : un développeur informé de la méthode peut-il effacer sa signature ?

**Protocole** :
1. Informer un développeur utilisant IA de TOUS les signaux mesurés.
2. Lui demander de continuer à utiliser l'IA pendant 3 mois en essayant de
   masquer son utilisation.
3. Mesurer si le drift est toujours détectable.

**Hypothèse** : les signaux de processus (fréquence, granularité) sont plus durs
à masquer que les signaux de style. Un développeur peut changer son style de code,
mais pas facilement changer sa fréquence de commit sans impacter sa productivité.

**Importance** : si un développeur motivé peut facilement effacer le signal,
l'approche est inutile pour les cas de mauvaise foi.

---

### E6 — Généralisation cross-langage *(long terme)*

**Question** : les signaux Niveau A sont-ils invariants selon le langage ?

**Hypothèse** : `median_files_per_commit`, `large_commit_ratio`, et
`median_inter_commit_hours` ne dépendent pas du langage — ils mesurent
le processus de travail, pas le code lui-même.

**À tester** : comparer les distributions de signaux pour des développeurs Python,
Go, TypeScript, Rust avant/après adoption IA.

**Prédiction** : si l'effet est réel, il devrait être visible dans tous les langages
avec des magnitudes comparables. Une différence systématique selon le langage
suggèrerait un confondant non modélisé.

---

## 4. Risques d'échec et mitigations

### R1 — Absence de ground truth (risque principal)

**Mécanisme** : sans développeurs ayant déclaré publiquement leur usage IA à une
date précise, toute calibration est circulaire. On ne peut pas valider un modèle
qu'on ne peut pas entraîner.

**Probabilité** : élevée. La grande majorité des développeurs n'annoncent pas
publiquement leur adoption d'outils IA.

**Mitigation** :
- Se limiter à des affirmations de type "détection de dérive comportementale"
  sans affirmer l'IA comme cause.
- Construire un dataset de ground truth par recrutement actif (E4).
- Utiliser les déclarations publiques avec dates précises (voir `declared.yaml`).

**Seuil d'abandon** : si après 24 mois, le dataset ground truth compte moins de
20 paires (développeur, date d'adoption vérifiée), l'approche probabiliste ne
peut pas être calibrée. Abandonner la revendication quantitative.

---

### R2 — Distribution shift des LLMs

**Mécanisme** : les patterns d'utilisation des LLMs évoluent. GPT-3.5 Copilot 2021
produisait des patterns différents de Claude 3 Sonnet 2024. Un modèle calibré
sur 2022-2023 sera peut-être invalide en 2026.

**Mitigation** :
- Ne pas calibrer sur les patterns stylistiques (Niveau C).
- Concentrer la calibration sur les signaux de processus (Niveau A),
  qui dépendent du comportement du développeur, pas du LLM.
- Prévoir un recalibrage annuel du modèle.

---

### R3 — Adaptation progressive des développeurs

**Mécanisme** : après 2-3 ans d'utilisation intensive de l'IA, les développeurs
normalisent leur workflow. Le signal de dérive diminue progressivement jusqu'à
devenir non détectable.

**Implication** : le système est utile pour détecter la **transition** (adoption),
pas l'**état stable** (utilisation confirmée depuis longtemps).

**Mitigation** : cibler les périodes de 0-18 mois après adoption. Au-delà,
le signal comportemental converge.

---

### R4 — Variance individuelle dominante

**Mécanisme** : pour certains développeurs, la variance naturelle de leurs commits
(selon le type de tâche, le projet, la phase) est supérieure à la différence
introduite par l'IA. Le signal est noyé dans le bruit.

**Probabilité** : élevée pour les développeurs très polyvalents (plusieurs projets,
types de tâches très variés) ou avec de faibles volumes de commits par fenêtre.

**Mitigation** :
- Seuil minimum de 5 commits par fenêtre trimestrielle (en dessous, la fenêtre
  n'est pas représentative).
- Minimum 10 fenêtres totales pour lancer l'analyse
  (`recent_n=4` + `min_historical=6`).

---

### R5 — Biais de sélection GitHub

**Mécanisme** : GitHub ne contient que les commits poussés publiquement.
Un développeur peut avoir un workflow IA très actif en local avec des `git squash`
agressifs avant de pousser. Le signal de granularité serait alors masqué.

**Implication** : le signal est mesuré sur le **workflow de collaboration**,
pas sur le workflow de développement local. Ces deux choses peuvent diverger.

**Mitigation** : ce risque est fondamental et sans mitigation complète.
Le signaler explicitement dans toute publication ou rapport.

---

## 5. Protocole de publication responsable

Toute publication de résultats sur un développeur identifié doit respecter les
contraintes suivantes :

1. **Jamais d'affirmation directe** : "X utilise l'IA" est interdit.
   Formuler : "Les signaux comportementaux de X sont statistiquement compatibles
   avec un changement de processus survenu autour de [date]. L'assistance IA est
   une hypothèse compatible — au même titre que [liste de confondants]."

2. **Toujours présenter les p-values et les intervalles de confiance** :
   une conclusion doit être accompagnée du niveau de preuve statistique.

3. **Toujours lister les hypothèses alternatives** : voir `_build_interpretation()`
   dans `temporal.py` pour la liste standard des confondants.

4. **Ne pas cibler des individus sans leur consentement** : l'analyse est légitime
   sur des données GitHub publiques à des fins de recherche, mais la publication
   nominative de conclusions sur une personne réelle nécessite son accord explicite.

5. **Versionner le modèle** : toute publication doit indiquer la version du pipeline,
   les paramètres utilisés, et la date de l'analyse.

---

## 6. Questions ouvertes

| # | Question | Difficulté | Impact |
|---|----------|------------|--------|
| Q1 | Quel est le seuil minimum de commits par fenêtre pour une estimation fiable ? | Faible | Élevé |
| Q2 | Les signaux Niveau A sont-ils corrélés entre eux ? (collinéarité) | Moyen | Élevé |
| Q3 | La granularité trimestrielle est-elle optimale, ou faut-il des fenêtres mensuelles ? | Moyen | Élevé |
| Q4 | Un LLM différent (Cursor vs. Copilot vs. Claude) produit-il des signatures différentes ? | Élevé | Moyen |
| Q5 | L'effet est-il additif (plus d'IA → plus de signal) ou binaire (présence/absence) ? | Élevé | Élevé |
| Q6 | Peut-on séparer l'effet "adoption d'IA" de l'effet "vieillissement professionnel" ? | Très élevé | Très élevé |
| Q7 | Les modèles entraînés sur des développeurs open-source généralisent-ils aux développeurs enterprise ? | Élevé | Élevé |

---

## 7. Critères de succès du projet

Le projet est un succès scientifique si :

- [ ] **S1** : Détection robuste de la dérive comportementale sur les 9 profils existants
  avec p < 0.05 (Fisher) pour au moins les développeurs dont le comportement
  a objectivement changé entre 2020 et 2024.

- [ ] **S2** : Aucun faux positif fort (p < 0.01) sur les développeurs déclarés `no_ai`
  (Torvalds, DHH) dans les fenêtres couvertes par leur déclaration.

- [ ] **S3** : Stabilité LODO : les conclusions ne changent pas si on retire
  un profil de la calibration (applicable dès que la calibration est possible).

- [ ] **S4** : Résultats reproductibles : le pipeline entier tourne sans modification
  sur les 9 profils et produit le même résultat à 48 heures d'intervalle.

- [ ] **S5** : Aucune affirmation directe d'usage IA dans les outputs — vérifiable
  en cherchant "uses AI", "utilise l'IA", "AI-assisted" dans tous les fichiers
  de sortie (`reports/`, terminaux, HTML).

Le projet est un succès pratique si, en plus de S1-S5 :

- [ ] **S6** : Un utilisateur extérieur peut analyser son propre profil GitHub en
  moins de 10 minutes avec `devfp run --login <username>`.

- [ ] **S7** : Le rapport généré est compréhensible par un non-statisticien sans
  formation supplémentaire.
