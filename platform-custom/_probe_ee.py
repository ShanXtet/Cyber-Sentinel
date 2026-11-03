from pathlib import Path

d = Path("/opt/opencti/public/assets")
for p in d.glob("*.js"):
    t = p.read_text(errors="ignore")
    hits = []
    if "severity:`ee`" in t:
        hits.append("severity_ee")
    if "/dashboard/pirs" in t:
        hits.append("pirs")
    if "I would like to use a EE feature" in t:
        hits.append("eechip_msg")
    if "label:e(`EE`)" in t or "label:n(`EE`)" in t or "children:`EE`" in t:
        hits.append("label_EE")
    if hits:
        print(p.name, hits)
