"""Prometheus metrics for IFCB exporter."""

import argparse

# import re
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
parser.add_argument(
    "--interval",
    type=int,
    default=900,
    help="Interval in seconds between metric updates (default: 900)",
)
parser.add_argument(
    "--lag-threshold-hours",
    type=int,
    default=24,
    help="Lag threshold in hours to determine if dataset is up-to-date (default: 24)",
)
parser.add_argument(
    "--lookback-days",
    type=int,
    default=14,
    help="Number of days to look back for bins (default: 14)",
)
args = parser.parse_args()

BASE_URL = args.base_url
PORT = args.port
INTERVAL = args.interval
LAG_THRESHOLD_HOURS = args.lag_threshold_hours
LOOKBACK_DAYS = args.lookback_days

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
    "latest_bin_timestamp": Gauge(
        "ifcb_latest_bin_timestamp",
        "Last bin date for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_blobs_timestamp": Gauge(
        "ifcb_latest_blobs_timestamp",
        "Last date blobs exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_blobs_lag": Gauge(
        "ifcb_latest_blobs_lag",
        "Lag time for the latest blobs for dataset (hours), or 100000 if none exist",
        ["dataset"],
    ),
    "latest_features_timestamp": Gauge(
        "ifcb_latest_features_timestamp",
        "Last date features exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_features_lag": Gauge(
        "ifcb_latest_features_lag",
        "Lag time for the latest features for dataset (hours), or 100000 if none exist",
        ["dataset"],
    ),
    "latest_class_scores_timestamp": Gauge(
        "ifcb_latest_class_scores_timestamp",
        "Last date class scores exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_class_scores_lag": Gauge(
        "ifcb_latest_class_scores_lag",
        "Lag time for the latest class scores for dataset (hours), or 100000 if none exist",
        ["dataset"],
    ),
    "is_dataset_up_to_date": Gauge(
        "ifcb_is_dataset_up_to_date",
        "Indicates if the dataset is lagging (0) or up-to-date (1)",
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
    # return dict of bins and sample_times (converted to Unix timestamps)
    # sorted by sample_time descending
    bins = {
        item["pid"]: int(
            datetime.strptime(item["sample_time"], "%Y-%m-%dT%H:%M:%SZ").timestamp()
        )
        for item in sorted(data, key=lambda x: x["sample_time"], reverse=True)
    }
    return bins


def check_classification_output(dataset):
    """Find the most recent date where each classification output exists for a dataset."""
    bins = fetch_bins(dataset)

    # Initialize timestamp result with cached values if they exist
    result = {}
    for key in CLASSIFICATION_OUTPUT_GAUGES:
        if "timestamp" in key:
            cached_value = classification_cache.get((dataset, key))
            if cached_value:
                result[key] = cached_value

    # Set latest_bin_timestamp to the most recent bin if bins exist
    if bins:
        latest_bin_timestamp = next(iter(bins.values()))  # First value in sorted dict
        result["latest_bin_timestamp"] = latest_bin_timestamp
        classification_cache[(dataset, "latest_bin_timestamp")] = latest_bin_timestamp

    # if we don't have all three product timestamps cached, check all bins
    product_timestamps = [
        k
        for k in CLASSIFICATION_OUTPUT_GAUGES
        if "timestamp" in k and k != "latest_bin_timestamp"
    ]
    cached_product_timestamps = [
        k for k in product_timestamps if (dataset, k) in classification_cache
    ]

    if len(cached_product_timestamps) < len(product_timestamps):
        bins_to_check = bins
    else:
        # Only check amount of bins for days in lookback_days
        lookback = time.time() - (LOOKBACK_DAYS * 24 * 3600)  # days to seconds
        bins_to_check = {
            pid: sample_time
            for pid, sample_time in bins.items()
            if sample_time >= lookback
        }
        # if no bins in last two weeks, check all bins
        if not bins_to_check:
            bins_to_check = bins

    for bin, bin_date in bins_to_check.items():
        # Get the oldest cached date among all keys
        oldest_cached = min(result.values()) if result else None
        # Stop checking if this bin is older than our cached data (bins are newest-to-oldest)
        if oldest_cached and bin_date <= oldest_cached:
            break

        url = f"{BASE_URL}/has_products/{bin}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Update any keys that are true and newer than cached
            for key in CLASSIFICATION_OUTPUT_GAUGES:
                # Skip latest_bin_timestamp - already handled above
                if key == "latest_bin_timestamp":
                    continue

                # if the product exists for this bin
                # data shows 'has_blobs', 'has_features', 'has_class_scores'
                # convert key to match
                data_key = (
                    key.replace("latest_", "has_")
                    .replace("_timestamp", "")
                    .replace("_lag", "")
                )
                if data.get(data_key, False):
                    # if we don't have a value yet, or this bin is newer than what we have in cache
                    if not result.get(key) or bin_date > result.get(key, 0):
                        # Update result
                        if "timestamp" in key:
                            result[key] = bin_date
                            # Update cache
                            classification_cache[(dataset, key)] = bin_date
                        elif "lag" in key:
                            # Calculate lag in hours: latest_bin_timestamp - product timestamp
                            lag_hours = (
                                result["latest_bin_timestamp"] - bin_date
                            ) / 3600.0
                            # Update result
                            result[key] = lag_hours
                            # Update cache
                            classification_cache[(dataset, key)] = lag_hours
                        elif "is_dataset_up_to_date" in key:
                            # Calculate lag in hours: latest_bin_timestamp - product timestamp
                            lag_hours = (
                                result["latest_bin_timestamp"] - bin_date
                            ) / 3600.0
                            # Determine if lagging
                            is_lagging = 0 if lag_hours > LAG_THRESHOLD_HOURS else 1
                            # Update result
                            result[key] = is_lagging
                            # Update cache
                            classification_cache[(dataset, key)] = is_lagging

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 500:
                continue
            else:
                raise

    # If still no data found, cache that we checked
    if not result:
        for key in CLASSIFICATION_OUTPUT_GAUGES:
            # Set lag metrics to 100000 to indicate no data (vs 0 which means current)
            if "_lag" in key:
                classification_cache[(dataset, key)] = 100000
            else:
                classification_cache[(dataset, key)] = 0
        return None

    return result


def update_classification_output_metrics(dataset):
    """Update Prometheus gauges for data existence for a dataset."""
    output = check_classification_output(dataset)

    for key in CLASSIFICATION_OUTPUT_GAUGES:
        # Set gauge: 100000 for lag metrics if not found (no data), 0 for timestamps
        if output is None:
            value = 100000 if "_lag" in key else 0
        else:
            value = output.get(key, 100000 if "_lag" in key else 0)
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

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
