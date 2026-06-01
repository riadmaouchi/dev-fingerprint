"""
Migrate old DevProfile JSON files to the new schema.

Old schema → New schema:
  - score_timeline          → behavior_timeline
  - window.llm_score        → window.style_score
  - window: add all Level A/B process signal fields (default 0.0)
  - change_point.metric     → change_point.signal
  - change_point: add signal_level="C", detection_method="pelt"
  - change_point.nearest_llm_event → change_point.nearest_known_event
  - top-level: add drift_result=null

Originals are backed up to reports/real/backup/ before modification.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROFILES_DIR = ROOT / "reports" / "real"
BACKUP_DIR = PROFILES_DIR / "backup"

_PROCESS_SIGNAL_DEFAULTS: dict[str, float] = {
    "median_files_per_commit": 0.0,
    "median_net_lines": 0.0,
    "large_commit_ratio": 0.0,
    "cross_module_ratio": 0.0,
    "refactor_ratio": 0.0,
    "median_inter_commit_hours": 0.0,
    "commits_per_week": 0.0,
    "test_touch_ratio": 0.0,
    "merge_ratio": 0.0,
}


def _migrate_window(window: dict) -> dict:
    out = dict(window)
    if "llm_score" in out:
        out["style_score"] = out.pop("llm_score")
    elif "style_score" not in out:
        out["style_score"] = 0.0
    for field, default in _PROCESS_SIGNAL_DEFAULTS.items():
        out.setdefault(field, default)
    return out


def _migrate_change_point(cp: dict) -> dict:
    out = dict(cp)
    if "metric" in out:
        out["signal"] = out.pop("metric")
    out.setdefault("signal_level", "C")
    out.setdefault("detection_method", "pelt")
    if "nearest_llm_event" in out:
        out["nearest_known_event"] = out.pop("nearest_llm_event")
    else:
        out.setdefault("nearest_known_event", None)
    return out


def migrate_profile(data: dict) -> dict:
    out = dict(data)
    if "score_timeline" in out:
        out["behavior_timeline"] = out.pop("score_timeline")
    out["behavior_timeline"] = [_migrate_window(w) for w in out.get("behavior_timeline", [])]
    out["change_points"] = [_migrate_change_point(cp) for cp in out.get("change_points", [])]
    out.setdefault("drift_result", None)
    return out


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    profiles = sorted(
        p for p in PROFILES_DIR.glob("*.json")
        if p.name != "summary.json" and p.parent == PROFILES_DIR
    )

    if not profiles:
        print("No profile JSON files found.")
        sys.exit(0)

    ok = 0
    errors: list[str] = []

    for path in profiles:
        backup = BACKUP_DIR / path.name
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"  backed up → {backup.relative_to(ROOT)}")

        raw = json.loads(path.read_text())
        migrated = migrate_profile(raw)
        path.write_text(json.dumps(migrated, indent=2, ensure_ascii=False))

        # Verify the migrated file is loadable
        try:
            sys.path.insert(0, str(ROOT / "src"))
            from devfp.models import DevProfile
            DevProfile.model_validate(migrated)
            print(f"  ✓ {path.name}")
            ok += 1
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            print(f"  ✗ {path.name}: {exc}")

    print(f"\n{ok}/{len(profiles)} profiles migrated successfully.")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
