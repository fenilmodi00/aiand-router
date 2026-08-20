import json
from pathlib import Path
for p in [
 "data/scorer-hard-bilinear-matched-cal.json",
 "data/scorer-hard-bilinear-mix1train-matched.json",
 "data/scorer-hard-bilinear-hash32.json",
 "data/scorer-hard-bilinear-distill48.json",
 "data/scorer-hard-bilinear-distill48-gymalt.json",
]:
 path=Path(p)
 if not path.exists():
  print("missing", p); continue
 d=json.loads(path.read_text(encoding="utf-8"))
 d["serve_candidate"]=False
 d["experimental"]=True
 d["serve_note"]="Loses replay_gate vs data/scorer-hard-logistic.json; shadow experiment only."
 path.write_text(json.dumps(d, indent=2), encoding="utf-8")
 print("stamped", p)
