"""Prometheus metrics for IFCB exporter."""

import argparse
import re
import time

from datetime import datetime
from typing import Dict, Tuple

import requests

from prometheus_client import Gauge, start_http_server


parser = argparse.ArgumentParser(description="IFCB Prometheus Exporter")
parser.add_argument(
    "--base-url",
    required=True,
    help="Base URL for the IFCB API (e.g., https://ifcb.caloos.org/api)",
)
parser.add_argument(
    "--port",
    type=int,
    default=8000,
    help="Port to expose Prometheus metrics on (default: 8000)",
)
args = parser.parse_args()

BASE_URL = args.base_url
PORT = args.port

TIMELINE_METRICS = {
    "size": "Bytes",
    "temperature": "Degrees C",
    "humidity": "Percentage",
    "run_time": "Seconds",
    "look_time": "Seconds",
    "ml_analyzed": "Milliliters",
    "concentration": "ROIs / ml",
    "n_triggers": "Count",
    "n_images": "Count",
}

# Add gauges for data existence checks
CLASSIFICATION_OUTPUT_GAUGES = {
    "has_blobs": Gauge(
        "ifcb_has_blobs",
        "Last date blobs exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "has_features": Gauge(
        "ifcb_has_features",
        "Last date features exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "has_class_scores": Gauge(
        "ifcb_has_class_scores",
        "Last date class scores exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
}

# Gauges with dataset label
GAUGES = {}
for metric, unit in TIMELINE_METRICS.items():
    GAUGES[metric] = {
        "value": Gauge(
            f"ifcb_{metric}_value", f"Latest {metric} in {unit}", ["dataset"]
        ),
        "timestamp": Gauge(
            f"ifcb_{metric}_timestamp",
            f"Timestamp of latest {metric} value",
            ["dataset"],
        ),
    }

classification_cache: Dict[Tuple[str, str], str] = {}  # {(dataset, key): date_string}


def update_metric(metric, dataset, latest_value, latest_value_time):
    """Update the Prometheus gauges for a given metric and dataset."""
    GAUGES[metric]["value"].labels(dataset=dataset).set(latest_value)
    GAUGES[metric]["timestamp"].labels(dataset=dataset).set(
        latest_value_time
    )  # Use a Unix timestamp (seconds since epoch)


def get_metrics_api_call(metric, ds, res="bin"):
    """Construct the API call URL."""
    return f"{BASE_URL}/time-series/{metric}?resolution={res}&dataset={ds}"


def get_dataset_list():
    """Fetch the list of datasets from the IFCB API."""
    url = f"{BASE_URL}/filter_options?"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    return data.get("dataset_options", [])


def fetch_latest_data(metric, dataset):
    """Fetch the latest data for a given metric and dataset from the IFCB API."""
    url = get_metrics_api_call(metric, ds=dataset, res="bin")
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    # if no data returned, return None
    if not data:
        return None, None
    # get the latest value and its timestamp
    latest_value = data["y"][-1]
    latest_value_time = int(
        datetime.strptime(data["x"][-1], "%Y-%m-%dT%H:%M:%SZ").timestamp()
    )
    return latest_value, latest_value_time


def fetch_bins(dataset):
    """Fetch the list of bins for a given dataset."""
    url = f"{BASE_URL}/list_bins?dataset={dataset}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()["data"]
    bins = [
        item["pid"]
        for item in sorted(data, key=lambda x: x["sample_time"], reverse=True)
    ]
    return bins


def get_date_from_bin(bin):
    """Extract date from bin name."""
    # bin example D20260114T160653_IFCB160
    match = re.search(r"D(\d{8})T", bin)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Invalid bin format: {bin}")


def check_classification_output(dataset):
    """Find the most recent date where each classification output exists for a dataset."""
    bins = fetch_bins(dataset)

    # Initialize result with cached values if they exist
    result = {}
    for key in CLASSIFICATION_OUTPUT_GAUGES:
        cached_value = classification_cache.get((dataset, key))
        if cached_value:
            result[key] = cached_value

    # If we have all three cached, we can still check a few recent bins for updates
    # Only check the first 10 bins (most recent)
    bins_to_check = bins[:10]

    for bin in bins_to_check:
        bin_date = get_date_from_bin(bin)

        # Get the oldest cached date among all keys
        oldest_cached = min(result.values()) if result else None
        # Skip if this bin is older than what we already have cached
        if oldest_cached and bin_date <= oldest_cached:
            break

        url = f"{BASE_URL}/has_products/{bin}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Update any keys that are true and newer than cached
            for key in CLASSIFICATION_OUTPUT_GAUGES:
                if data.get(key, False):
                    if not result.get(key) or bin_date > result[key]:
                        result[key] = bin_date
                        # Update cache
                        classification_cache[(dataset, key)] = bin_date

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 500:
                continue
            else:
                raise

    # If still no data found, cache that we checked
    if not result:
        for key in CLASSIFICATION_OUTPUT_GAUGES:
            classification_cache[(dataset, key)] = 0
        return None

    return result


def update_classification_output_metrics(dataset):
    """Update Prometheus gauges for data existence for a dataset."""
    output = check_classification_output(dataset)
    if output is None:
        # output will be None if all three products are False,
        # create output with all false values
        output = {key: 0 for key in CLASSIFICATION_OUTPUT_GAUGES}
    for key in CLASSIFICATION_OUTPUT_GAUGES:
        # Set gauge to 0 if false
        value = output.get(key, 0)
        CLASSIFICATION_OUTPUT_GAUGES[key].labels(dataset=dataset).set(value)


def main():
    """Main function to start the Prometheus exporter."""
    # Start Prometheus metrics server on the specified port
    start_http_server(PORT)
    while True:
        try:
            # Fetch and update metrics for all datasets
            for dataset in get_dataset_list():  # skip first dataset for testing

                for metric in TIMELINE_METRICS:
                    latest_value, latest_value_time = fetch_latest_data(metric, dataset)
                    if latest_value is not None and latest_value_time is not None:
                        update_metric(metric, dataset, latest_value, latest_value_time)
                update_classification_output_metrics(dataset)
        except Exception as e:
            # log error but keep running
            print(f"Error: {e}")

        time.sleep(900)  # wait 15 minutes


if __name__ == "__main__":
    main()
