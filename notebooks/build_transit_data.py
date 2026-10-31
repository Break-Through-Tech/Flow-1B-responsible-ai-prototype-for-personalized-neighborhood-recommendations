"""Build a ZIP-level Miami-Dade transit feature table from GTFS files."""

from datetime import date
import io
from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
# The allowlist defines the project's Miami-Dade geography. GTFS itself has
# no ZIP field, so this file is applied after stops are spatially mapped.
ALLOWED_ZIPS_PATH = PROJECT_ROOT / "data" / "raw" / "miami_dade_zctas.txt"
ZCTA_BOUNDARIES_DIR = SCRIPT_DIR / "zcta_boundaries"
OUTPUT_PATH = SCRIPT_DIR / "miami_transit.csv"

# These are the only GTFS tables needed for the requested final columns.
# stop_times is the event table; the other tables provide its relationships
# and attributes.
GTFS_FILES = {
    "stops": "stops.txt",
    "routes": "routes.txt",
    "trips": "trips.txt",
    "stop_times": "stop_times.txt",
    "calendar": "calendar.txt",
}
AGENCY_NAME = "Miami-Dade Transit"


def load_allowed_zips() -> set[str]:
    """Load the project geography and keep ZIP codes as five-character strings."""
    allowed = {
        line.strip()
        for line in ALLOWED_ZIPS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if not allowed:
        raise ValueError(f"No ZIP codes found in {ALLOWED_ZIPS_PATH}.")
    return allowed


def load_gtfs() -> dict[str, pd.DataFrame]:
    """Read the GTFS text tables used by the final feature calculations."""
    return {
        name: pd.read_csv(SCRIPT_DIR / filename)
        for name, filename in GTFS_FILES.items()
    }


def load_zcta_boundaries() -> gpd.GeoDataFrame:
    """Download and load Census ZCTA polygons used to enrich stops with ZIPs."""
    url = (
        "https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/"
        "tl_2024_us_zcta520.zip"
    )
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    ZCTA_BOUNDARIES_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(ZCTA_BOUNDARIES_DIR)
    return gpd.read_file(
        ZCTA_BOUNDARIES_DIR / "tl_2024_us_zcta520.shp"
    )


def assign_zips(stops: pd.DataFrame, zcta: gpd.GeoDataFrame) -> pd.DataFrame:
    """Spatially map stop coordinates to ZCTAs and retain project ZIPs only."""
    # A GTFS stop has latitude/longitude but no ZIP. Converting coordinates
    # to points and joining them to ZCTA polygons creates the missing
    # stop_id -> zip_code relationship used by every ZIP-level feature.
    stops_geo = gpd.GeoDataFrame(
        stops.copy(),
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs="EPSG:4326",
    )
    zcta = zcta.to_crs(stops_geo.crs)
    enriched = gpd.sjoin(
        stops_geo,
        zcta[["ZCTA5CE20", "geometry"]],
        how="left",
        predicate="within",
    ).rename(columns={"ZCTA5CE20": "zip_code"})
    enriched["zip_code"] = enriched["zip_code"].astype("string").str.zfill(5)
    return pd.DataFrame(enriched.drop(columns="geometry"))


def add_mode_labels(routes: pd.DataFrame) -> pd.DataFrame:
    """Map GTFS route_type codes to readable Miami transit mode labels."""
    # Numeric GTFS codes are useful for computation but not for explanations.
    # These mappings match the modes represented in the Miami-Dade feed.
    result = routes.copy()
    result["transit_type"] = result["route_type"].map(
        {0: "metromover", 2: "metrorail", 3: "bus"}
    ).fillna("other")
    return result


def active_weekday_service_ids(calendar: pd.DataFrame) -> set:
    """Return service IDs scheduled on at least one Monday-Friday."""
    # A trip points to service_id, not directly to a weekday. This lookup
    # converts calendar flags into the service IDs used by stop_times.
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    active = calendar[calendar[weekdays].eq(1).any(axis=1)]
    return set(active["service_id"])


def departure_count(
    stop_events: pd.DataFrame,
    category: str,
) -> pd.Series:
    """Count distinct scheduled departure events for one calendar category."""
    events = stop_events[stop_events[category]].drop_duplicates(
        ["zip_code", "stop_id", "trip_id", "departure_time"]
    )
    return events.groupby("zip_code").size()


def gtfs_time_to_minutes(value: object) -> float:
    """Convert GTFS HH:MM:SS to minutes, preserving hours above 24."""
    if pd.isna(value):
        return float("nan")
    parts = str(value).split(":")
    if len(parts) != 3:
        return float("nan")
    try:
        hours, minutes, seconds = (float(part) for part in parts)
    except ValueError:
        return float("nan")
    return hours * 60 + minutes + seconds / 60


def median_headway(stop_events: pd.DataFrame, category: str) -> pd.Series:
    """Calculate the median stop-route headway for each ZIP.

    Headways are calculated within each ZIP, stop, and route so departures
    from unrelated stops or routes are never compared. Pair-level medians are
    then aggregated to the ZIP median.
    """
    events = stop_events[stop_events[category]].copy()
    events["departure_minutes"] = events["departure_time"].map(gtfs_time_to_minutes)
    events = events.dropna(subset=["departure_minutes"]).drop_duplicates(
        ["zip_code", "stop_id", "route_id", "trip_id", "departure_time"]
    )
    events = events.sort_values(
        ["zip_code", "stop_id", "route_id", "departure_minutes"]
    )
    events["headway_minutes"] = events.groupby(
        ["zip_code", "stop_id", "route_id"]
    )["departure_minutes"].diff()
    valid = events[events["headway_minutes"] > 0]
    pair_medians = valid.groupby(
        ["zip_code", "stop_id", "route_id"]
    )["headway_minutes"].median()
    return pair_medians.groupby("zip_code").median()


def known_share(frame: pd.DataFrame, value_column: str, positive: int) -> pd.Series:
    """Calculate a share using only explicit GTFS yes/no values.

    GTFS value 0 means unknown for these fields, so unknown records are
    excluded from the denominator rather than treated as negative evidence.
    """
    known = frame[frame[value_column].isin([1, 2])]
    if known.empty:
        return pd.Series(dtype="float64")
    return known.assign(
        is_positive=known[value_column].eq(positive)
    ).groupby("zip_code")["is_positive"].mean()


def main() -> None:
    # Load source tables and establish the geographic boundary before joining
    # schedules. This keeps out-of-scope stops from entering any final count.
    allowed_zips = load_allowed_zips()
    gtfs = load_gtfs()
    zcta = load_zcta_boundaries()

    stops = assign_zips(gtfs["stops"], zcta)
    in_scope = stops["zip_code"].isin(allowed_zips)
    print(f"Removed stops outside project ZIP scope: {(~in_scope).sum():,}")
    # Keep only fields needed for stop-level accessibility and ZIP aggregation.
    # Coordinates and display names are intentionally not part of the final
    # ZIP-level dataset.
    stops = stops.loc[in_scope, ["stop_id", "zip_code", "wheelchair_boarding"]]

    # Select only columns needed from each relational GTFS table. The joins
    # below turn separate text files into one analysis-ready event table.
    routes = add_mode_labels(gtfs["routes"])
    trips = gtfs["trips"][
        [
            "trip_id",
            "route_id",
            "service_id",
            "wheelchair_accessible",
            "bikes_allowed",
        ]
    ]
    stop_times = gtfs["stop_times"][
        ["trip_id", "stop_id", "departure_time"]
    ]

    # Calendar flags are attached to trips through service_id. A trip can
    # belong to more than one category when the feed has overlapping service
    # records, so each category is retained as a boolean flag.
    calendar = gtfs["calendar"].copy()
    calendar["weekday_service"] = calendar[
        ["monday", "tuesday", "wednesday", "thursday", "friday"]
    ].eq(1).any(axis=1)
    calendar["saturday_service"] = calendar["saturday"].eq(1)
    calendar["sunday_service"] = calendar["sunday"].eq(1)

    # This merge converts separate GTFS tables into one event-level table:
    # stop_times identifies where/when a trip stops; trips identifies its
    # route, service calendar, accessibility, and bike attributes; routes
    # identifies the transit mode. ZIP comes from the spatial stop join.
    events = (
        stop_times.merge(trips, on="trip_id", how="inner")
        .merge(routes[["route_id", "route_type", "transit_type"]], on="route_id", how="inner")
        .merge(stops, on="stop_id", how="inner")
        .merge(
            calendar[
                [
                    "service_id",
                    "weekday_service",
                    "saturday_service",
                    "sunday_service",
                ]
            ],
            on="service_id",
            how="left",
        )
    )
    for category in ("weekday_service", "saturday_service", "sunday_service"):
        events[category] = events[category].fillna(False).astype(bool)

    # Every final row is one ZIP. Distinct IDs prevent repeated stop_times
    # records from inflating physical-stop and route counts:
    # - transit_stop_count: distinct stop_id values in the ZIP.
    # - unique_route_count: distinct route_id values serving the ZIP.
    # - transit_types: readable route_type labels joined with "|".
    # - *_route_count: distinct routes per GTFS route_type (3 bus, 2 rail,
    #   and 0 Metromover for this Miami-Dade feed).
    result = stops.groupby("zip_code").agg(
        transit_stop_count=("stop_id", "nunique")
    ).reset_index()
    # Count distinct IDs instead of rows: stop_times repeats a stop for every
    # trip, while the feature should count each physical stop only once.
    route_counts = events.groupby("zip_code").agg(
        unique_route_count=("route_id", "nunique")
    ).reset_index()
    mode_route_counts = (
        events[["zip_code", "route_id", "route_type"]]
        .drop_duplicates()
        .assign(
            bus_route=lambda frame: frame["route_type"].eq(3),
            metrorail_route=lambda frame: frame["route_type"].eq(2),
            metromover_route=lambda frame: frame["route_type"].eq(0),
        )
        .groupby("zip_code")
        .agg(
            bus_route_count=("bus_route", "sum"),
            metrorail_route_count=("metrorail_route", "sum"),
            metromover_route_count=("metromover_route", "sum"),
        )
        .reset_index()
    )
    route_counts = route_counts.merge(mode_route_counts, on="zip_code", how="left")
    result = result.merge(route_counts, on="zip_code", how="left")

    # Store readable modes as a stable, sorted pipe-separated value. This
    # produces values such as "bus|metrorail" for user-facing explanations.
    modes = events.groupby("zip_code")["transit_type"].agg(
        lambda values: "|".join(sorted(set(values)))
    ).rename("transit_types")
    result = result.merge(modes, on="zip_code", how="left")

    # Count distinct scheduled stop departures for each service category.
    # These are regular calendar counts; calendar_dates exceptions are not
    # applied because the output represents a reusable schedule snapshot.
    weekday = departure_count(events, "weekday_service").rename("weekday_departures")
    saturday = departure_count(events, "saturday_service").rename("saturday_departures")
    sunday = departure_count(events, "sunday_service").rename("sunday_departures")
    result = result.merge(weekday, on="zip_code", how="left")
    result = result.merge(saturday, on="zip_code", how="left")
    result = result.merge(sunday, on="zip_code", how="left")

    # Headway is the time between consecutive departures on the same
    # stop-route pair. GTFS times above 24:00 are preserved as next-day
    # service, then pair-level medians are aggregated to each ZIP.
    weekday_headway = median_headway(
        events, "weekday_service"
    ).rename("weekday_median_headway_minutes")
    weekend_events = events.assign(
        weekend_service=events["saturday_service"] | events["sunday_service"]
    )
    weekend_headway = median_headway(
        weekend_events, "weekend_service"
    ).rename("weekend_median_headway_minutes")
    result = result.merge(weekday_headway, on="zip_code", how="left")
    result = result.merge(weekend_headway, on="zip_code", how="left")

    # Peak counts remain useful commuter context: morning is 07:00-09:00 and
    # evening is 16:00-19:00, restricted to weekday-service events.
    peak_events = events.copy()
    peak_hours = pd.to_numeric(
        peak_events["departure_time"].astype("string").str.split(":").str[0],
        errors="coerce",
    )
    peak_events = peak_events[
        peak_events["weekday_service"] & peak_hours.notna()
    ]
    morning = departure_count(
        peak_events[peak_hours.loc[peak_events.index].between(7, 9, inclusive="left")],
        "weekday_service",
    ).rename("morning_peak_departures")
    evening = departure_count(
        peak_events[peak_hours.loc[peak_events.index].between(16, 19, inclusive="left")],
        "weekday_service",
    ).rename("evening_peak_departures")
    result = result.merge(morning, on="zip_code", how="left")
    result = result.merge(evening, on="zip_code", how="left")

    # Accessibility and bike shares use only explicit GTFS yes/no values.
    # Unknown values are excluded rather than incorrectly treated as "no".
    # The resulting values are proportions between 0 and 1, calculated at ZIP
    # level after the stop/trip relationships have been established.
    stop_access = known_share(
        stops.rename(columns={"wheelchair_boarding": "accessibility"}),
        "accessibility",
        1,
    ).rename("accessible_stop_share")
    result = result.merge(stop_access, on="zip_code", how="left")

    trip_access = known_share(events, "wheelchair_accessible", 1).rename(
        "wheelchair_accessible_trip_share"
    )
    bike_access = known_share(events, "bikes_allowed", 1).rename(
        "bike_allowed_trip_share"
    )
    result = result.merge(trip_access, on="zip_code", how="left")
    result = result.merge(bike_access, on="zip_code", how="left")

    # These metadata fields describe the schedule snapshot, not neighborhood
    # measurements. They are repeated per ZIP so each output row is
    # self-describing and its schedule validity can be evaluated later.
    # agency.txt is not present in the current raw snapshot. The feed
    # provenance is already established as Miami-Dade Transit, so retain that
    # explicit source label until agency.txt is restored.
    result["gtfs_agency"] = AGENCY_NAME
    result["service_start_date"] = gtfs["calendar"]["start_date"].min()
    result["service_end_date"] = gtfs["calendar"]["end_date"].max()
    result["data_as_of"] = date.today().isoformat()

    # Select and order the public contract. Intermediate stop_id, trip_id,
    # route_id, and raw schedule columns are not exposed in the final table.
    final_columns = [
        "zip_code",
        "transit_stop_count",
        "unique_route_count",
        "transit_types",
        "bus_route_count",
        "metrorail_route_count",
        "metromover_route_count",
        "weekday_departures",
        "saturday_departures",
        "sunday_departures",
        "weekday_median_headway_minutes",
        "weekend_median_headway_minutes",
        "morning_peak_departures",
        "evening_peak_departures",
        "accessible_stop_share",
        "wheelchair_accessible_trip_share",
        "bike_allowed_trip_share",
        "gtfs_agency",
        "service_start_date",
        "service_end_date",
        "data_as_of",
    ]
    result = result[final_columns].sort_values("zip_code")
    # Fail closed: never write a final dataset containing a ZIP outside the
    # project's Miami-Dade allowlist.
    invalid_zips = set(result["zip_code"]) - allowed_zips
    if invalid_zips:
        raise ValueError(f"Output contains ZIPs outside project scope: {sorted(invalid_zips)}")
    result.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(result):,} ZIP rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
