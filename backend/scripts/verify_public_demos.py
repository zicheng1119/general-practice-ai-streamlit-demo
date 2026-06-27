from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from uuid import uuid4

import httpx


EASY_BASE = "https://demo.easyappointments.org/index.php/api/v1"
EASY_AUTH = ("administrator", "administrator")
OPENMRS_BASE = "https://o3.openmrs.org/openmrs/ws/rest/v1"
OPENMRS_AUTH = ("admin", "Admin123")


def verify_easyappointments(write: bool) -> None:
    with httpx.Client(timeout=20.0, auth=EASY_AUTH) as client:
        services = client.get(f"{EASY_BASE}/services")
        services.raise_for_status()
        providers = client.get(f"{EASY_BASE}/providers")
        providers.raise_for_status()
        slots = client.get(
            f"{EASY_BASE}/availabilities",
            params={
                "providerId": 2,
                "serviceId": 1,
                "date": (date.today() + timedelta(days=1)).isoformat(),
            },
        )
        slots.raise_for_status()

        print("Easy!Appointments services:", len(services.json()))
        print("Easy!Appointments providers:", len(providers.json()))
        print("Easy!Appointments first slots:", slots.json()[:3])

        if not write:
            return

        unique = uuid4().hex[:8]
        customer_payload = {
            "firstName": "Codex",
            "lastName": f"Demo{unique[:4]}",
            "email": f"codex-{unique}@example.com",
            "phone": "0000000000",
            "city": "Demo",
            "timezone": "UTC",
            "language": "english",
            "notes": "Public demo verification",
        }
        customer = client.post(f"{EASY_BASE}/customers", json=customer_payload)
        customer.raise_for_status()
        customer_id = customer.json()["id"]

        slot_date = (date.today() + timedelta(days=1)).isoformat()
        appointment_payload = {
            "start": f"{slot_date} 09:30:00",
            "end": f"{slot_date} 10:00:00",
            "location": "Demo Clinic",
            "status": "Booked",
            "notes": "Codex public demo verification",
            "customerId": customer_id,
            "providerId": 2,
            "serviceId": 1,
        }
        appointment = client.post(f"{EASY_BASE}/appointments", json=appointment_payload)
        appointment.raise_for_status()
        appointment_id = appointment.json()["id"]

        print("Easy!Appointments created customer:", customer_id)
        print("Easy!Appointments created appointment:", appointment_id)


def verify_openmrs(write: bool) -> None:
    with httpx.Client(timeout=20.0, auth=OPENMRS_AUTH) as client:
        session = client.get(f"{OPENMRS_BASE}/session")
        session.raise_for_status()
        patient = client.get(
            f"{OPENMRS_BASE}/patient",
            params={"q": "john", "limit": 1, "v": "default"},
        )
        patient.raise_for_status()
        encounter_role = client.get(
            f"{OPENMRS_BASE}/encounterrole",
            params={"limit": 1, "v": "default"},
        )
        encounter_role.raise_for_status()
        encounter_type = client.get(
            f"{OPENMRS_BASE}/encountertype",
            params={"limit": 3, "v": "default"},
        )
        encounter_type.raise_for_status()

        print("OpenMRS authenticated:", session.json()["authenticated"])
        print("OpenMRS sample patient:", patient.json()["results"][0]["uuid"])
        print("OpenMRS encounter role:", encounter_role.json()["results"][0]["uuid"])
        print("OpenMRS encounter type:", encounter_type.json()["results"][1]["uuid"])

        if not write:
            return

        payload = {
            "patient": "5234b232-e779-4267-98fb-2bdef1e814b7",
            "location": "5a7f3c53-6bb4-448b-a966-5e65b397b9f3",
            "encounterType": "0e8230ce-bd1d-43f5-a863-cf44344fa4b0",
            "encounterDatetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0800"),
            "encounterProviders": [
                {
                    "provider": "bc7d2b01-482a-4219-8bfb-4f89b85b2079",
                    "encounterRole": "a0b03050-c99b-11e0-9572-0800200c9a66",
                }
            ],
        }
        encounter = client.post(f"{OPENMRS_BASE}/encounter", json=payload)
        encounter.raise_for_status()
        print("OpenMRS created encounter:", encounter.json()["uuid"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify public OSS demo integrations used by this project.")
    parser.add_argument("--write-easyappointments", action="store_true", help="Create a demo customer and appointment.")
    parser.add_argument("--write-openmrs", action="store_true", help="Create a demo encounter.")
    args = parser.parse_args()

    verify_easyappointments(write=args.write_easyappointments)
    verify_openmrs(write=args.write_openmrs)


if __name__ == "__main__":
    main()
