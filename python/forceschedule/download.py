#!/usr/bin/env python3
"""
Simple script to download Landsat Level 1C and Sentinel-2 L1C data using EODAG
"""

import sys

from eodag import EODataAccessGateway


class FORCEDownload(object):

    def __init__(self):
        pass


def download_satellite_data(
    product_type="S2_MSI_L1C",
    bbox=[2.2, 48.8, 2.5, 49.0],  # Default: Paris area
    start_date="2023-01-01",
    end_date="2023-12-31",
    max_results=5
):
    """Download satellite data using EODAG"""

    # Initialize EODAG
    dag = EODataAccessGateway()

    # Search for products
    results, _ = dag.search(
        productType=product_type,
        bbox=bbox,
        startTimeFromAscendingNode=start_date,
        completionTimeFromAscendingNode=end_date,
        geom={"bbox": bbox}
    )

    print(f"Found {len(results)} products")

    # Download results
    downloaded = []
    for i, product in enumerate(results[:max_results]):
        print(f"Downloading {i + 1}/{min(len(results), max_results)}: "
              f"{product.properties['title']}")
        try:
            result = dag.download(product, output_dir="./downloads")
            downloaded.append(result)
        except Exception as e:
            print(f"Error downloading {product.properties['id']}: {e}")

    return downloaded


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) < 2:
        print(
            "Usage: python download_satellite.py [sentinel|landsat] "
            "[bbox_min_lon bbox_min_lat bbox_max_lon bbox_max_lat]")
        print("Example: python download_satellite.py "
              "sentinel 2.2 48.8 2.5 49.0")
        sys.exit(1)

    data_type = sys.argv[1].lower()

    # Parse bounding box if provided
    bbox = [2.2, 48.8, 2.5, 49.0]  # Default Paris
    if len(sys.argv) == 6:
        bbox = [float(x) for x in sys.argv[2:6]]

    # Download based on type
    if data_type == "sentinel":
        print("Downloading Sentinel-2 L1C data...")
        download_satellite_data(
            product_type="S2_MSI_L1C",
            bbox=bbox
        )
    elif data_type == "landsat":
        print("Downloading Landsat Level 1C data...")
        download_satellite_data(
            product_type="LANDSAT_C2L1",
            bbox=bbox
        )
    else:
        print("Invalid data type. Use 'sentinel' or 'landsat'")
        sys.exit(1)
