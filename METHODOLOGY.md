# Méthodologie — dev-fingerprint

## Objectif scientifique

Estimer :

> **P(activité compatible avec assistance IA | historique Git observé)**

Et **non** : `P(commit généré par IA)`.

La distinction est fondamentale : nous mesurons un changement de processus,
pas la provenance du code.

---

## Architecture du pipeline

```
Commits GitHub
     │
     ▼
Extraction de métriques par commit (StyleMetrics)
     │
     ├── Signaux de processus (Niveau A/B) — métriques directes du commit
     │   ├── files_changed
     │   ├── net_lines / total_churn
     │   ├── cross_module_ratio
     │   ├── is_refactor
     │   └── touches_tests / test_file_ratio
     │
     └── Signaux de style (Niveau C) — via AST/tree-sitter
         ├── comment_density, docstring_coverage
         ├── avg_identifier_length, error_handling_density
         └── style_score (CodeAnalyzer.copilot_score)
                    │
                    ▼
         Agrégation trimestrielle (BehaviorWindow)
                    │
                    ▼
         Détection de points de rupture (PELT + CUSUM + EWMA + BOCPD)
         par signal individuellement — union des alarmes
                    │
                    ▼
         Test d'auto-comparaison (Mann-Whitney U)
         Auteur récent vs. auteur historique
                    │
                    ▼
         Fisher's method (Level A signals only)
                    │
                    ▼
         DriftResult — interprétation probabiliste
```

---

## Classement des signaux

### Niveau A — Signaux de processus (preuve primaire)

Justification théorique : ces signaux mesurent la façon dont le code est produit,
pas l'apparence du résultat. Un assistant IA modifie la granularité des tâches,
la vitesse d'exécution, et la cohérence topologique des changements.

| Signal | Description | Résistance au contournement | Stabilité inter-langages |
|--------|-------------|----------------------------|--------------------------|
| `median_files_per_commit` | Médiane du nombre de fichiers modifiés par commit | Élevée | Élevée |
| `large_commit_ratio` | Fraction de commits avec \|net_lines\| > 200 | Modérée | Élevée |
| `cross_module_ratio` | Dispersion cross-module normalisée (0=même module, 1=max spread) | Élevée | Élevée |
| `refactor_ratio` | Fraction de commits de refactoring (churn élevé, net faible) | Modérée | Élevée |

**Hypothèse causale** : un assistant IA abaisse le coût cognitif de la génération de code,
ce qui se traduit par des commits plus grands et plus transversaux. C'est une hypothèse
plausible, non démontrée.

**Facteurs confondants** :
- Changement de rôle (lead → contributeur)
- Phase du projet (exploration → stabilisation)
- Adoption d'un nouveau framework
- Évolution de la taille de l'équipe

### Niveau B — Signaux de processus (utiles mais fragiles)

| Signal | Description | Faiblesse principale |
|--------|-------------|---------------------|
| `test_touch_ratio` | Fraction de commits touchant des fichiers de test | Dépend du style du projet et de la phase |
| `median_net_lines` | Médiane du delta de lignes par commit | Grande variance, dépend du type de tâche |

### Niveau C — Signaux de style (baseline seulement, non primaires)

**Ces signaux sont conservés pour la comparaison avec les approches naïves.
Ils ne doivent PAS être utilisés comme preuve primaire. Voir CRITIQUE.md.**

| Signal | Description | Faiblesse principale |
|--------|-------------|---------------------|
| `style_score` | Score composite CodeAnalyzer.copilot_score() | Indiscernable du style d'un expert |
| `comment_score` | Densité de commentaires | Fonction de la phase projet, pas de l'IA |
| `docstring_score` | Couverture de docstrings | Imposé par les revues de code |
| `verbosity_score` | Longueur des identifiants | Fonction des conventions du langage |
| `error_handling_score` | Densité de gestion d'erreurs | Dépend du domaine |
| `commit_style_score` | Fraction de conventional commits | Standard pre-IA (commitizen, etc.) |
| `function_style_score` | Inverse de la longueur des fonctions | Variable selon type de tâche |

---

## Méthodes de détection

Le pipeline utilise **cinq méthodes distinctes** réparties en deux rôles :

| Rôle | Méthode | Type |
|------|---------|------|
| Détection de ruptures | PELT | Optimisation exacte |
| Détection de ruptures | CUSUM | Contrôle séquentiel |
| Détection de ruptures | EWMA | Alerte précoce continue |
| Détection de ruptures | BOCPD | Inférence bayésienne en ligne |
| Test de dérive globale | Mann-Whitney U + Fisher | Non-paramétrique |

Les quatre méthodes de rupture s'appliquent **signal par signal**,
de façon indépendante. Leurs alarmes sont réunies par union puis
filtrées par un seuil de magnitude relative (≥15%).
Le test Mann-Whitney opère sur la comparaison récent-vs-historique
et produit un p-value combiné via la méthode de Fisher (signaux Niveau A uniquement).

---

### Tableau comparatif des méthodes de détection de rupture

| Critère | PELT | CUSUM | EWMA | BOCPD |
|---------|------|-------|------|-------|
| **Paradigme** | Optimisation globale | Contrôle séquentiel | Contrôle continu | Inférence bayésienne |
| **Hypothèse sur les données** | i.i.d. par segment (RBF) | Gaussien stationnaire | Gaussien stationnaire | Normal-Inverse-Gamma |
| **Détecte les shifts abrupts** | ✅ Optimal | ✅ Bon | ✅ Bon | ✅ Bon |
| **Détecte les dérives graduelles** | ⚠️ Faible | ✅ Fort | ⚠️ Faible | ❌ Faible |
| **Localise précisément** | ✅ Exact | ⚠️ Retard | ❌ Flou | ✅ Au point de saut |
| **Interprétabilité** | Moyenne (optimisation) | Élevée (statistique) | Élevée (statistique) | Élevée (probabilité) |
| **Sensibilité aux hyperparamètres** | `penalty` critique | `h` critique | `lambda_` modéré | `hazard` modéré |
| **Série minimale** | 6 (2×min_size=3) | 4 | 4 | 4 |
| **Plusieurs ruptures** | ✅ Natif | ⚠️ Reset à chaque alarme | ⚠️ Reset aux alarmes | ⚠️ Décroissance après 1ère |
| **Sortie** | Indices exacts | Indices d'alarme | Indices hors-contrôle | Indices P(r=0)>seuil |
| **Paramètres par défaut** | `penalty=3.0` | `k=0.5, h=5.0` | `λ=0.2, L=3σ` | `H=1/15, seuil=0.25` |

**Recommandation** : utiliser PELT + CUSUM en défaut (ensemble complémentaire).
Ajouter BOCPD pour les signaux Niveau A lorsque l'on souhaite une probabilité
de rupture interprétable ; EWMA pour la surveillance continue sans localisation précise.

---

### PELT (Pruned Exact Linear Time)
- Optimisation exacte du coût de segmentation sur l'ensemble de la série.
- `min_size=3`, `penalty=3.0` (BIC-like), seuil de magnitude relative : 15%.
- **Force** : optimal pour un shift dominant unique ; résultats reproductibles.
- **Faiblesse** : séries courtes (< 12 points) ; ne détecte pas les dérives lentes.

### CUSUM (Cumulative Sum Control Chart)
- Accumulation des écarts standardisés à la moyenne de référence (première moitié).
- `k=0.5` (slack), `h=5.0` (seuil). Réinitialisation après chaque alarme.
- **Force** : détecte les dérives graduelles et les shifts petits mais persistants.
- **Faiblesse** : retard de détection ; faux positifs si `h` trop bas.

### EWMA (Exponentially Weighted Moving Average)
- Moyenne mobile exponentielle avec UCL/LCL steady-state à 3σ.
- `lambda_=0.2`, `l_factor=3.0`. Initialisation sur première moitié.
- **Force** : alerte précoce ; résistant aux outliers ponctuels.
- **Faiblesse** : ne localise pas précisément la rupture ; moins sensible aux grands shifts.

### BOCPD (Bayesian Online Change Point Detection)
*Adams & MacKay, 2007 — "Bayesian Online Changepoint Detection"*

- Maintient une distribution postérieure sur la **longueur du run courant** r_t.
- Modèle conjugué : Normal-Inverse-Gamma (predictif Student-t).
- Alarme quand P(r_t = 0 | x_{1:t}) > seuil (0.25 par défaut).
- `hazard = 1/15` : durée de run attendue ≈ 4 ans de données trimestrielles.
- **Force** : sortie probabiliste directement interprétable ; pas de calibration fréquentiste.
  Robuste quand les segments ont des variances différentes.
- **Faiblesse** : prior global (moyenne de la série entière) peut masquer la 2ème rupture
  si la 1ère a déjà réorganisé la distribution postérieure. Séries très courtes (< 8 pts)
  donnent des probabilités plates.

**Note implémentation** : le prior est initialisé sur la moyenne et variance de
l'ensemble de la série (prior vague). Pour les séries avec `n < 8` fenêtres,
préférer PELT ou CUSUM.

---

## Test d'auto-comparaison

### Protocole
- **Historique** : toutes les fenêtres sauf les `recent_n` dernières (défaut : 4).
- **Récent** : les `recent_n` dernières fenêtres.
- **Test** : Mann-Whitney U bilatéral (non-paramétrique, pas d'hypothèse de normalité).
- **Minimum** : `min_historical=6` + `recent_n=4` = 10 fenêtres minimum (~2,5 ans).
- **Combinaison** : méthode de Fisher sur les p-values des signaux Niveau A uniquement.

### H₀ / H₁
- **H₀** : la distribution récente est issue de la même distribution que la baseline.
- **H₁** : la distribution récente diffère significativement de la baseline.

Rejeter H₀ implique un changement de comportement. Ce changement est **compatible**
avec l'assistance IA, mais aussi avec une liste de facteurs alternatifs.

### Facteurs alternatifs à considérer systématiquement

| Facteur | Mécanisme observable |
|---------|---------------------|
| Vieillissement | Délégation accrue, commits plus rares et plus importants |
| Changement de rôle | Lead → contributeur, etc. |
| Phase du projet | Exploration vs. stabilisation vs. maintenance |
| Évolution de l'équipe | Taille, culture, processus de revue |
| Adoption d'outils | IDE, refactoring automatisé, CI/CD |
| Absence / retour | Patterns radicalement différents après une pause |

---

## Cas Linus Torvalds

Torvalds est un cas d'étude de référence pour les **facteurs confondants** :

1. Son rôle a évolué de mainteneur actif à "project guardian".
2. Le projet Linux a massivement évolué : outils, contributeurs, processus.
3. Sa prise de recul publique en 2018 crée une rupture comportementale documentée
   et indépendante de l'IA.

Toute interprétation d'un signal de drift sur Torvalds doit corriger ces confondants
avant de considérer l'hypothèse IA.

---

## Protocole de validation

### Ce qui est démontrable aujourd'hui
- ✅ Détecter un changement statistiquement significatif dans le comportement
  d'un développeur par rapport à sa propre baseline.
- ✅ Identifier les signaux qui ont changé et dans quelle direction.
- ✅ Localiser approximativement la date du changement.

### Ce qui est seulement plausible
- ⚠️ Associer le changement à l'émergence des outils IA (corrélation temporelle).
- ⚠️ Distinguer l'assistance IA des autres facteurs confondants.

### Ce qui est spéculatif
- ❌ Affirmer qu'un développeur utilise l'IA à partir du signal seul.
- ❌ Quantifier l'intensité de l'utilisation.
- ❌ Différencier les outils IA entre eux.

### Données nécessaires pour une validation rigoureuse
1. **Groupe témoin** : développeurs déclarant explicitement n'utiliser aucun assistant IA.
2. **Groupe positif** : développeurs déclarant utiliser explicitement un assistant IA.
3. **Calibration** : minimum 30 échantillons labelisés (15/classe), Platt scaling
   ou isotonic regression (`validation/calibration.py`).
4. **Validation croisée** : LODO leave-one-developer-out (`validation/cross_validate.py`).

---

## Risques d'échec du projet

1. **Ground truth insuffisant** : sans déclarations vérifiables, toute calibration
   est circulaire. C'est le risque principal.

2. **Fragilité temporelle** : les patterns des LLMs évoluent. Un calibrateur 2023
   sera probablement invalide en 2026.

3. **Confondants non observés** : GitHub ne contient pas d'informations sur les
   changements de rôle ou de vie personnelle des développeurs.

4. **Adaptation des développeurs** : l'utilisation longue de l'IA réduit
   progressivement le signal (le workflow se normalise).

5. **Variance individuelle dominante** : pour certains développeurs, la variance
   de leurs propres commits est plus grande que la différence IA/humain.
