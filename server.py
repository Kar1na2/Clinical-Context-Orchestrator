import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clinical-context-orchestrator")
FHIR_EHR = "http://localhost:8080/fhir"
FHIR_LAB = "http://localhost:8081/fhir"


def resolve_patient_id(server_url: str, synthea_id: str) -> str | None:
    """Use Synthea UUID to look up the local patient ID on a given server."""
    try:
        resp = httpx.get(
            f"{server_url}/Patient",
            params={"identifier": synthea_id, "_format": "json"},
            timeout=10,
        )
        entries = resp.json().get("entry", [])
        return entries[0]["resource"]["id"] if entries else None
    except httpx.ConnectError:
        return None
    except httpx.TimeoutException:
        return None


@mcp.tool()
def get_medications(patient_id: str):
    """Get active medications for a patient from the EHR system (server 1)."""
    try:
        local_id = resolve_patient_id(FHIR_EHR, patient_id)
        if not local_id:
            return {"error": f"Patient {patient_id} not found in EHR system (server may be down)"}
        resp = httpx.get(
            f"{FHIR_EHR}/MedicationRequest",
            params={"patient": local_id, "_format": "json"},
            timeout=10,
        )
        entries = resp.json().get("entry", [])
        return [
            {
                "medication": e["resource"].get("medicationCodeableConcept", {}).get("text"),
                "status": e["resource"].get("status"),
                "authored_on": e["resource"].get("authoredOn"),
            }
            for e in entries
        ]
    except httpx.ConnectError:
        return {"error": "EHR system (server 1) is unreachable"}
    except httpx.TimeoutException:
        return {"error": "EHR system (server 1) timed out"}


@mcp.tool()
def get_allergies(patient_id: str):
    """Get allergy list for a patient from the EHR system (server 1)."""
    try:
        local_id = resolve_patient_id(FHIR_EHR, patient_id)
        if not local_id:
            return {"error": f"Patient {patient_id} not found in EHR system (server may be down)"}
        resp = httpx.get(
            f"{FHIR_EHR}/AllergyIntolerance",
            params={"patient": local_id, "_format": "json"},
            timeout=10,
        )
        entries = resp.json().get("entry", [])
        return [
            {
                "substance": e["resource"].get("code", {}).get("text"),
                "criticality": e["resource"].get("criticality"),
                "status": e["resource"].get("clinicalStatus", {}).get("coding", [{}])[0].get("code"),
            }
            for e in entries
        ]
    except httpx.ConnectError:
        return {"error": "EHR system (server 1) is unreachable"}
    except httpx.TimeoutException:
        return {"error": "EHR system (server 1) timed out"}


@mcp.tool()
def get_recent_labs(patient_id: str):
    """Get recent lab results for a patient from the lab system (server 2)."""
    try:
        local_id = resolve_patient_id(FHIR_LAB, patient_id)
        if not local_id:
            return {"error": f"Patient {patient_id} not found in lab system (server may be down)"}
        resp = httpx.get(
            f"{FHIR_LAB}/Observation",
            params={"patient": local_id, "category": "laboratory", "_format": "json", "_count": 50, "_sort": "-date"},
            timeout=10,
        )
        entries = resp.json().get("entry", [])

        # Group labs by date, then return only the most recent date's results
        by_date = {}
        for e in entries:
            r = e["resource"]
            date = r.get("effectiveDateTime", "")[:10]
            by_date.setdefault(date, []).append({
                "test": r.get("code", {}).get("text"),
                "value": r.get("valueQuantity", {}).get("value"),
                "unit": r.get("valueQuantity", {}).get("unit"),
            })

        if not by_date:
            return []
        latest_date = max(by_date.keys())
        return {"date": latest_date, "results": by_date[latest_date]}
    except httpx.ConnectError:
        return {"error": "Lab system (server 2) is unreachable"}
    except httpx.TimeoutException:
        return {"error": "Lab system (server 2) timed out"}


@mcp.tool()
def get_problem_list(patient_id: str):
    """Get the problem list (conditions/diagnoses) for a patient from the EHR system (server 1)."""
    try:
        local_id = resolve_patient_id(FHIR_EHR, patient_id)
        if not local_id:
            return {"error": f"Patient {patient_id} not found in EHR system (server may be down)"}
        resp = httpx.get(
            f"{FHIR_EHR}/Condition",
            params={"patient": local_id, "_format": "json"},
            timeout=10,
        )
        entries = resp.json().get("entry", [])
        return [
            {
                "condition": e["resource"].get("code", {}).get("text"),
                "status": e["resource"].get("clinicalStatus", {}).get("coding", [{}])[0].get("code"),
                "onset": e["resource"].get("onsetDateTime"),
            }
            for e in entries
        ]
    except httpx.ConnectError:
        return {"error": "EHR system (server 1) is unreachable"}
    except httpx.TimeoutException:
        return {"error": "EHR system (server 1) timed out"}


@mcp.tool()
def get_clinical_snapshot(patient_id: str):
    """Get a full clinical snapshot by querying both silos and merging results.
    Medications, allergies and problem list come from server 1. Labs come from server 2.
    """
    return {
        "patient_id": patient_id,
        "medications": get_medications(patient_id),
        "allergies": get_allergies(patient_id),
        "recent_labs": get_recent_labs(patient_id),
        "problem_list": get_problem_list(patient_id),
    }


def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
