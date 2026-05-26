import httpx

SERVER = "http://localhost:8080/fhir"
OUTPUT = "patient_info.md"

resp = httpx.get(f"{SERVER}/Patient", params={"_format": "json", "_count": 300}, timeout=30)
entries = resp.json().get("entry", [])

rows = []
for entry in entries:
    resource = entry["resource"]
    name = resource.get("name", [{}])[0]
    full_name = " ".join(name.get("given", []) + [name.get("family", "")])
    birthdate = resource.get("birthDate", "N/A")
    synthea_id = next(
        (i["value"] for i in resource.get("identifier", []) if "synthea" in i.get("system", "")),
        "N/A",
    )
    rows.append((full_name, birthdate, synthea_id))

header = f"{'Name':<30} {'Birthdate':<15} {'Synthea UUID'}\n" + "-" * 80
body = "\n".join(f"{name:<30} {birthdate:<15} {sid}" for name, birthdate, sid in rows)
output = f"{header}\n{body}\n"

print(f"Found {len(rows)} patients\n")
print(output)

with open(OUTPUT, "w") as f:
    f.write(output)

print(f"Saved {len(rows)} patients to {OUTPUT}")
