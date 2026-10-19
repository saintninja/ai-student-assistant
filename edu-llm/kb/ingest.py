import sys, pathlib, re, httpx, yaml

BASE = "https://mfua.edu-org.local/api"   # local doman name
token = sys.argv[1]
root = pathlib.Path(__file__).parent

for f in sorted(root.rglob("*.md")):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", f.read_text(encoding="utf-8"), re.S)
    if not m:
        print("SKIP (нет шапки):", f); continue
    meta, body = yaml.safe_load(m.group(1)), m.group(2)
    r = httpx.post(f"{BASE}/admin/kb/ingest", verify=False,   # verify=False for a while no trusted CA
        headers={"Authorization": f"Bearer {token}"},
        json={**meta, "text": body}, timeout=300)
    print(f, r.status_code, r.json())