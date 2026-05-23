import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server")

@mcp.tool()
def get_medications(patient_id: str = "5cbc121b-cd71-4428-b8b7-31e53eba8184"):
    """Get active medications for a patient"""
    # In the future, this will query the HAPI server for 'MedicationRequest' resources
    return [
        {
            "medication": "Lisinopril 10mg Oral Tablet",
            "status": "active",
            "date_prescribed": "2023-05-10",
            "dosage_instruction": "Take 1 tablet by mouth daily"
        },
        {
            "medication": "Atorvastatin 20mg Oral Tablet",
            "status": "active",
            "date_prescribed": "2023-05-10",
            "dosage_instruction": "Take 1 tablet by mouth daily at bedtime"
        }
    ]

@mcp.tool()
def get_recent_labs(patient_id: str = "5cbc121b-cd71-4428-b8b7-31e53eba8184"):
    """Get recent lab results for a patient"""
    # In the future, this will query 'Observation' resources where category is 'laboratory'
    return [
        {
            "test_name": "Hemoglobin A1c",
            "value": 5.8,
            "unit": "%",
            "date": "2024-01-15",
            "reference_range": "4.0 - 5.6"
        },
        {
            "test_name": "Low Density Lipoprotein Cholesterol",
            "value": 110,
            "unit": "mg/dL",
            "date": "2024-01-15",
            "reference_range": "< 100"
        }
    ]

@mcp.tool()
def get_allergies(patient_id: str = "5cbc121b-cd71-4428-b8b7-31e53eba8184"): 
    """Get list of allergies from a patient"""
    # In the future, this will query 'AllergyIntolerance' resources
    return [
        {
            "substance": "Penicillin",
            "reaction": "Hives",
            "severity": "moderate",
            "status": "active"
        }
    ]
    
def main():
    mcp.run(transport="stdio")
    
if __name__ == "__main__":
    main()