"""
Provenance audit: check that nothing the system serves is fabricated.

The project's central claim is that every number on screen is computed from real measurements.
This asserts that mechanically rather than by inspection, so the claim can be re-checked by
anyone at any time.

    python backend/scripts/audit_provenance.py

Exit code 0 if every check passes, 1 otherwise. Checks:

  1. No fake/mock/placeholder/synthetic content in the serving path
  2. Test doubles exist only under tests/
  3. Models were trained on the real USGS release, with the row counts to prove it
  4. Every processed row traces to the raw release through an audited filter chain
  5. Imagery comes from named public archives, not local fixtures
  6. The harmonisation factors were measured from real same-day scene pairs
  7. The LLM cannot write into the numeric assessment
  8. Stress-score thresholds are defined once, in the backend
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hydrosentinel import config as C  # noqa: E402

ROOT = C.ROOT_DIR
BACKEND = C.BACKEND_DIR
SERVING = [BACKEND / "hydrosentinel", BACKEND / "app"]
FRONTEND = ROOT / "frontend" / "src"

# Words that would indicate fabricated content if they appeared in code that serves users.
# Matched case-insensitively against source lines, excluding comments that merely discuss them.
BANNED = re.compile(r"\b(fake|mock|dummy|placeholder|synthetic|simulated|lorem)\b", re.I)

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((bool(ok), name, detail))


def py_files(paths) -> list[Path]:
    out = []
    for p in paths:
        out += [f for f in p.rglob("*.py") if "__pycache__" not in str(f)]
    return out


def source_lines(path: Path) -> list[tuple[int, str]]:
    """Code lines only — a docstring explaining that something is *not* fake is not a violation."""
    lines, in_doc, delim = [], False, ""
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if in_doc:
            if delim in line:
                in_doc = False
            continue
        if line.startswith(('"""', "'''")):
            delim = line[:3]
            if not (line.count(delim) >= 2 and len(line) > 3):
                in_doc = True
            continue
        if line.startswith("#"):
            continue
        lines.append((i, raw.split("#")[0]))
    return lines


# ----------------------------------------------------------------------- 1 & 2
hits = []
for f in py_files(SERVING) + [p for p in FRONTEND.rglob("*.jsx")] + [p for p in FRONTEND.rglob("*.js")]:
    for n, line in (source_lines(f) if f.suffix == ".py" else
                    [(i, l) for i, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
                     if not l.strip().startswith(("//", "*", "/*"))]):
        if BANNED.search(line):
            hits.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:70]}")
check(not hits, "no fabricated content in the serving path",
      "; ".join(hits[:3]) if hits else f"scanned {len(py_files(SERVING))} python + frontend sources")

doubles = [f.relative_to(ROOT) for f in py_files(SERVING)
           if re.search(r"monkeypatch|FakeClient|_fake_reads", f.read_text(encoding="utf-8"))]
check(not doubles, "test doubles confined to tests/", str(doubles) if doubles else "none in production code")

# ----------------------------------------------------------------------- 3 & 4
audit_path = C.DATA_PROCESSED / "preprocess_audit.json"
if audit_path.exists():
    a = json.loads(audit_path.read_text(encoding="utf-8"))
    chain_ok, prev = True, a["distinct_matchups"]
    for step in a["audit"]:
        chain_ok &= (prev - step["dropped"] == step["remaining"])
        prev = step["remaining"]
    check(chain_ok, "every filtered row is accounted for",
          f"{a['raw_rows_target_params']:,} raw rows -> {a['distinct_matchups']:,} matchups -> {prev:,} kept")
    totals = {r["target"]: r["total"] for r in a["summary"]}
    check(sum(totals.values()) == prev, "per-target tables sum to the filtered total", str(totals))
else:
    check(False, "preprocessing audit present", "run scripts/preprocess.py")

meta_path = C.MODELS_DIR / "turbidity" / "metadata.json"
if meta_path.exists():
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    real_sites = all(s.isdigit() for s in m["training_sites"])
    check(real_sites and len(m["training_sites"]) > 20, "models trained on real USGS site numbers",
          f"{m['n_rows']:,} rows, {len(m['training_sites'])} sites, basins {m['training_basins']}")
    check(m["conformal"]["n_calibration"] > 100, "conformal calibrated on held-out rows",
          f"n={m['conformal']['n_calibration']}")
else:
    check(False, "trained model metadata present", "run scripts/train.py")

# ----------------------------------------------------------------------- 5
from hydrosentinel import live, live_global  # noqa: E402
check(live.BUCKET == "usgs-wma-sentinel-2-aqr-acolite-dsf" and live.HTTP_BASE.startswith("https://"),
      "US imagery from the USGS public archive", live.HTTP_BASE)
check(live_global.STAC_SEARCH.startswith("https://earth-search.aws.element84.com"),
      "global imagery from the Copernicus public archive", live_global.STAC_SEARCH)
check(live.NWIS_IV.startswith("https://waterservices.usgs.gov"),
      "ground truth from the USGS NWIS service", live.NWIS_IV)

# ----------------------------------------------------------------------- 6
h_path = C.MODELS_DIR / "harmonisation_l2a.json"
if h_path.exists():
    h = json.loads(h_path.read_text(encoding="utf-8"))
    pairs_real = all(p.get("aqr_scene") and p.get("l2a_scene") and p.get("date") for p in h["pairs"])
    check(pairs_real and h["n_pairs"] >= 10, "harmonisation measured from real scene pairs",
          f"{h['n_pairs']} same-day pairs at {h['n_sites']} sites")
else:
    check(False, "harmonisation study present", "run scripts/harmonise_l2a.py")

# ----------------------------------------------------------------------- 7
llm_src = (BACKEND / "hydrosentinel" / "llm.py").read_text(encoding="utf-8")
writes = re.findall(r"assessment\[[^\]]+\]\s*=|result\[.(?:stress|indicators|ood)", llm_src)
check(not writes, "the LLM cannot write into the numeric assessment",
      "returns prose only" if not writes else str(writes))

# ----------------------------------------------------------------------- 8
from hydrosentinel import stress  # noqa: E402
front = (FRONTEND / "components" / "panels.jsx").read_text(encoding="utf-8")
backend_bands = [b for b, _ in stress.STRESS_STATUS][:2]
hardcoded = re.findall(r"score\s*>=\s*(\d+)", front)
check(not hardcoded or [float(x) for x in hardcoded] == sorted(backend_bands, reverse=True),
      "score thresholds agree between backend and dashboard",
      f"backend {backend_bands}, dashboard {hardcoded or 'served by API'}")

# ----------------------------------------------------------------------- report
print("\nPROVENANCE AUDIT\n" + "=" * 72)
for ok, name, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
failed = [r for r in results if not r[0]]
print("=" * 72)
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
