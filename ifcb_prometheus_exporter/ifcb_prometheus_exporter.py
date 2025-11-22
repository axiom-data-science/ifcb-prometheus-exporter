"""Prometheus metrics for IFCB exporter."""

import requests
from datetime import datetime

from prometheus_client import Gauge, start_http_server

TIMELINE_METRICS = {
    "size": "Bytes",
    "temperature": "Degrees C",
    "humidity": "Percentage",
    "run_time": "Seconds",
    "look_time": "Seconds",
    "ml_analyzed": "Milliliters",
    'concentration': 'ROIs / ml',
    'n_triggers': 'Count',
    'n_images': 'Count',
}

BASE_URL = "https://ifcb.caloos.org/api"

# Gauges with dataset label
GAUGES = {}
for metric, unit in TIMELINE_METRICS.items():
    GAUGES[metric] = {
        "value": Gauge(f'ifcb_{metric}_value', f'Latest {metric} in {unit}', ['dataset']),
        "timestamp": Gauge(f'ifcb_{metric}_timestamp', f'Timestamp of latest {metric} value', ['dataset'])
    }


def update_metric(metric, dataset, latest_value, latest_value_time):
    """Update the Prometheus gauges for a given metric and dataset."""
    GAUGES[metric]["value"].labels(dataset=dataset).set(latest_value)
    GAUGES[metric]["timestamp"].labels(dataset=dataset).set(latest_value_time)  # Use a Unix timestamp (seconds since epoch)


def get_metrics_api_call(metric, ds, res='bin'):
    """Construct the API call URL."""
    return f"{BASE_URL}/time-series/{metric}?resolution={res}&dataset={ds}"


def get_dataset_list():
    """Fetch the list of datasets from the IFCB API."""
    url = f"{BASE_URL}/filter_options?"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    return data.get('dataset_options', [])


def fetch_latest_data(metric, dataset):
    """Fetch the latest data for a given metric and dataset from the IFCB API."""
    url = get_metrics_api_call(metric, ds=dataset, res='bin')
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    # if no data returned, return None
    if not data:
        return None, None
    # get the latest value and its timestamp
    latest_value = data['y'][-1]
    latest_value_time = int(datetime.strptime(data['x'][-1], "%Y-%m-%dT%H:%M:%SZ").timestamp())
    return latest_value, latest_value_time


def main():
    # Start Prometheus metrics server on port 8000 (you can choose another port if needed)
    start_http_server(8000)

    # Fetch and update metrics for all datasets
    for dataset in get_dataset_list():
        for metric in TIMELINE_METRICS:
            latest_value, latest_value_time = fetch_latest_data(metric, dataset)
            if latest_value is not None and latest_value_time is not None:
                update_metric(metric, dataset, latest_value, latest_value_time)


if __name__ == "__main__":
    main()