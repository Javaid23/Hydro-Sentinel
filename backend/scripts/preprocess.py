"""
Build clean per-target matchup tables from the raw USGS release.

Writes:
    data/processed/turbidity.parquet
    data/processed/chlorophyll_a.parquet
    data/processed/cdom.parquet
    data/processed/observations.parquet      (one row per scene × site, all targets' observed values)
    data/processed/preprocess_audit.json     (rows dropped per filter rule, summary counts)
    docs/preprocess_summary.md               (human-readable version of the audit)

Usage (from repo root, with backend/.venv active or via its python):
    python backend/scripts/preprocess.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `hydrosentinel` importable

from hydrosentinel import config as C  # noqa: E402
from hydrosentinel import data  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("preprocess")


def main() -> int:
    raw = data.load_raw()
    matched = data.collapse_matchups(raw)
    kept, audit = data.apply_filters(matched)
    tables = data.split_targets(kept)
    summary = data.summarise(tables)

    C.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    for key, t in tables.items():
        out = C.DATA_PROCESSED / f"{key}.parquet"
        t.to_parquet(out, index=False)
        log.info("wrote %s (%s rows)", out.name, f"{len(t):,}")
    obs = data.build_observation_index(tables)
    obs.to_parquet(C.DATA_PROCESSED / "observations.parquet", index=False)
    log.info("wrote observations.parquet (%s scene×site observations, %d sites)", f"{len(obs):,}", obs["site_no"].nunique())

    meta = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_rows_target_params": int(len(raw)),
        "distinct_matchups": int(len(matched)),
        "filter": C.MATCHUP_FILTER.__dict__,
        "audit": audit.to_dict(orient="records"),
        "summary": summary.reset_index().to_dict(orient="records"),
        "targets": {k: {"label": t.label, "unit": t.unit, "parm_codes": list(t.parm_codes), "note": t.note}
                    for k, t in C.TARGETS.items()},
    }
    (C.DATA_PROCESSED / "preprocess_audit.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    md = [
        "# Preprocessing summary\n",
        f"Generated {meta['generated_utc']} by `backend/scripts/preprocess.py`.\n",
        f"\nRaw rows with a target parameter code: **{len(raw):,}** → distinct scene×site×target "
        f"matchups (nearest sonde reading per overpass): **{len(matched):,}**.\n",
        "\n## Rows dropped per filter rule\n\n| rule | dropped | remaining |\n|---|---|---|\n",
        *[f"| {r['rule']} | {r['dropped']:,} | {r['remaining']:,} |\n" for r in meta["audit"]],
        "\n## Usable observations per basin × target\n\n",
        "| target | " + " | ".join(summary.columns) + " |\n|---|" + "---|" * len(summary.columns) + "\n",
        *[f"| {k} | " + " | ".join(f"{v:,}" for v in row) + " |\n" for k, row in summary.iterrows()],
        "\nDecisions behind each rule: [data_findings.md](data_findings.md).\n",
    ]
    (C.DOCS_DIR / "preprocess_summary.md").write_text("".join(md), encoding="utf-8")
    print("\n" + summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
