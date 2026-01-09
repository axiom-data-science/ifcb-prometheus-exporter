"""Prometheus metrics for IFCB exporter."""

import argparse

from datetime import datetime
import re
import requests

from bs4 import BeautifulSoup

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
    "has_blobs": Gauge("ifcb_has_blobs", "Whether blobs exist for dataset (1=true, 0=false)", ["dataset"]),
    "has_features": Gauge("ifcb_has_features", "Whether features exist for dataset (1=true, 0=false)", ["dataset"]),
    "has_class_scores": Gauge("ifcb_has_class_scores", "Whether class scores exist for dataset (1=true, 0=false)", ["dataset"]),
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

def fetch_bin_id_from_html(dataset):
    """Scrape bin IDs from the HTML page for a dataset."""
    base = BASE_URL.replace('/api', '')
    url = f"{base}/bin?dataset={dataset}"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Adjust the selector below to match where bin IDs appear in the HTML
    script_text = "".join([script.text for script in soup.find_all("script")])
    match = re.search(r'_bin\s*=\s*"([^"]+)"', script_text)
    if match:
        current_bin = match.group(1)
    return current_bin  

def check_classification_output(dataset):
    """Check for the existence of blobs, features, and class scores for a dataset."""
    bin = fetch_bin_id_from_html(dataset)  
    url = f"{BASE_URL}/has_products/{bin}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError as e:
        # 500 error is returned if all three products are False, return None and address later
        return None
    # Example response: {"has_blobs": true, "has_features": true, "has_class_scores": true}
    return data


def update_classification_output_metrics(dataset):
    """Update Prometheus gauges for data existence for a dataset."""
    output = check_classification_output(dataset)
    if output is None:
        # output will be None if all three products are False,
        # create output with all false values
        output = {key: False for key in CLASSIFICATION_OUTPUT_GAUGES}
    for key in CLASSIFICATION_OUTPUT_GAUGES:
        # Set gauge to 1 if true, 0 if false
        value = 1 if output.get(key, False) else 0
        CLASSIFICATION_OUTPUT_GAUGES[key].labels(dataset=dataset).set(value)


def main():
    """Main function to start the Prometheus exporter."""
    # Start Prometheus metrics server on the specified port
    start_http_server(PORT)

    # Fetch and update metrics for all datasets
    for dataset in get_dataset_list():
        for metric in TIMELINE_METRICS:
            latest_value, latest_value_time = fetch_latest_data(metric, dataset)
            if latest_value is not None and latest_value_time is not None:
                update_metric(metric, dataset, latest_value, latest_value_time)
        update_classification_output_metrics(dataset)


if __name__ == "__main__":
    main()
