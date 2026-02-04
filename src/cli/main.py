import sys
import csv
import io
import requests
import json

VALID_OPTIONS = ["demo", "small", "large"]
API_BASE_URL = "http://localhost:8000"

aggregated_results = {
    "patients": {},
    "totals": {}
}


def get_choice() -> str:
    """Gets the export size choice from user input."""

    if len(sys.argv) > 1:
        return sys.argv[1].lower()

    choice = input(
        "Please choose from one of the following: demo, small, or large: "
    ).strip().lower()

    return choice

def validate_choice(choice: str) -> str:
    """Validates the choice against VALID_OPTONS, exit if invalid."""

    if choice not in VALID_OPTIONS:
        print("Invalid option")
        sys.exit(1)
    return choice

def get_export_download_ids(size: str) -> list[str]:
    """Fetches the list of download IDs for the specified export size."""

    url = f"{API_BASE_URL}/api/export/{size}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        download_ids = data.get('data', {}).get('download_ids', [])
        return download_ids
    except requests.RequestException as e:
        print(f"Fetching export download_ids failed: {e}")
        sys.exit(1)

def read_download_data_stream(size: str, download_id:str) -> dict:
    """Fetches the metadata for a specific download ID."""

    url = f"{API_BASE_URL}/api/export/{size}/{download_id}/data"
    try:
        with requests.get(url, stream=True, timeout=(5, 300)) as r:
            r.raise_for_status()

            text_stream = io.TextIOWrapper(
                r.raw, encoding="utf-8", newline=""
            )
            reader = csv.DictReader(text_stream)

            for row in reader:
                patient_id = row.get('patient_id')
                event_type = row.get('event_type')
                value = row.get('value')
                
                 # Skip invalid rows for now; we can also exit early and return error (whichever preffered)
                if not patient_id or not event_type or not value:
                    print("Invalid row data:", row)
                    continue 
                
                # Process and Aggregate results:
                # if new patient in aggregated_results, initialize
                if patient_id not in aggregated_results["patients"]:
                    aggregated_results["patients"][patient_id] = {}
                
                # if existing patient in aggregated_results, but new event_type, initialize event_type data
                if patient_id in aggregated_results["patients"] and not event_type in aggregated_results["patients"][patient_id]:
                    aggregated_results["patients"][patient_id][event_type] = value

                # else if existing patient in aggregated_results, and existing event_type, update event_type totals
                elif patient_id in aggregated_results["patients"] and event_type in aggregated_results["patients"][patient_id]:
                    # Assuming value is numeric for aggregation
                    try:
                        existing_value = float(aggregated_results["patients"][patient_id][event_type])
                        new_value = float(value)
                        aggregated_results["patients"][patient_id][event_type] = existing_value + new_value
                    except ValueError:
                        print(f"Non-numeric value encountered for patient {patient_id}, event {event_type}: {value}")
                        continue  # Skip non-numeric values for aggregation

                # Update totals in aggregated_results
                aggregated_results["totals"][event_type] = aggregated_results["totals"].get(event_type, 0) + float(value)

    except requests.exceptions.RequestException as e:
        # Network / HTTP issues
        raise RuntimeError(f"CSV stream request failed: {e}") from e

    except csv.Error as e:
        # CSV parsing errors (rare but real)
        raise RuntimeError(f"CSV parsing failed: {e}") from e

    except UnicodeDecodeError as e:
        # Encoding issues
        raise RuntimeError(f"CSV decoding failed: {e}") from e


def main():
    choice = get_choice()
    validate_choice(choice)

    export_download_ids = get_export_download_ids(choice)
    if len(export_download_ids) == 0:
        print("No download IDs found for the selected export size.")
        sys.exit(1)
        
    print(f"Found {len(export_download_ids)} download_ids for export sized {choice}")
    print(f"Processing {len(export_download_ids)} download for {choice} export...")

    for idx, download_id in enumerate(export_download_ids):
        read_download_data_stream(choice, download_id)
        print(f"Processed download {idx + 1} of {len(export_download_ids)}: {download_id}..")

    print("Processing completed.")
    print("Aggregated Results:")
    print(json.dumps(
        aggregated_results,
        sort_keys=True,
        indent=4,
        separators=(',', ': ')
    ))

if __name__ == "__main__":
    main()