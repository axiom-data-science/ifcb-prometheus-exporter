#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Console script for ifcb-prometheus-exporter."""

import argparse
import sys


def main():
    """Console script for ifcb-prometheus-exporter."""
    parser = argparse.ArgumentParser(description="IFCB Prometheus Exporter CLI")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL for the IFCB API (e.g., https://ifcb.caloos.org/api)",
    )
    args = parser.parse_args()

    print(f"Base URL: {args.base_url}")
    print(
        "Replace this message by putting your code into ifcb_prometheus_exporter.cli.main"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
