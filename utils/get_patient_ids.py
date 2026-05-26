import httpx

SERVER = "http://localhost:8080/fhir"

resp = httpx.get(f"{SERVER}/Patient", params={"_format": "json", "_count": 300}, timeout=30)
entries = resp.json().get("entry", [])

print(f"Found {len(entries)} patients\n")
for entry in entries:
    resource = entry["resource"]
    local_id = resource["id"]
    name = resource.get("name", [{}])[0]
    full_name = " ".join(name.get("given", []) + [name.get("family", "")])
    synthea_id = next(
        (i["value"] for i in resource.get("identifier", []) if "synthea" in i.get("system", "")),
        "N/A"
    )
    print(f"{full_name:<30} local_id={local_id:<6} synthea_uuid={synthea_id}")
