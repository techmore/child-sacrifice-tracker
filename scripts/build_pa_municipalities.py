#!/usr/bin/env python3
"""Build the Pennsylvania municipal map from the Census cartographic shapefile."""
import json
from pathlib import Path

import shapefile


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "references/open/census-pa-county-subdivisions-2025.zip"
OUTPUT = ROOT / "docs/data/pa-municipalities.json"


def main():
    features = []
    with shapefile.Reader(str(SOURCE)) as reader:
        for record in reader.iterShapeRecords():
            fields = record.record
            geoid = fields["GEOID"]
            base_name, _, legal_type = fields["NAMELSAD"].rpartition(" ")
            features.append({
                "type": "Feature",
                "id": geoid,
                "properties": {"geoid": geoid, "name": f"{base_name} {legal_type.capitalize()}"},
                # Preserve the shapefile's clockwise exteriors for D3's spherical projection.
                "geometry": record.shape.__geo_interface__,
            })

    counties = {feature["id"][:5] for feature in features}
    if counties != {f"42{county:03d}" for county in range(1, 134, 2)}:
        raise ValueError("Municipal boundaries must cover all 67 Pennsylvania counties")

    data = {"type": "FeatureCollection", "features": sorted(features, key=lambda feature: feature["id"])}
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
