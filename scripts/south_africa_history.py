"""Read national public-sector terminations from archived South African Health Reviews."""

import re
import subprocess


COUNT = r"([0-9]{1,3}(?: [0-9]{3})+)(?= {2,})"
REPORTS = {
    "za-dhis-terminations-2022": (
        63,
        ("2019/20", "2020/21", "2021/22"),
        r"^ *(?:ToPs \(Terminations of Pregnancy\) +)?{period} +DHIS +{count}",
    ),
    "za-dhis-terminations-2023": (
        34,
        ("2022/23",),
        r"^ *ToPs *\n +{start}/ *\n +\(Terminations +DHIS +{count}[^\n]*\n +{end} *\n",
    ),
    "za-dhis-terminations-2024": (
        26,
        ("2023/24",),
        r"^ +{start}/ *\n +ToPs \(terminations of pregnancy\) +DHIS +{count}[^\n]*\n +{end} *\n",
    ),
    "za-dhis-terminations-2025": (
        29,
        ("2024/25",),
        r"^ +ToPs \(Terminations of Pregnancy\) +{period} +{count}[^\n]*\n +DHIS",
    ),
}


def read_south_africa(archived):
    """Return reported national totals with April-to-March reporting periods."""
    rows = []
    for source, (page, periods, pattern) in REPORTS.items():
        path = archived(source)
        table = subprocess.run(
            ["pdftotext", "-f", str(page), "-l", str(page), "-layout", str(path), "-"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout
        for period in periods:
            start, end = period.split("/")
            counts = re.findall(
                pattern.format(period=period, start=start, end=end, count=COUNT),
                table, re.MULTILINE,
            )
            if len(counts) != 1:
                raise ValueError(f"Expected one national DHIS total for {period} in {path}")
            rows.append({
                "year": int(start) + 1,
                "count": int(counts[0].replace(" ", "")),
                "status": "reported",
                "notes": f"Financial year {period} (April–March). DHIS public-sector count.",
                "source": source,
            })
    return rows
