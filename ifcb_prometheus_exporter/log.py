# -*- coding: utf-8 -*-
"""Logging configuration."""
import logging
import logging.config

import importlib.resources


logger = logging.getLogger("ifcb-prometheus-exporter")


def setup_logging():
    """Initializes the project logging."""
    ref = importlib.resources.files("ifcb_prometheus_exporter") / "logging.conf"
    with importlib.resources.as_file(ref) as path:
        logging.config.fileConfig(path)

