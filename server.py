import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("clinical-context-orchestrator")
SILOS = {
    "ehr": {"url": "http://localhost:8080/fhir", "version": "R4"},
    "lab": {"url": "http://localhost:8081/fhir", "version": "DSTU2"},
}

RESOURCE_NAMES = {
    "R4": {
        "medication": "MedicationRequest",
        "allergy": "AllergyIntolerance",
        "condition": "Condition",
        "observation": "Observation",
    },
    "DSTU2": {
        "medication": "MedicationOrder",
        "allergy": "AllergyIntolerance",
        "condition": "Condition",
        "observation": "Observation",
    },
}

def resolve_patient(silo, given_name, family_name, birthdate):
    """Return (local_id, status). status is one of:
    ok | not_found | ambiguous | unreachable. On 'ambiguous', local_id is the
    list of candidate ids."""
    try:
        resp = httpx.get(
            f"{silo['url']}/Patient",
            params={
                "given": given_name,
                "family": family_name,
                "birthdate": birthdate,  # search param is lowercase on both versions
                "_format": "json",
            },
            timeout=10,
        )
        entries = resp.json().get("entry", [])
    except (httpx.ConnectError, httpx.TimeoutException):
        return None, "unreachable"
    if not entries:
        return None, "not_found"
    if len(entries) > 1:
        return [e["resource"]["id"] for e in entries], "ambiguous"
    return entries[0]["resource"]["id"], "ok"


def _resolution_error(silo_name, status, local_id):
    if status == "unreachable":
        return {"error": f"{silo_name} silo is unreachable or timed out"}
    if status == "not_found":
        return {"error": f"No patient matched name + DOB in the {silo_name} silo"}
    if status == "ambiguous":
        return {
            "error": (
                f"Multiple patients matched in the {silo_name} silo "
                f"(ids: {local_id}) - refusing to guess; please disambiguate"
            )
        }
    return {"error": f"Could not resolve patient in the {silo_name} silo"}


def _norm_medication(r, version):
    return {
        "medication": (r.get("medicationCodeableConcept") or {}).get("text"),
        "status": r.get("status"),
        # field renamed across versions: R4 authoredOn  <->  DSTU2 dateWritten
        "authored_on": r.get("authoredOn") if version == "R4" else r.get("dateWritten"),
    }


def _norm_allergy(r, version):
    if version == "R4":
        substance = (r.get("code") or {}).get("text")
        status = (r.get("clinicalStatus") or {}).get("coding", [{}])[0].get("code")
    else:
        # DSTU2: the substance lives in .substance, and status is a plain code
        substance = (r.get("substance") or {}).get("text")
        status = r.get("status")
    return {"substance": substance, "criticality": r.get("criticality"), "status": status}


def _norm_condition(r, version):
    if version == "R4":
        status = (r.get("clinicalStatus") or {}).get("coding", [{}])[0].get("code")
    else:
        # DSTU2: clinicalStatus is a plain code string, not a CodeableConcept
        status = r.get("clinicalStatus")
    return {
        "condition": (r.get("code") or {}).get("text"),
        "status": status,
        "onset": r.get("onsetDateTime"),
    }


def _norm_observation(r, version):
    q = r.get("valueQuantity") or {}
    return {
        "test": (r.get("code") or {}).get("text"),
        "value": q.get("value"),
        "unit": q.get("unit"),
        "date": (r.get("effectiveDateTime") or "")[:10],
    }


# --- Fetch helpers (identity already resolved; query + normalize) ----------

def _search(silo, resource_key, params):
    """Search one silo for one resource type, using that silo's version to pick
    the resource name. Returns a list of entries, or None if the silo is down."""
    resource_type = RESOURCE_NAMES[silo["version"]][resource_key]
    try:
        resp = httpx.get(
            f"{silo['url']}/{resource_type}",
            params={**params, "_format": "json"},
            timeout=10,
        )
        return resp.json().get("entry", [])
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


def _fetch_medications(silo, local_id):
    entries = _search(silo, "medication", {"patient": local_id})
    if entries is None:
        return {"error": "silo unreachable while fetching medications"}
    return [_norm_medication(e["resource"], silo["version"]) for e in entries]


def _fetch_allergies(silo, local_id):
    entries = _search(silo, "allergy", {"patient": local_id})
    if entries is None:
        return {"error": "silo unreachable while fetching allergies"}
    return [_norm_allergy(e["resource"], silo["version"]) for e in entries]


def _fetch_problem_list(silo, local_id):
    entries = _search(silo, "condition", {"patient": local_id})
    if entries is None:
        return {"error": "silo unreachable while fetching problem list"}
    return [_norm_condition(e["resource"], silo["version"]) for e in entries]


def _fetch_recent_labs(silo, local_id):
    entries = _search(
        silo,
        "observation",
        {"patient": local_id, "category": "laboratory", "_count": 50, "_sort": "-date"},
    )
    if entries is None:
        return {"error": "silo unreachable while fetching labs"}
    # Group labs by date, then return only the most recent date's results.
    by_date = {}
    for e in entries:
        obs = _norm_observation(e["resource"], silo["version"])
        by_date.setdefault(obs["date"], []).append(
            {"test": obs["test"], "value": obs["value"], "unit": obs["unit"]}
        )
    if not by_date:
        return []
    latest_date = max(by_date.keys())
    return {"date": latest_date, "results": by_date[latest_date]}


# --- Tools -----------------------------------------------------------------
# Each public tool takes demographics, resolves identity in the right silo,
# then fetches. birthdate is "YYYY-MM-DD".

def _with_resolution(silo_name, given_name, family_name, birthdate, fetch):
    silo = SILOS[silo_name]
    local_id, status = resolve_patient(silo, given_name, family_name, birthdate)
    if status != "ok":
        return _resolution_error(silo_name, status, local_id)
    return fetch(silo, local_id)


@mcp.tool()
def get_medications(given_name: str, family_name: str, birthdate: str):
    """Get active medications from the EHR silo (server 1, R4)."""
    return _with_resolution("ehr", given_name, family_name, birthdate, _fetch_medications)


@mcp.tool()
def get_allergies(given_name: str, family_name: str, birthdate: str):
    """Get the allergy list from the EHR silo (server 1, R4)."""
    return _with_resolution("ehr", given_name, family_name, birthdate, _fetch_allergies)


@mcp.tool()
def get_problem_list(given_name: str, family_name: str, birthdate: str):
    """Get the problem list (conditions/diagnoses) from the EHR silo (server 1, R4)."""
    return _with_resolution("ehr", given_name, family_name, birthdate, _fetch_problem_list)


@mcp.tool()
def get_recent_labs(given_name: str, family_name: str, birthdate: str):
    """Get the most recent lab panel from the Lab silo (server 2, DSTU2)."""
    return _with_resolution("lab", given_name, family_name, birthdate, _fetch_recent_labs)


@mcp.tool()
def get_clinical_snapshot(given_name: str, family_name: str, birthdate: str):
    """Get a full clinical snapshot for one patient by querying both silos and
    merging the results. Identity is resolved per silo from name + DOB.
    EHR (R4) supplies medications, allergies, and problems; Lab (DSTU2) supplies labs.

    'resolved_ids' shows the DIFFERENT local id each silo assigned to the same
    person - the snapshot itself is proof the orchestrator stitched two distinct
    identifiers into one unified record."""
    ehr, lab = SILOS["ehr"], SILOS["lab"]
    ehr_id, ehr_status = resolve_patient(ehr, given_name, family_name, birthdate)
    lab_id, lab_status = resolve_patient(lab, given_name, family_name, birthdate)

    def ehr_section(fetch):
        return fetch(ehr, ehr_id) if ehr_status == "ok" else _resolution_error("ehr", ehr_status, ehr_id)

    return {
        "patient": {
            "given_name": given_name,
            "family_name": family_name,
            "birthdate": birthdate,
        },
        "resolved_ids": {
            "ehr": ehr_id if ehr_status == "ok" else f"<{ehr_status}>",
            "lab": lab_id if lab_status == "ok" else f"<{lab_status}>",
        },
        "medications": ehr_section(_fetch_medications),
        "allergies": ehr_section(_fetch_allergies),
        "problem_list": ehr_section(_fetch_problem_list),
        "recent_labs": (
            _fetch_recent_labs(lab, lab_id)
            if lab_status == "ok"
            else _resolution_error("lab", lab_status, lab_id)
        ),
    }


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()