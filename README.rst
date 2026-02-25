IFCB Prometheus Exporter
===============================

A Prometheus exporter for Imaging FlowCytobot (IFCB) data. This tool collects metrics from IFCB instruments and exposes them in a format compatible with Prometheus monitoring systems, enabling real-time observability and integration with Grafana dashboards.

Copyright 2025 Axiom Data Science, LLC

See LICENSE for details.

Installation
------------

This project relies on conda for installation and managing of the project dependencies.

1. Download and install miniconda for your operating system https://docs.conda.io/en/latest/miniconda.html.

2. Clone this project with ``git``.

3.  Once conda is available build the environment for this project with::

      conda env create -f environment.yml

    The above command creates a new conda environment titled ``ifcb-prometheus-exporter`` with the necessary project
    dependencies.

    To update an existing environment with any changes to the dependencies use::

      conda env update -f environment.yml

4. An additional environment file is present for development and testing. The developer dependencies can be installed with::

   conda env update -f dev-environment.yml

5. To install the project to the new environment::

      conda activate ifcb-prometheus-exporter
      pip install -e .

Running Tests
-------------

To run the project's tests::

   pytest -sv --integration

Usage Example
-------------

To run the exporter and expose metrics on port 8000, you must specify the base URL for the IFCB API using the ``--base-url`` argument::

   python ifcb_prometheus_exporter/ifcb_prometheus_exporter.py --base-url https://ifcb.caloos.org/api

Then visit http://localhost:8000/metrics to view the metrics in Prometheus format. The exporter will use the provided base URL for data collection.

The following  are a list of the base URLs that can be used with this exporter:
   1. for Caloos: https://ifcb.caloos.org/api
   2. for WHOI: https://ifcb-data.whoi.edu/api
   3. for Salish Sea: https://salish-sea-ifcbdb.srv.axds.co/api
   4. for HABON: https://habon-ifcb.whoi.edu/api


Additional arguments can be specified:
  --interval: Update interval in seconds (default: 900)
  --port: Port to expose Prometheus metrics (default: 8000)
  --lag-threshold-seconds: Lag threshold in seconds to determine if dataset is up-to-date (default: 86400)
  --lookback-bins: Number of bins to look back for products (default: 20)
  --log-level: Logging level (default: INFO)
  --datasets: CSV list of specific datasets (default: all datasets in IFCB API)

Example with custom arguments::

   python ifcb_prometheus_exporter/ifcb_prometheus_exporter.py --base-url https://ifcb.caloos.org/api --interval 600 --port 9000 --lag-threshold-seconds 43200 --lookback-bins 10 --log-level DEBUG

You can also use the CLI entry point::

   python ifcb_prometheus_exporter/cli.py --base-url https://ifcb.caloos.org/api

Metrics Returned
-----------------
The exporter provides the following metrics:

- ``ifcb_latest_bin_timestamp{dataset="<dataset_name>"}``: Timestamp of the latest bin for the specified dataset (Unix timestamp), or 0 if none exist
- ``ifcb_is_dataset_up_to_date{dataset="<dataset_name>"}``: Indicates if the dataset is lagging (0) or up-to-date (1)
- ``ifcb_latest_blobs_timestamp{dataset="<dataset_name>"}``: Timestamp of the latest blobs for the specified dataset (Unix timestamp), or 0 if none exist
- ``ifcb_latest_blobs_lag_seconds{dataset="<dataset_name>"}``: Lag time for the latest blobs for dataset (seconds), or -1 if none exist
- ``ifcb_latest_features_timestamp{dataset="<dataset_name>"}``: Timestamp of the latest features for the specified dataset (Unix timestamp), or 0 if none exist
- ``ifcb_latest_features_lag_seconds{dataset="<dataset_name>"}``: Lag time for the latest features for dataset (seconds), or -1 if none exist
- ``ifcb_latest_class_scores_timestamp{dataset="<dataset_name>"}``: Timestamp of the latest class scores for the specified dataset (Unix timestamp), or 0 if none exist
- ``ifcb_latest_class_scores_lag_seconds{dataset="<dataset_name>"}``: Lag time for the latest class scores for dataset (seconds), or -1 if none exist
- ``ifcb_size_value{dataset="<dataset_name>"}``: Latest size value of the dataset in Bytes
- ``ifcb_size_timestamp{dataset="<dataset_name>"}``: Timestamp of latest size value
- ``ifcb_temperature_value{dataset="<dataset_name>"}``: Latest temperature in Degrees C
- ``ifcb_temperature_timestamp{dataset="<dataset_name>"}``: Timestamp of latest temperature value
- ``ifcb_humidity_value{dataset="<dataset_name>"}``: Latest humidity in Percentage
- ``ifcb_humidity_timestamp{dataset="<dataset_name>"}``: Timestamp of latest humidity value
- ``ifcb_run_time_value{dataset="<dataset_name>"}``: Latest run_time in Seconds
- ``ifcb_run_time_timestamp{dataset="<dataset_name>"}``: Timestamp of latest run_time value
- ``ifcb_look_time_value{dataset="<dataset_name>"}``: Latest look_time in Seconds
- ``ifcb_look_time_timestamp{dataset="<dataset_name>"}``: Timestamp of latest look_time value
- ``ifcb_ml_analyzed_value{dataset="<dataset_name>"}``: Latest ml_analyzed in Milliliters
- ``ifcb_ml_analyzed_timestamp{dataset="<dataset_name>"}``: Timestamp of latest ml_analyzed value
- ``ifcb_concentration_value{dataset="<dataset_name>"}``: Latest concentration in ROIs / ml
- ``ifcb_concentration_timestamp{dataset="<dataset_name>"}``: Timestamp of latest concentration value
- ``ifcb_n_triggers_value{dataset="<dataset_name>"}``: Latest n_triggers in Count
- ``ifcb_n_triggers_timestamp{dataset="<dataset_name>"}``: Timestamp of latest n_triggers value
- ``ifcb_n_images_value{dataset="<dataset_name>"}``: Latest n_images in Count
- ``ifcb_n_images_timestamp{dataset="<dataset_name>"}``: Timestamp of latest n_images value

Prometheus Integration
---------------------

Add the following to your Prometheus configuration to scrape metrics::

   scrape_configs:
     - job_name: 'ifcb'
       static_configs:
         - targets: ['localhost:8000']

Troubleshooting
---------------

- If you see ``ModuleNotFoundError``, make sure to update your environment with::

     conda env update -f environment.yml

- If metrics do not appear, check API connectivity and ensure the exporter is running.

Contributing
------------

Pull requests and issues are welcome! Please see CONTRIBUTING.rst for guidelines.

License
-------

This project is licensed under the terms described in LICENSE.

Building with Docker
--------------------


To build the Docker container::

   docker build -t ifcb-prometheus-exporter .

To run the exporter in Docker and expose metrics on port 8000::

   docker run -p 8000:8000 ifcb-prometheus-exporter

You can pass arguments to the exporter as needed, for example::

   docker run -p 9000:9000 ifcb-prometheus-exporter python ifcb_prometheus_exporter/ifcb_prometheus_exporter.py --base-url https://ifcb.caloos.org/api --port 9000

Credits
-------

This package was created with Cookiecutter_ and the ``audreyr/cookiecutter-pypackage``_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _``audreyr/cookiecutter-pypackage``: https://github.com/audreyr/cookiecutter-pypackage
