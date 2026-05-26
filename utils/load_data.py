"""
Split Synthea FHIR bundles and load into two HAPI FHIR containers:
  Container 1 (port 8080) — EHR/Pharmacy: Patient, MedicationRequest, AllergyIntolerance
  Container 2 (port 8081) — Lab System:   Patient, Observation (lab category only)
"""

import json
import os
import glob
import time
import httpx

SYNTHEA_DIR = os.path.expanduser("~/workato_data")
SERVER_1 = "http://localhost:8080/fhir"
SERVER_2 = "http://localhost:8081/fhir"

# Set to None to process all files
LIMIT = 300

# Infrastructure resources referenced by clinical resources — included in both bundles
# so that urn:uuid: placeholders (e.g. Encounter, Practitioner) always resolve.
INFRA_TYPES = {"Encounter", "Practitioner", "PractitionerRole", "Organization", "Location", "Condition"}

SERVER_1_TYPES = {"Patient", "MedicationRequest", "AllergyIntolerance"} | INFRA_TYPES
SERVER_2_TYPES = {"Patient", "Observation"} | INFRA_TYPES


def is_lab_observation(resource: dict) -> bool:
    """Return True only for Observation resources categorised as laboratory."""
    for cat in resource.get("category", []):
        for coding in cat.get("coding", []):
            if coding.get("code") == "laboratory":
                return True
    return False


def split_bundle(entries: list) -> tuple[list, list]:
    """Return (entries_for_server1, entries_for_server2)."""
    s1, s2 = [], []
    for entry in entries:
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")

        if rtype in SERVER_1_TYPES:
            s1.append(entry)

        if rtype in SERVER_2_TYPES:
            if rtype == "Observation" and not is_lab_observation(resource):
                continue
            s2.append(entry)

    return s1, s2


def make_transaction_bundle(entries: list) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries,
    }


def post_bundle(client: httpx.Client, server_url: str, bundle: dict) -> bool:
    try:
        resp = client.post(server_url, json=bundle, timeout=30)
        resp.raise_for_status()
        return True
    except (httpx.HTTPStatusError, Exception):
        return False


def main():
    files = sorted(glob.glob(os.path.join(SYNTHEA_DIR, "*.json")))
    if LIMIT:
        files = files[:LIMIT]
    print(f"Loading {len(files)} files...")

    ok1 = ok2 = fail1 = fail2 = 0

    with httpx.Client() as client:
        for i, path in enumerate(files, 1):
            with open(path) as f:
                bundle = json.load(f)

            entries = bundle.get("entry", [])
            s1_entries, s2_entries = split_bundle(entries)

            print(f"\r[{i}/{len(files)}]", end="", flush=True)

            if s1_entries:
                if post_bundle(client, SERVER_1, make_transaction_bundle(s1_entries)):
                    ok1 += 1
                else:
                    fail1 += 1

            if s2_entries:
                if post_bundle(client, SERVER_2, make_transaction_bundle(s2_entries)):
                    ok2 += 1
                else:
                    fail2 += 1

            time.sleep(0.2)

    print(f"\nDone.")
    print(f"  Server 1 — success: {ok1}, failed: {fail1}")
    print(f"  Server 2 — success: {ok2}, failed: {fail2}")


if __name__ == "__main__":
    main()
