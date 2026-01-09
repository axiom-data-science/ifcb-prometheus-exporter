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

4. An Additional environment file is present for testing and development environments. The additional developer dependencies can be installed with::

      conda env update -f test-environment.yml

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

Prometheus Integration
---------------------

Add the following to your Prometheus configuration to scrape metrics::

   scrape_configs:
     - job_name: 'ifcb'
       static_configs:
         - targets: ['localhost:8000']

Troubleshooting
---------------

- If you see `ModuleNotFoundError`, make sure to update your environment with::

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

To build the docker container::

   docker build -t ifcb-prometheus-exporter .

Running with Docker
-------------------

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
