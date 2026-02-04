"""Prometheus metrics for IFCB exporter."""

import argparse
import logging
import time
from datetime import datetime
from typing import Dict, Tuple

import requests
from prometheus_client import Gauge, start_http_server

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    "--lag-threshold-seconds",
    type=int,
    default=86400,
    help="Lag threshold in seconds to determine if dataset is up-to-date (default: 86400)",
)
parser.add_argument(
    "--lookback-seconds",
    type=int,
    default=1209600,
    help="Number of seconds to look back for bins (default: 1209600, which is 14 days)",
)
args = parser.parse_args()

BASE_URL = args.base_url
PORT = args.port
INTERVAL = args.interval
LAG_THRESHOLD_SECONDS = args.lag_threshold_seconds
LOOKBACK_SECONDS = args.lookback_seconds

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
    "latest_blobs_lag_seconds": Gauge(
        "ifcb_latest_blobs_lag_seconds",
        "Lag time for the latest blobs for dataset (seconds), or -1 if none exist",
        ["dataset"],
    ),
    "latest_features_timestamp": Gauge(
        "ifcb_latest_features_timestamp",
        "Last date features exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_features_lag_seconds": Gauge(
        "ifcb_latest_features_lag_seconds",
        "Lag time for the latest features for dataset (seconds), or -1 if none exist",
        ["dataset"],
    ),
    "latest_class_scores_timestamp": Gauge(
        "ifcb_latest_class_scores_timestamp",
        "Last date class scores exist for dataset (Unix timestamp), or 0 if none exist",
        ["dataset"],
    ),
    "latest_class_scores_lag_seconds": Gauge(
        "ifcb_latest_class_scores_lag_seconds",
        "Lag time for the latest class scores for dataset (seconds), or -1 if none exist",
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

    # Initialize timestamp result with cached values if they exist and are not 0
    result = {}
    for key in CLASSIFICATION_OUTPUT_GAUGES:
        if "timestamp" in key:
            cached_value = classification_cache.get((dataset, key))
            if cached_value and cached_value > 0:  # Ignore 0 (no data) values
                result[key] = cached_value

    # Set latest_bin_timestamp to the most recent bin if bins exist
    if bins:
        latest_bin_timestamp = next(iter(bins.values()))  # First value in sorted dict
        result["latest_bin_timestamp"] = latest_bin_timestamp
        classification_cache[(dataset, "latest_bin_timestamp")] = latest_bin_timestamp

    # if we don't have all three product timestamps cached (or they're 0), check all bins
    product_timestamps = [
        k
        for k in CLASSIFICATION_OUTPUT_GAUGES
        if "timestamp" in k and k != "latest_bin_timestamp"
    ]
    cached_product_timestamps = [
        k
        for k in product_timestamps
        if (dataset, k) in classification_cache
        and classification_cache[(dataset, k)] > 0  # Must have real data, not 0
    ]

    if len(cached_product_timestamps) < len(product_timestamps):
        bins_to_check = bins
    else:
        # Only check amount of bins for seconds in lookback_seconds from latest bin
        lookback = latest_bin_timestamp - LOOKBACK_SECONDS  # seconds
        bins_to_check = {
            pid: sample_time
            for pid, sample_time in bins.items()
            if sample_time >= lookback
        }

    for bin, bin_date in bins_to_check.items():
        # Get the oldest cached product timestamp (exclude latest_bin_timestamp)
        product_timestamps_in_result = [
            v
            for k, v in result.items()
            if k != "latest_bin_timestamp" and "timestamp" in k and v > 0
        ]
        oldest_cached = (
            min(product_timestamps_in_result) if product_timestamps_in_result else None
        )
        # Stop checking if this bin is older than our cached data (bins are newest-to-oldest)
        if oldest_cached and bin_date <= oldest_cached:
            break

        url = f"{BASE_URL}/has_products/{bin}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Check each product type (blobs, features, class_scores)
            for product in ["blobs", "features", "class_scores"]:
                api_key = f"has_{product}"
                timestamp_key = f"latest_{product}_timestamp"

                if data.get(api_key, False):
                    # If we don't have this timestamp yet, or this bin is newer
                    if timestamp_key not in result or bin_date > result[timestamp_key]:
                        result[timestamp_key] = bin_date
                        classification_cache[(dataset, timestamp_key)] = bin_date

        except requests.exceptions.HTTPError as e:
            # If we get a 500 or 502 error, skip this bin and continue checking older bins
            # this error occurs when the api is missing all three products for a bin
            # but we want to keep checking older bins in case they have products
            if e.response.status_code == 500:
                continue
            if e.response.status_code == 502:
                continue
            else:
                raise

    # Calculate lag and up_to_date metrics based on timestamps we found
    if "latest_bin_timestamp" in result:
        for product in ["blobs", "features", "class_scores"]:
            timestamp_key = f"latest_{product}_timestamp"
            lag_key = f"latest_{product}_lag_seconds"

            if timestamp_key in result:
                # Calculate lag: latest_bin_timestamp - product timestamp
                lag_seconds = result["latest_bin_timestamp"] - result[timestamp_key]
                result[lag_key] = lag_seconds
                classification_cache[(dataset, lag_key)] = lag_seconds
            else:
                # No product found after checking bins, cache timestamp as 0
                result[timestamp_key] = 0
                classification_cache[(dataset, timestamp_key)] = 0
                # Set lag to -1 to indicate no data
                result[lag_key] = -1
                classification_cache[(dataset, lag_key)] = -1

        # Calculate is_dataset_up_to_date: compare latest bin to current time
        bin_lag_seconds = time.time() - result["latest_bin_timestamp"]
        is_lagging = int(bin_lag_seconds > LAG_THRESHOLD_SECONDS)

        result["is_dataset_up_to_date"] = is_lagging
        classification_cache[(dataset, "is_dataset_up_to_date")] = is_lagging

    # If still no data found (no bins), cache that we checked
    if not result:
        for key in CLASSIFICATION_OUTPUT_GAUGES:
            # Set lag metrics to -1 to indicate no data (vs 0 which means current)
            if "_lag" in key:
                classification_cache[(dataset, key)] = -1
            else:
                classification_cache[(dataset, key)] = 0
        return None

    return result


def update_classification_output_metrics(dataset):
    """Update Prometheus gauges for data existence for a dataset."""
    output = check_classification_output(dataset)

    for key in CLASSIFICATION_OUTPUT_GAUGES:
        # Set gauge: -1 for lag metrics if not found (no data), 0 for timestamps
        if output is None:
            value = -1 if "_lag" in key else 0
        else:
            value = output.get(key, -1 if "_lag" in key else 0)
        CLASSIFICATION_OUTPUT_GAUGES[key].labels(dataset=dataset).set(value)


def main():
    """Main function to start the Prometheus exporter."""
    logger.info(f"Starting IFCB Prometheus Exporter on port {PORT}")
    logger.info(f"Base URL: {BASE_URL}")
    logger.info(f"Update interval: {INTERVAL} seconds")
    logger.info(f"Lag threshold: {LAG_THRESHOLD_SECONDS} seconds")
    logger.info(f"Lookback period: {LOOKBACK_SECONDS} seconds")

    # Start Prometheus metrics server on the specified port
    start_http_server(PORT)
    while True:
        try:
            # Fetch and update metrics for all datasets
            datasets = get_dataset_list()
            logger.info(f"Fetching metrics for {len(datasets)} datasets")

            for dataset in datasets:
                logger.debug(f"Processing dataset: {dataset}")

                for metric in TIMELINE_METRICS:
                    latest_value, latest_value_time = fetch_latest_data(metric, dataset)
                    if latest_value is not None and latest_value_time is not None:
                        update_metric(metric, dataset, latest_value, latest_value_time)
                update_classification_output_metrics(dataset)

            logger.info("Successfully updated metrics for all datasets")
        except Exception as e:
            # log error but keep running
            logger.error(f"Error updating metrics: {e}", exc_info=True)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
