# Clinical-Context-Orchestrator

## Setup

Firstly for setting up the demonstration with 2 separate servers run the following

```bash
# Silo 1 — Primary Care, R4, port 8080
docker run -d --name primary_care -p 8080:8080 hapiproject/hapi:latest

# Silo 2 — Cardiology, DSTU2, port 8081
docker run -d --name cardiology -p 8081:8080 \
  -e hapi.fhir.fhir_version=DSTU2 \
  hapiproject/hapi:latest
```

This will set up the engine for both servers, then we can populate it using [synthea](https://synthea.mitre.org/)

1. Install Synthea first (this step has already been done for you)
```bash
curl -L -o synthea-with-dependencies.jar \
  https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
```

2. Generate the data (also done for you both are contained in this repository already) | for the interest of showing as demonstration it will be a small size of 12 patients
```bash
java -jar synthea-with-dependencies.jar -p 10 -s 1 \
  --exporter.fhir.export=true \
  --exporter.hospital.fhir.export=true \
  --exporter.practitioner.fhir.export=true \
  --exporter.fhir_dstu2.export=true \
  --exporter.hospital.fhir_dstu2.export=true \
  --exporter.practitioner.fhir_dstu2.export=true \
  Massachusetts
```

3. Populate the engine with the dataset we have created 
```bash
# R4 -> Primary Care (8080)
cd output/fhir
for f in hospitalInformation*.json practitionerInformation*.json; do
  curl -sS -X POST http://localhost:8080/fhir \
    -H "Content-Type: application/fhir+json" --data-binary @"$f" -o /dev/null
done
for f in $(ls *.json | grep -vE 'hospitalInformation|practitionerInformation'); do
  curl -sS -X POST http://localhost:8080/fhir \
    -H "Content-Type: application/fhir+json" --data-binary @"$f" -o /dev/null
done

# DSTU2 -> Cardiology (8081)
cd ../fhir_dstu2
for f in hospitalInformation*.json practitionerInformation*.json; do
  curl -sS -X POST http://localhost:8081/fhir \
    -H "Content-Type: application/fhir+json" --data-binary @"$f" -o /dev/null
done
for f in $(ls *.json | grep -vE 'hospitalInformation|practitionerInformation'); do
  curl -sS -X POST http://localhost:8081/fhir \
    -H "Content-Type: application/fhir+json" --data-binary @"$f" -o /dev/null
done
```

4. We can verify that both are working fine through 
```bash
curl -s "http://localhost:8080/fhir/MedicationRequest?_count=1"   # R4
curl -s "http://localhost:8081/fhir/MedicationOrder?_count=1"     # DSTU2
```

both should give the same result