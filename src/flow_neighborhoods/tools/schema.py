"""schema tool: what columns the data files have, with a plain-English note for each."""

import csv
from pathlib import Path
from typing import Literal, TypedDict

from ..data import DataError
from ..engine import Recommender


class Column(TypedDict):
    name: str
    note: str


class DataFile(TypedDict):
    file: str
    data_type: Literal["real", "derived", "placeholder", "synthetic"]
    description: str
    row_count: int
    columns: list[Column]


class Schema(TypedDict):
    status: Literal["ok"]
    files: list[DataFile]
    notes: list[str]
    warnings: list[str]
    guidance: str


NO_NOTE = "No description written yet. Do not guess what this column means."

GUIDANCE = (
    "Describe only the files and columns listed here. Report each file's data_type "
    "(real, derived, placeholder or synthetic) when it matters, and say so if a column "
    "has no note. Do not invent columns or meanings. For a specific ZIP's values, use "
    "area_stats, not this tool."
)

NOTES = [
    "Only the six files listed here are described; other files in the data folder are not.",
    (
        "Cleaned files are filled in and capped to reduce outliers; the original files are "
        "kept alongside them."
    ),
    (
        "Lifestyle scores in the area_features files run from 0 to 1; they are scores, not "
        "measurements."
    ),
]

# file -> (data_type, description, {column: note}). Notes follow data_dictionary.md.
DATASETS: dict[str, tuple[str, str, dict[str, str]]] = {
    "area_features_cleaned.csv": (
        "placeholder",
        (
            "One row per ZIP with the lifestyle scores the recommender ranks on. The scores are "
            "starter placeholders, not measured values."
        ),
        {
            "zip": "Five-digit ZIP code.",
            "transit": "Lifestyle score for transit access (placeholder, derived from rent).",
            "social": "Lifestyle score for social scene (placeholder, derived from population).",
            "quiet": "Lifestyle score for quietness (placeholder, derived from population).",
            "pet_friendly": "Lifestyle score for pet friendliness (placeholder, same everywhere).",
            "walkable": "Lifestyle score for walkability (placeholder).",
            "migration_score": "In-migration activity proxy, 0 to 1 (derived).",
            "median_rent_usd": "Median monthly rent in US dollars. Missing means unknown.",
            "co_living_friendly": "Lifestyle score for co-living / roommate friendliness.",
            "single_family_friendly": "Single-family housing score. Not used by the recommender.",
        },
    ),
    "area_features.csv": (
        "placeholder",
        (
            "Original, uncleaned version of area_features_cleaned.csv. This is the file that "
            "holds area_name."
        ),
        {
            "zip": "Five-digit ZIP code.",
            "area_name": "Neighborhood name for the ZIP (some are placeholders like 'ZCTA5 33101').",
            "rent_band": "Rent range the ZIP falls in.",
            "transit": "Lifestyle score for transit access (placeholder).",
            "social": "Lifestyle score for social scene (placeholder).",
            "quiet": "Lifestyle score for quietness (placeholder).",
            "pet_friendly": "Lifestyle score for pet friendliness (placeholder).",
            "walkable": "Lifestyle score for walkability (placeholder).",
            "migration_score": "In-migration activity proxy, 0 to 1 (derived).",
            "median_rent_usd": "Median monthly rent in US dollars. -666666666 means missing.",
            "co_living_friendly": "Lifestyle score for co-living / roommate friendliness.",
            "single_family_friendly": "Single-family housing score. Not used by the recommender.",
        },
    ),
    "public_features_cleaned.csv": (
        "real",
        (
            "Public Census (ACS) and Zillow-style statistics per ZIP, cleaned. Columns starting "
            "with 'winsorized_' were capped to limit outliers."
        ),
        {
            "zip": "Five-digit ZIP code.",
            "B01003_001E": "Census: total population.",
            "B07003_001E": "Census: population aged 1 year and over.",
            "B07003_004E": "Census: people who lived in the same house one year ago.",
            "B07003_008E": "Census: people who moved within the same county.",
            "B07003_010E": "Census: people who moved from a different county.",
            "B11016_001E": "Census: total households.",
            "B25003_002E": "Census: owner-occupied housing units.",
            "B25003_003E": "Census: renter-occupied housing units.",
            "B25064_001E": "Census: median gross rent in dollars.",
            "B25077_001E": "Census: median home value in dollars.",
            "median_rent_usd": "Median monthly rent in US dollars (Census or derived).",
            "population": "Total population of the ZIP.",
            "winsorized_zillow_home_value_index": "Zillow-style home value index, capped.",
            "winsorized_zillow_rent_index": "Zillow-style rent index, capped.",
            "winsorized_moved_different_house_pct": "Share who moved to a different house, capped.",
            "winsorized_B25077_001E": "Median home value in dollars, capped.",
            "winsorized_B25064_001E": "Median gross rent in dollars, capped.",
            "winsorized_B07003_008E": "People who moved within the same county, capped.",
        },
    ),
    "area_options_cleaned.csv": (
        "synthetic",
        "NOT REAL LISTINGS. Made-up housing options used for demos and testing.",
        {
            "zip": "Five-digit ZIP code.",
            "migration_score": "In-migration proxy, 0 to 1, read from a made-up summary; 0 may mean missing.",
            "median_rent": "Median monthly rent in US dollars, read from a made-up summary; 0 may mean missing.",
        },
    ),
    "crowd_text_snippets_cleaned.csv": (
        "synthetic",
        "Demo review snippets turned into one 0/1 column per theme. Not authentic reviews.",
        {"zip": "Five-digit ZIP code."},
    ),
    "crowd_text_snippets.csv": (
        "synthetic",
        "Demo review snippets, one per row. Not authentic reviews; use crowd_themes to read them.",
        {
            "snippet_id": "Unique ID for the snippet; cite it when quoting.",
            "zip": "Five-digit ZIP code the snippet is about.",
            "source": "Where the snippet is labeled as coming from.",
            "theme": "Topic label for the snippet (a topic, not a sentiment).",
            "text": "The snippet text.",
        },
    ),
}

# Columns that come in families: any column starting with the prefix gets this note.
PREFIX_NOTES = {
    "rent_band_": "1 if the ZIP's rent falls in this band, else 0 (one column per band).",
    "housing_preference_": "1 if this housing preference applies, else 0 (synthetic).",
    "household_": "1 if this household type applies, else 0 (synthetic).",
    "tag_": "1 if this lifestyle tag applies, else 0 (synthetic).",
    "theme_": "1 if any snippet for the ZIP has this theme, else 0 (demo text).",
}


def _note_for(file: str, column: str) -> str | None:
    notes = DATASETS[file][2]
    if column in notes:
        return notes[column]
    for prefix, note in PREFIX_NOTES.items():
        if column.startswith(prefix):
            return note
    return None


def _read_header_and_rows(path: Path) -> tuple[list[str], int]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if not header:
                raise DataError(f"{path.name} is empty or has no header row")
            return header, sum(1 for _ in reader)
    except UnicodeDecodeError as exc:
        raise DataError(f"{path.name} is not valid UTF-8 text") from exc


def schema(engine: Recommender, data_dir: Path) -> Schema:
    """Columns and notes for the described data files. Takes no arguments from the agent.

    A missing or unreadable file raises DataError (shown to the agent as a tool error).
    A column with no written note is kept, given a "do not guess" note, and listed in
    warnings so the gap is visible rather than silently skipped.
    """
    files: list[DataFile] = []
    warnings: list[str] = []
    for name, (data_type, description, _) in DATASETS.items():
        path = Path(data_dir) / name
        if not path.is_file():
            raise DataError(f"{name} is missing from the data folder")
        header, row_count = _read_header_and_rows(path)
        columns: list[Column] = []
        for column in header:
            note = _note_for(name, column)
            if note is None:
                warnings.append(f"{name}: column '{column}' has no description yet")
                note = NO_NOTE
            columns.append({"name": column, "note": note})
        files.append(
            {
                "file": name,
                "data_type": data_type,  # type: ignore[typeddict-item]
                "description": description,
                "row_count": row_count,
                "columns": columns,
            }
        )
    return {
        "status": "ok",
        "files": files,
        "notes": NOTES,
        "warnings": warnings,
        "guidance": GUIDANCE,
    }
