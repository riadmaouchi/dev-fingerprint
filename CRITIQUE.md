# Critique des approches naïves de détection d'IA dans le code

Ce document documente pourquoi les approches intuitives de détection d'IA dans le code
sont scientifiquement non défendables. Il sert de justification pour les choix
méthodologiques de ce projet.

---

## Hypothèse de travail

Nous ne cherchons PAS à détecter si un commit a été généré par une IA.

Nous cherchons à estimer :

> **P(activité compatible avec assistance IA | historique Git observé)**

Cette distinction est fondamentale. Le code généré par une IA et le code écrit par un
développeur expert peuvent être indiscernables. La seule observable fiable est le
**processus** de développement, pas le **style** du code.

---

## 1. Détection par style de code

### Description
Rechercher dans le diff des caractéristiques supposément typiques du code généré par IA :
longueur des fonctions, indentation, complexité cyclomatique, etc.

### Biais
- Un développeur senior Python avec une forte culture PEP8 produit naturellement
  des fonctions courtes et bien structurées — exactement le style attribué aux LLMs.
- Le style de code dépend du langage, du framework, des conventions d'équipe,
  de l'ancienneté du développeur, et du type de tâche (feature vs. hotfix vs. refactoring).

### Faux positifs
- Tout développeur qui suit les conventions modernes de son écosystème.
- Tout développeur qui a adopté un linter strict (black, gofmt, rustfmt).
- Tout développeur qui a changé d'équipe ou de projet avec des conventions différentes.

### Faux négatifs
- Un utilisateur de Copilot qui retouche systématiquement les suggestions IA
  pour correspondre à son style personnel.
- Un utilisateur de Claude qui formule ses prompts pour produire du code "old school".

### Contournement trivial
Un développeur peut désactiver ou modifier toute suggestion IA avant de commiter.
Le style final dans le diff est toujours le résultat d'un filtre humain.

---

## 2. Détection par densité de commentaires

### Description
Les LLMs génèrent typiquement plus de commentaires et de docstrings que les développeurs
organiques. Détecter une densité de commentaires supérieure à la moyenne historique.

### Biais
- Les projets open source à fort trafic (Linux, CPython) ont des conventions de
  documentation strictes qui préexistent aux LLMs.
- La densité de commentaires est une fonction de la phase du projet
  (proof-of-concept vs. production) et du type de changement (API publique vs. interne).
- Les revues de code et les exigences de documentation augmentent les commentaires
  indépendamment de l'IA.

### Faux positifs
- Tout développeur qui améliore la documentation d'un module legacy.
- Tout projet qui passe d'une phase d'exploration à une phase de stabilisation.
- Tout développeur qui change de rôle et devient plus pédagogue dans son code.

### Faux négatifs
- Les utilisateurs de Copilot qui suppriment systématiquement les commentaires générés.

### Contournement trivial
Supprimer tous les commentaires avant de commiter.

---

## 3. Détection par messages de commit

### Description
Les messages de commit formatés avec le style "Conventional Commits"
(`feat:`, `fix:`, `chore:`) sont supposément associés aux LLMs.

### Biais
- Conventional Commits est une convention documentée et adoptée par des milliers
  de projets bien avant l'ère des LLMs.
- Des outils comme `commitizen`, `semantic-release`, et les templates GitHub
  imposent ce format indépendamment de l'IA.
- Le style du message de commit est souvent imposé par les reviewers ou le CI.

### Faux positifs
- Tout projet qui utilise `semantic-release` ou `commitizen`.
- Tout développeur qui lit les meilleures pratiques Git (> 2020).
- Tout projet open source qui demande des messages structurés dans CONTRIBUTING.md.

### Faux négatifs
- Les utilisateurs de Copilot qui écrivent leurs messages de commit manuellement
  (ce que beaucoup font).

### Contournement trivial
Écrire les messages de commit manuellement.

---

## 4. Détection par nomenclature

### Description
Les LLMs génèrent des noms de variables et fonctions plus longs et descriptifs
(`calculate_user_total_purchase_amount` vs `calc_total`).

### Biais
- Les conventions de nomenclature varient selon le langage, le framework,
  et les guidelines de l'équipe.
- Python, par exemple, a toujours favorisé les noms descriptifs (PEP8).
- Un développeur qui améliore la lisibilité d'une codebase legacy produit
  exactement ce signal.
- L'adoption d'outils de renommage automatique (ex: IDE refactoring) produit
  le même signal.

### Faux positifs
- Tout développeur qui adopte les conventions modernes de son langage.
- Tout développeur senior qui revoit du code junior.

### Faux négatifs
- Un utilisateur de LLM qui préfère les noms courts par habitude et les impose
  aux suggestions.

### Contournement trivial
Renommer les variables générées pour correspondre au style personnel avant de commiter.

---

## 5. Détection par formatage

### Description
Détecter des patterns de formatage spécifiques (espacement, indentation, longueur
de ligne) associés aux LLMs.

### Biais
- Les formatters automatiques (black, prettier, rustfmt) rendent le code indiscernable
  du code formaté par un LLM.
- L'adoption d'un formatter dans un projet existant crée exactement ce signal.

### Faux positifs
- Tout projet qui adopte un auto-formatter.
- Tout développeur qui configure son éditeur différemment.

### Faux négatifs
- Tout utilisateur de LLM dont le formatter reformate les suggestions.

### Contournement trivial
Passer le code généré dans un formatter avant de commiter.

---

## 6. Recherche de phrases typiques de ChatGPT

### Description
Rechercher des phrases comme "Certainly!", "As an AI language model", "Sure, here's",
ou des patterns de docstring spécifiques à GPT-4.

### Biais majeur
- Ces phrases apparaissent dans les réponses conversationnelles des LLMs,
  pas dans le code qu'ils génèrent.
- Si quelqu'un cherche un fragment de code uniquement, le LLM ne préfacera pas
  sa réponse avec "Certainly!".

### Invalidité fondamentale
Cette approche a un taux de vrais positifs proche de zéro pour le code pur.
Elle n'est applicable qu'aux messages de commit ou README générés avec une invite
qui inclut de la prose, ce qui est rare dans le développement logiciel réel.

---

## 7. Détection basée sur un seul commit

### Invalidité fondamentale
Un seul commit ne peut jamais fournir de preuve statistique de quoi que ce soit.

**Raisons :**
1. La variance inter-commit d'un même développeur est supérieure à la différence
   entre le code humain et le code IA (bruit > signal).
2. Il n'existe pas de distribution de référence "code humain" vs "code IA" —
   les deux distributions se chevauchent massivement.
3. Un seul commit est susceptible à toutes les sources de biais citées ci-dessus.
4. L'inférence sur un seul commit viole le principe fondamental de la statistique :
   une observation ne peut pas établir un pattern.

**Ce que l'on peut détecter sur un seul commit :** rien de défendable.

**Ce que l'on peut détecter sur une série temporelle :** un changement de
comportement de développement par rapport à la baseline historique de l'auteur.

---

## Conclusion : ce que ce projet fait différemment

Ce projet abandonne les approches ci-dessus et se concentre sur :

1. **Signaux de processus (Niveau A)** — mesures de HOW le code est écrit,
   pas du résultat : fréquence des commits, taille médiane, dispersion cross-module,
   ratio de refactoring.

2. **Analyse longitudinale** — comparaison de l'auteur avec lui-même dans le passé,
   pas avec une distribution générique "code humain".

3. **Tests statistiques explicites** — Mann-Whitney U pour la comparaison
   de distributions, Fisher pour la combinaison de signaux.

4. **Interprétation probabiliste** — P(drift comportemental | historique),
   avec explicitation des hypothèses alternatives.

5. **Reconnaissance des limites** — sans données de ground truth (déclarations
   explicites des développeurs), aucune calibration n'est possible.
