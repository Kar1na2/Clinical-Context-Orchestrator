import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clinical-context-orchestrator")
FHIR_EHR = "http://localhost:8080/fhir"
FHIR_LAB = "http://localhost:8081/fhir"

def resolve_patient_id(server_url: str, synthea_id: str) -> str | None:
    """Use synthea_UUID to look for patient_id in different server"""
    resp = httpx.get(
        f"{server_url}/Patient",
        params={"identifier": synthea_id, "_format": "json"},
        timeout=10,
    )
    entries = resp.json().get("entry", [])
    return entries[0]["resource"]["id"] if entries else None

@mcp.tool()
def get_medications(patient_id: str = "5cbc121b-cd71-4428-b8b7-31e53eba8184"):
    """Get active medications for a patient"""
    # In the future, this will query the HAPI server for 'MedicationRequest' resources
    local_id = resolve_patient_id(FHIR_EHR, patient_id)
    if not local_id:
        return {"error": f"Patient {patient_id} not found in EHR system"}
    resp = httpx.get(
        f"{FHIR_EHR}/MedicationRequest",
        params={"patient": local_id, "_format": "json"},
        timeout = 10,
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

@mcp.tool()
def get_allergies(patient_id: str): 
    """Get list of allergies from a patient"""
    # In the future, this will query 'AllergyIntolerance' resources
    local_id = resolve_patient_id(FHIR_EHR, patient_id)
    if not local_id:
        return {"error": f"Patient {patient_id} not found in EHR system"}
    resp = httpx.get(
        f"{FHIR_EHR}/AllergyIntolerance",
        params={"patient": local_id, "_format": "json"},
        timeout = 10,
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

@mcp.tool()
def get_recent_labs(patient_id: str):
    """Get recent lab results for a patient"""
    # In the future, this will query 'Observation' resources where category is 'laboratory'
    local_id = resolve_patient_id(FHIR_LAB, patient_id)
    if not local_id:
        return {"error": f"Patient {patient_id} not found in lab system"}
    resp = httpx.get(
        f"{FHIR_LAB}/Observation",
        params={"patient": local_id, "category": "laboratory", "_format": "json", "_count": 20},
        timeout=10,
    )
    entries = resp.json().get("entry", [])
    return [
        {
            "test": e["resource"].get("code", {}).get("text"),
            "value": e["resource"].get("valueQuantity", {}).get("value"),
            "unit": e["resource"].get("valueQuantity", {}).get("unit"),
            "date": e["resource"].get("effectiveDateTime"),
        }
        for e in entries
    ]
    
def get_clinical_snapshot(patient_id: str):
    """Get the full clinical snapshot of patient from different server database,
    Medications and allergies come from server 1, labs from server 2.
    """
    return {
        "patient_id": patient_id,
        "medications": get_medications(patient_id),
        "allergies": get_allergies(patient_id),
        "recent_labs": get_recent_labs(patient_id),
    }


def main():
    mcp.run(transport="stdio")
    
if __name__ == "__main__":
    main()