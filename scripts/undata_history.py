"""Read annual counts and source qualifiers from UN Demographic Yearbook Table 13."""

from pathlib import Path
import re
from xml.etree import ElementTree

SPREADSHEET = "{urn:schemas-microsoft-com:office:spreadsheet}"
BIFF_HEADER = bytes.fromhex("d0cf11e0a1b11ae1")
CONTINENTS = {
    "AFRICA": "Africa",
    "AMERICA, NORTH": "North America",
    "AMERICA, SOUTH": "South America",
    "ASIA": "Asia",
    "EUROPE": "Europe",
    "OCEANIA": "Oceania",
}
MISSING_VALUES = {"", "...", "…", "–", "—", "-", ".."}
BILINGUAL_SEPARATOR = re.compile(r"\s+[-–—]\s*")


def split_text(value):
    """Return the English label or note from a bilingual field."""
    return BILINGUAL_SEPARATOR.split(value.strip(), maxsplit=1)[0].strip()


def read_xml(path):
    workbook = ElementTree.parse(path)
    spreadsheet = SPREADSHEET
    italic_styles = set()
    for style in workbook.iter(spreadsheet + "Style"):
        font = style.find(spreadsheet + "Font")
        if font is not None and font.get(spreadsheet + "Italic") == "1":
            italic_styles.add(style.get(spreadsheet + "ID"))
    sheets = []
    for sheet in workbook.iter(spreadsheet + "Worksheet"):
        rows = []
        for row in sheet.iter(spreadsheet + "Row"):
            cells = {}
            index = 0
            for cell in row.findall(spreadsheet + "Cell"):
                column = cell.get(spreadsheet + "Index")
                if column:
                    index = int(column) - 1
                value = cell.find(spreadsheet + "Data")
                if value is not None:
                    cells[index] = (
                        "".join(value.itertext()).strip(),
                        cell.get(spreadsheet + "StyleID") in italic_styles,
                    )
                index += 1 + int(cell.get(spreadsheet + "MergeAcross", "0"))
            rows.append(cells)
        sheets.append(rows)
    return sheets


def read_biff(path):
    import xlrd

    workbook = xlrd.open_workbook(path, formatting_info=True)
    sheets = []
    for sheet in workbook.sheets():
        rows = []
        for row in sheet.get_rows():
            cells = {}
            for column, cell in enumerate(row):
                value = cell.value
                if value == "":
                    continue
                if cell.ctype == xlrd.XL_CELL_NUMBER and value.is_integer():
                    value = int(value)
                font = workbook.font_list[workbook.xf_list[cell.xf_index].font_index]
                cells[column] = (str(value).strip(), bool(font.italic))
            rows.append(cells)
        sheets.append(rows)
    return sheets


def read_count(value):
    compact = re.sub(r"[\s,]", "", value)
    if re.fullmatch(r"[0-9]+", compact):
        return int(compact)
    if compact in MISSING_VALUES:
        return None
    raise ValueError(f"Unexpected UN Yearbook count marker: {value!r}")


def read_notes(rows):
    footnotes = {}
    for row in rows:
        text, _ = row.get(0, ("", False))
        match = re.fullmatch(r"([0-9]+|[a-f])\s+(.+)", text, re.DOTALL)
        if match:
            number, note = match.groups()
            footnotes[number] = " ".join(split_text(note).split())
    return footnotes


def read_undata(path):
    """Return published non-missing observations, preserving per-row qualifications."""
    path = Path(path)
    with path.open("rb") as source:
        header = source.read(len(BIFF_HEADER))
    sheets = read_biff(path) if header == BIFF_HEADER else read_xml(path)
    positions = {}
    rows = sheets[0]
    for index, row in enumerate(rows):
        if row.get(0, ("", False))[0]:
            continue
        years = {
            column: int(value)
            for column, (value, _) in row.items()
            if re.fullmatch(r"(?:19|20)[0-9]{2}", value)
        }
        if len(years) >= 8 and list(years.values()) == list(range(min(years.values()), max(years.values()) + 1)):
            positions = years
            data_rows = rows[index + 1:]
            break
    if not positions:
        raise ValueError(f"No year columns in {path}")
    has_note_columns = all(b - a == 2 for a, b in zip(positions, list(positions)[1:]))
    footnotes = read_notes(sheets[1] if len(sheets) > 1 else rows)
    continent = None
    pending_label = None
    observations = []
    for row in data_rows:
        label, _ = row.get(0, ("", False))
        if not label:
            continue
        if label.startswith(("GENERAL NOTES", "FOOTNOTES")):
            break
        english = split_text(label)
        if english in CONTINENTS:
            continent = CONTINENTS[english]
            continue
        if not continent:
            continue
        if not any(row.get(column, ("", False))[0] for column in positions):
            pending_label = label
            continue
        if pending_label:
            label = f"{pending_label} {label}"
            pending_label = None

        label = label.rstrip(".").strip()
        groups = re.findall(r"\(([0-9]+|[a-f])\)", label)
        label = re.sub(r"\(([0-9]+|[a-f])\)", "", label).strip()
        trailing = re.search(r"([0-9]+)$", label)
        if trailing:
            groups.append(trailing.group(1))
            label = label[:trailing.start()].rstrip()
        name = split_text(label)
        for column, year in positions.items():
            value, italic = row.get(column, ("", False))
            # The 2006 companion PDF displays this fractional workbook value as 22,103.
            corrected_count = (path.stem, name, year, value) == (
                "un-dyb-abortions-2006", "Albania", 1997, "22102.562",
            )
            count = 22103 if corrected_count else read_count(value.rstrip("*").strip())
            if count is None:
                continue
            marker = row.get(column + 1, ("", False))[0] if has_note_columns else ""
            numbers = groups + re.findall(r"[0-9]+", marker)
            notes = [footnotes.get(number, f"Source footnote {number}") for number in dict.fromkeys(numbers)]
            if corrected_count:
                notes.append("The workbook stores 22,102.562. The published Table 13 PDF displays 22,103.")
            provisional = "*" in value or "*" in marker or any("provisional" in note.lower() for note in notes)
            status = "qualified" if notes else "reported"
            if provisional:
                status = "provisional"
                notes.append("The source marks this figure as provisional.")
            if italic:
                status = "less_reliable"
                notes.append("The source marks this figure as less reliable.")
            if any(re.search(
                r"(?<!not )(?:include|includes|including|refer to) [^.]*?(?:spontaneous abortions|miscarriages)|"
                r"foetal deaths of less than|fetal deaths of less than|applications to commissions|"
                r"abortion is not legally induced in the country|"
                r"data refer to both [0-9]{4}\s+and\s+[0-9]{4}",
                note, re.IGNORECASE,
            ) for note in notes):
                status = "different_measure"
            observations.append({
                "name": name,
                "continent": continent,
                "year": year,
                "count": count,
                "status": status,
                "notes": notes,
                "source_id": path.stem,
            })
    if not observations:
        raise ValueError(f"No observations in {path}")
    return observations
