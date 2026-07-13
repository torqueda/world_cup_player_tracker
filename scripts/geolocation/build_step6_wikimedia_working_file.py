#!/usr/bin/env python3
"""
Build a Step 6 Wikimedia/Wikidata matching and geocoding working file for
2026 World Cup player-club map data.

Version 0.2.1 changes from v0.2:
- Fixes candidate_search_df missing qid column when search results exist.
- Adds defensive handling if candidate rows lack qid.

Version 0.2 changes from v0.1:
- Keeps every input club in clubs_step6_working.csv, even if no candidates are found.
- Adds contact-aware Wikimedia User-Agent support.
- Adds serial request throttling, retries, exponential backoff, Retry-After handling,
  and maxlag support for Wikidata Action API calls.
- Writes API/search logs so failed searches are diagnosable.
- Deduplicates Wikidata candidate details before scoring ambiguity.
- Uses a two-stage approach:
    1. wbsearchentities search per club query variant.
    2. batched SPARQL detail lookup for candidate QIDs.
- Produces separate no-candidate and API-error review files.

Run:
  python build_step6_wikimedia_working_file_v2.py \
    --workbook world_cup_2026_player_map_master_manually_reviewed.xlsx \
    --outdir step6_working_outputs_v2 \
    --contact "your_email@example.com"

Notes:
- The script does not edit your master workbook.
- The script is intentionally conservative. It proposes candidates; it does not finalize geocoding.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

DEFAULT_CLIENT_NAME = "world-cup-2026-player-club-map-step6"
DEFAULT_CLIENT_VERSION = "0.2.1"

# Read-only script. Keep request rates modest.
DEFAULT_SEARCH_DELAY_SECONDS = 0.35
DEFAULT_SPARQL_DELAY_SECONDS = 1.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_MAXLAG = 5

FOOTBALL_HINT_WORDS = {
    "football",
    "soccer",
    "association football",
    "club",
    "team",
    "sports club",
}

BAD_ENTITY_HINTS = {
    "band",
    "album",
    "film",
    "song",
    "company",
    "human",
    "person",
    "given name",
    "surname",
    "settlement",
    "city",
    "town",
    "village",
    "commune",
    "district",
    "province",
    "municipality",
    "railway station",
    "airport",
    "school",
    "university",
}


@dataclass
class RequestLogRow:
    timestamp_utc: str
    service: str
    request_type: str
    query_or_batch: str
    status: str
    http_status: str
    attempt_count: int
    elapsed_seconds: float
    result_count: int
    error_message: str


class WikimediaClient:
    def __init__(
        self,
        contact: str,
        client_name: str = DEFAULT_CLIENT_NAME,
        client_version: str = DEFAULT_CLIENT_VERSION,
        search_delay_seconds: float = DEFAULT_SEARCH_DELAY_SECONDS,
        sparql_delay_seconds: float = DEFAULT_SPARQL_DELAY_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        maxlag: int = DEFAULT_MAXLAG,
        timeout_seconds: int = 60,
    ) -> None:
        self.contact = contact.strip() if contact else ""
        self.client_name = client_name
        self.client_version = client_version
        self.search_delay_seconds = search_delay_seconds
        self.sparql_delay_seconds = sparql_delay_seconds
        self.max_retries = max_retries
        self.maxlag = maxlag
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.request_log: List[RequestLogRow] = []

        contact_part = self.contact if self.contact else "local personal research; add --contact for contact info"
        self.user_agent = (
            f"{self.client_name}/{self.client_version} ({contact_part}) "
            f"python-requests/{requests.__version__}"
        )
        self.headers = {
            "User-Agent": self.user_agent,
            "Api-User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    @staticmethod
    def now_utc() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _sleep_with_jitter(self, base_seconds: float) -> None:
        time.sleep(base_seconds + random.uniform(0, 0.15))

    def _request_json(
        self,
        service: str,
        request_type: str,
        url: str,
        params: Dict[str, Any],
        headers_extra: Optional[Dict[str, str]] = None,
        delay_after_success: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        headers = dict(self.headers)
        if headers_extra:
            headers.update(headers_extra)

        query_or_batch = str(params.get("search") or params.get("query") or params.get("ids") or "")[:500]
        start = time.time()
        last_error = ""
        last_status = ""
        attempt = 0

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
                last_status = str(response.status_code)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
                    last_error = f"HTTP 429 Too Many Requests; sleeping {wait}s"
                    time.sleep(wait)
                    continue

                if response.status_code in {500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After")
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
                    last_error = f"HTTP {response.status_code}; sleeping {wait}s"
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict) and data.get("error"):
                    error = data.get("error", {})
                    code = str(error.get("code", ""))
                    info = str(error.get("info", error))
                    if code == "maxlag":
                        wait = min(60, 5 * attempt)
                        last_error = f"maxlag response: {info}; sleeping {wait}s"
                        time.sleep(wait)
                        continue
                    last_error = f"API error {code}: {info}"
                    break

                elapsed = time.time() - start
                result_count = self._result_count(data, request_type)
                self.request_log.append(RequestLogRow(
                    timestamp_utc=self.now_utc(),
                    service=service,
                    request_type=request_type,
                    query_or_batch=query_or_batch,
                    status="ok",
                    http_status=last_status,
                    attempt_count=attempt,
                    elapsed_seconds=round(elapsed, 3),
                    result_count=result_count,
                    error_message="",
                ))
                if delay_after_success:
                    self._sleep_with_jitter(delay_after_success)
                return data

            except Exception as exc:
                last_error = repr(exc)
                wait = min(60, 2 ** attempt)
                time.sleep(wait)

        elapsed = time.time() - start
        self.request_log.append(RequestLogRow(
            timestamp_utc=self.now_utc(),
            service=service,
            request_type=request_type,
            query_or_batch=query_or_batch,
            status="failed",
            http_status=last_status,
            attempt_count=attempt,
            elapsed_seconds=round(elapsed, 3),
            result_count=0,
            error_message=last_error,
        ))
        return None

    @staticmethod
    def _result_count(data: Dict[str, Any], request_type: str) -> int:
        if request_type == "wbsearchentities":
            return len(data.get("search", [])) if isinstance(data, dict) else 0
        if request_type == "sparql":
            try:
                return len(data["results"]["bindings"])
            except Exception:
                return 0
        return 0

    def search_entities(self, query: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": limit,
            "search": query,
            "maxlag": self.maxlag,
        }
        data = self._request_json(
            service="wikidata_action_api",
            request_type="wbsearchentities",
            url=WIKIDATA_API,
            params=params,
            delay_after_success=self.search_delay_seconds,
        )
        if data is None:
            return None
        return data.get("search", [])

    def sparql(self, query: str) -> Optional[Dict[str, Any]]:
        params = {
            "query": query,
            "format": "json",
        }
        return self._request_json(
            service="wikidata_query_service",
            request_type="sparql",
            url=SPARQL_ENDPOINT,
            params=params,
            headers_extra={"Accept": "application/sparql-results+json"},
            delay_after_success=self.sparql_delay_seconds,
        )

    def write_request_log(self, path: Path) -> None:
        rows = [row.__dict__ for row in self.request_log]
        pd.DataFrame(rows).to_csv(path, index=False)


def normalize_name(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    value = str(value).strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\b(f\.?c\.?|a\.?f\.?c\.?|s\.?k\.?|c\.?f\.?|s\.?c\.?|a\.?c\.?|f\.?k\.?)\b", " ", value)
    value = re.sub(r"\b(football club|soccer club|club de football|club|calcio|deportivo|sporting club)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def ascii_fold(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    value = unicodedata.normalize("NFKD", str(value))
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def build_query_variants(club_name: Any, club_name_ascii: Any, max_variants: int = 8) -> List[str]:
    raw_names = []
    for value in [club_name, club_name_ascii, ascii_fold(club_name), ascii_fold(club_name_ascii)]:
        if value is not None and not pd.isna(value):
            text = str(value).strip()
            if text:
                raw_names.append(text)

    variants: List[str] = []
    seen = set()

    def add(text: str) -> None:
        text = re.sub(r"\s+", " ", text).strip(" -,.\t\n\r")
        key = text.lower()
        if text and key not in seen:
            variants.append(text)
            seen.add(key)

    for name in raw_names:
        add(name)
        add(f"{name} football club")
        add(f"{name} soccer club")
        stripped = re.sub(r"\b(F\.?C\.?|A\.?F\.?C\.?|S\.?K\.?|C\.?F\.?|S\.?C\.?|A\.?C\.?|F\.?K\.?)\b", "", name, flags=re.I)
        stripped = re.sub(r"\b(Club|Football Club|Soccer Club|Sporting Club)\b", "", stripped, flags=re.I)
        stripped = re.sub(r"\s+", " ", stripped).strip(" -,.\t\n\r")
        if stripped and stripped.lower() != name.lower():
            add(stripped)
            add(f"{stripped} football club")

    # Put exact names first, then suffix-expanded forms. Keep a modest number to reduce API load.
    return variants[:max_variants]


def parse_wkt_point(value: Any) -> Tuple[Optional[float], Optional[float]]:
    if not value or pd.isna(value):
        return None, None
    match = re.search(r"Point\(([-0-9.]+)\s+([-0-9.]+)\)", str(value))
    if not match:
        return None, None
    lon = float(match.group(1))
    lat = float(match.group(2))
    return lat, lon


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def search_all_clubs(
    clubs_df: pd.DataFrame,
    client: WikimediaClient,
    search_limit: int,
    max_query_variants: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    candidate_meta: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    search_rows: List[Dict[str, Any]] = []

    total = len(clubs_df)
    for idx, club in clubs_df.iterrows():
        club_id = str(club["club_id"])
        club_name = str(club.get("club_name", "") or "")
        club_name_ascii = str(club.get("club_name_ascii", "") or "")
        variants = build_query_variants(club_name, club_name_ascii, max_variants=max_query_variants)

        if idx % 25 == 0:
            print(f"Searching Wikidata candidates: {idx + 1}/{total} clubs...", flush=True)

        for query in variants:
            results = client.search_entities(query, limit=search_limit)
            if results is None:
                search_rows.append({
                    "club_id": club_id,
                    "club_name": club_name,
                    "query": query,
                    "search_status": "api_request_failed",
                    "result_count": 0,
                    "qid": "",
                    "search_rank": "",
                    "search_label": "",
                    "search_description": "",
                })
                continue

            search_rows.append({
                "club_id": club_id,
                "club_name": club_name,
                "query": query,
                "search_status": "ok_no_results" if len(results) == 0 else "ok_results",
                "result_count": len(results),
                "qid": "",
                "search_rank": "",
                "search_label": "",
                "search_description": "",
            })

            for rank, result in enumerate(results, start=1):
                qid = result.get("id")
                if not qid:
                    continue

                existing = candidate_meta[club_id].get(qid)
                if existing is None or rank < int(existing.get("search_rank", 999)):
                    candidate_meta[club_id][qid] = {
                        "club_id": club_id,
                        "club_name": club_name,
                        "club_name_ascii": club_name_ascii,
                        "qid": qid,
                        "search_query": query,
                        "search_rank": rank,
                        "search_label": result.get("label", ""),
                        "search_description": result.get("description", ""),
                    }

                search_rows.append({
                    "club_id": club_id,
                    "club_name": club_name,
                    "query": query,
                    "search_status": "candidate",
                    "result_count": len(results),
                    "qid": qid,
                    "search_rank": rank,
                    "search_label": result.get("label", ""),
                    "search_description": result.get("description", ""),
                })

    candidate_rows = []
    for club_id, qid_map in candidate_meta.items():
        candidate_rows.extend(qid_map.values())

    return pd.DataFrame(candidate_rows), pd.DataFrame(search_rows)


def fetch_candidate_details(qids: List[str], client: WikimediaClient, batch_size: int = 40) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    qids = sorted(set(qids))

    for batch_num, batch in enumerate(chunked(qids, batch_size), start=1):
        print(f"Fetching SPARQL details batch {batch_num} ({len(batch)} QIDs)...", flush=True)
        values = " ".join(f"wd:{qid}" for qid in batch)
        query = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        PREFIX bd: <http://www.bigdata.com/rdf#>
        PREFIX schema: <http://schema.org/>

        SELECT ?club ?clubLabel ?clubDescription
               ?instanceOfLabel
               ?countryLabel ?leagueLabel
               ?stadium ?stadiumLabel ?stadiumCoord
               ?cityLabel ?clubCoord ?enwiki
        WHERE {{
          VALUES ?club {{ {values} }}

          OPTIONAL {{ ?club wdt:P31 ?instanceOf. }}
          OPTIONAL {{ ?club wdt:P17 ?country. }}
          OPTIONAL {{ ?club wdt:P118 ?league. }}

          OPTIONAL {{
            ?club wdt:P115 ?stadium.
            OPTIONAL {{ ?stadium wdt:P625 ?stadiumCoord. }}
            OPTIONAL {{ ?stadium wdt:P131 ?city. }}
          }}

          OPTIONAL {{ ?club wdt:P625 ?clubCoord. }}

          OPTIONAL {{
            ?enwiki schema:about ?club ;
                    schema:isPartOf <https://en.wikipedia.org/> .
          }}

          SERVICE wikibase:label {{
            bd:serviceParam wikibase:language "en".
            ?club rdfs:label ?clubLabel.
            ?club schema:description ?clubDescription.
            ?instanceOf rdfs:label ?instanceOfLabel.
            ?country rdfs:label ?countryLabel.
            ?league rdfs:label ?leagueLabel.
            ?stadium rdfs:label ?stadiumLabel.
            ?city rdfs:label ?cityLabel.
          }}
        }}
        """
        data = client.sparql(query)
        if data is None:
            for qid in batch:
                rows.append({
                    "wikidata_id": qid,
                    "detail_status": "sparql_failed_for_batch",
                    "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
                    "wikidata_label": "",
                    "wikidata_description": "",
                    "instance_of": "",
                    "country": "",
                    "league": "",
                    "stadium_wikidata_id": "",
                    "stadium": "",
                    "city": "",
                    "stadium_lat": "",
                    "stadium_lon": "",
                    "club_lat": "",
                    "club_lon": "",
                    "wikipedia_url": "",
                })
            continue

        bindings = data.get("results", {}).get("bindings", [])
        seen_in_batch = set()
        for row in bindings:
            club_uri = row.get("club", {}).get("value", "")
            qid = club_uri.rsplit("/", 1)[-1]
            seen_in_batch.add(qid)
            stadium_uri = row.get("stadium", {}).get("value", "")
            stadium_qid = stadium_uri.rsplit("/", 1)[-1] if stadium_uri else ""
            stadium_lat, stadium_lon = parse_wkt_point(row.get("stadiumCoord", {}).get("value"))
            club_lat, club_lon = parse_wkt_point(row.get("clubCoord", {}).get("value"))
            rows.append({
                "wikidata_id": qid,
                "detail_status": "ok",
                "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
                "wikidata_label": row.get("clubLabel", {}).get("value", ""),
                "wikidata_description": row.get("clubDescription", {}).get("value", ""),
                "instance_of": row.get("instanceOfLabel", {}).get("value", ""),
                "country": row.get("countryLabel", {}).get("value", ""),
                "league": row.get("leagueLabel", {}).get("value", ""),
                "stadium_wikidata_id": stadium_qid,
                "stadium": row.get("stadiumLabel", {}).get("value", ""),
                "city": row.get("cityLabel", {}).get("value", ""),
                "stadium_lat": stadium_lat if stadium_lat is not None else "",
                "stadium_lon": stadium_lon if stadium_lon is not None else "",
                "club_lat": club_lat if club_lat is not None else "",
                "club_lon": club_lon if club_lon is not None else "",
                "wikipedia_url": row.get("enwiki", {}).get("value", ""),
            })

        for qid in batch:
            if qid not in seen_in_batch:
                rows.append({
                    "wikidata_id": qid,
                    "detail_status": "no_sparql_detail_row",
                    "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
                    "wikidata_label": "",
                    "wikidata_description": "",
                    "instance_of": "",
                    "country": "",
                    "league": "",
                    "stadium_wikidata_id": "",
                    "stadium": "",
                    "city": "",
                    "stadium_lat": "",
                    "stadium_lon": "",
                    "club_lat": "",
                    "club_lon": "",
                    "wikipedia_url": "",
                })

    details_df = pd.DataFrame(rows)
    if details_df.empty:
        return details_df

    # Deduplicate detail rows caused by multiple instance_of/stadium rows.
    # Prefer rows with stadium coordinates, then any stadium, then Wikipedia URL.
    details_df["has_stadium_coords"] = details_df.apply(
        lambda r: pd.notna(r.get("stadium_lat")) and str(r.get("stadium_lat", "")).strip() != "" and pd.notna(r.get("stadium_lon")) and str(r.get("stadium_lon", "")).strip() != "",
        axis=1,
    )
    details_df["has_stadium"] = details_df["stadium"].astype(str).str.strip().ne("")
    details_df["has_wikipedia"] = details_df["wikipedia_url"].astype(str).str.strip().ne("")
    details_df = details_df.sort_values(
        ["wikidata_id", "has_stadium_coords", "has_stadium", "has_wikipedia"],
        ascending=[True, False, False, False],
    )
    details_df = details_df.drop_duplicates(subset=["wikidata_id"], keep="first")
    details_df = details_df.drop(columns=["has_stadium_coords", "has_stadium", "has_wikipedia"])
    return details_df


def has_value(value: Any) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip() != ""


def score_candidate(club_name: Any, club_name_ascii: Any, row: pd.Series) -> int:
    name_norms = [normalize_name(club_name), normalize_name(club_name_ascii)]
    name_norms = [n for n in name_norms if n]
    label_norm = normalize_name(row.get("wikidata_label", ""))
    search_label_norm = normalize_name(row.get("search_label", ""))

    best_name_score = 0.0
    if name_norms:
        for candidate_label in [label_norm, search_label_norm]:
            if candidate_label:
                best_name_score = max(best_name_score, max(SequenceMatcher(None, n, candidate_label).ratio() for n in name_norms))

    description = f"{row.get('wikidata_description', '')} {row.get('search_description', '')}".lower()
    instance_of = str(row.get("instance_of", "")).lower()
    label_all = f"{row.get('wikidata_label', '')} {row.get('search_label', '')}".lower()

    score = 0
    score += round(best_name_score * 45)

    if label_norm and label_norm in name_norms:
        score += 25
    elif search_label_norm and search_label_norm in name_norms:
        score += 15

    if any(hint in description for hint in FOOTBALL_HINT_WORDS):
        score += 15
    if "association football club" in instance_of or "football club" in instance_of:
        score += 22
    elif "sports club" in instance_of or "association football" in instance_of:
        score += 12

    if has_value(row.get("stadium")):
        score += 8
    if has_value(row.get("stadium_lat")) and has_value(row.get("stadium_lon")):
        score += 15
    elif has_value(row.get("club_lat")) and has_value(row.get("club_lon")):
        score += 7
    if has_value(row.get("wikipedia_url")):
        score += 5

    # Penalize obvious non-club entities.
    combined = f"{description} {instance_of} {label_all}"
    for bad in BAD_ENTITY_HINTS:
        if bad in combined and "football" not in combined and "soccer" not in combined:
            score -= 20
            break

    try:
        rank = int(row.get("search_rank", 99))
        score += max(0, 8 - rank)
    except Exception:
        pass

    return max(0, min(100, score))


def build_candidate_rows(candidate_search_df: pd.DataFrame, details_df: pd.DataFrame) -> pd.DataFrame:
    if candidate_search_df.empty:
        return pd.DataFrame()

    candidate_search_df = candidate_search_df.copy()
    if "qid" not in candidate_search_df.columns:
        # Defensive guard: v0.2 accidentally omitted qid from the deduped candidate rows.
        # If this ever happens again, keep the pipeline alive and route all clubs to review
        # instead of crashing or silently dropping rows.
        candidate_search_df["qid"] = ""

    candidate_search_df["qid"] = candidate_search_df["qid"].fillna("").astype(str).str.strip()
    candidate_search_df = candidate_search_df[candidate_search_df["qid"].ne("")].copy()
    if candidate_search_df.empty:
        return pd.DataFrame()

    if details_df.empty:
        candidates = candidate_search_df.copy()
        candidates["wikidata_id"] = candidates["qid"]
        candidates["detail_status"] = "no_details_requested_or_returned"
    else:
        candidates = candidate_search_df.merge(
            details_df,
            left_on="qid",
            right_on="wikidata_id",
            how="left",
        )

    for col in [
        "detail_status", "wikidata_url", "wikidata_label", "wikidata_description",
        "instance_of", "country", "league", "stadium_wikidata_id", "stadium",
        "city", "stadium_lat", "stadium_lon", "club_lat", "club_lon", "wikipedia_url",
    ]:
        if col not in candidates.columns:
            candidates[col] = ""
        candidates[col] = candidates[col].fillna("")

    candidates["candidate_score"] = candidates.apply(
        lambda row: score_candidate(row.get("club_name", ""), row.get("club_name_ascii", ""), row),
        axis=1,
    )
    return candidates


def classify_working_rows(clubs_df: pd.DataFrame, candidates_df: pd.DataFrame, search_log_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    working_rows: List[Dict[str, Any]] = []

    # Work out whether each club had API failures and whether it had any search results.
    search_status_by_club = defaultdict(lambda: {"api_failures": 0, "ok_queries": 0, "candidate_count": 0})
    if not search_log_df.empty:
        for _, row in search_log_df.iterrows():
            cid = row.get("club_id")
            if row.get("search_status") == "api_request_failed":
                search_status_by_club[cid]["api_failures"] += 1
            if str(row.get("search_status", "")).startswith("ok"):
                search_status_by_club[cid]["ok_queries"] += 1
            if row.get("search_status") == "candidate":
                search_status_by_club[cid]["candidate_count"] += 1

    grouped = {}
    if not candidates_df.empty:
        for club_id, group in candidates_df.groupby("club_id"):
            group = group.sort_values(["candidate_score", "search_rank"], ascending=[False, True])
            grouped[club_id] = group

    for _, club in clubs_df.iterrows():
        club_id = str(club["club_id"])
        base = club.to_dict()
        status_info = search_status_by_club[club_id]
        group = grouped.get(club_id)

        common_blank = {
            "candidate_score": "",
            "search_query": "",
            "search_rank": "",
            "search_label": "",
            "search_description": "",
            "wikidata_id": "",
            "wikidata_url": "",
            "wikidata_label": "",
            "wikidata_description": "",
            "instance_of": "",
            "country": "",
            "league": "",
            "stadium_wikidata_id": "",
            "stadium": "",
            "city": "",
            "stadium_lat": "",
            "stadium_lon": "",
            "club_lat": "",
            "club_lon": "",
            "wikipedia_url": "",
            "coordinate_basis": "",
            "geo_source_url": "",
            "proposed_club_lat": "",
            "proposed_club_lon": "",
            "approved_wikidata_id": "",
            "approved_stadium": "",
            "approved_lat": "",
            "approved_lon": "",
            "approved_geo_source_url": "",
            "manual_notes": "",
        }

        if group is None or group.empty:
            row = dict(base)
            row.update(common_blank)
            if status_info["api_failures"] > 0 and status_info["ok_queries"] == 0:
                row["match_status"] = "api_search_failed_all_queries"
                row["review_reason"] = "All Wikidata search requests failed for this club. Rerun or manually search."
            elif status_info["candidate_count"] == 0:
                row["match_status"] = "no_wikidata_candidates_found"
                row["review_reason"] = "No Wikidata candidates returned from search variants. Manual match required."
            else:
                row["match_status"] = "no_candidate_rows_unexpected"
                row["review_reason"] = "Search log suggests candidates, but candidate table has none. Check logs."
            row["manual_review_flag"] = "TRUE"
            working_rows.append(row)
            continue

        best = group.iloc[0]
        second_score = int(group.iloc[1]["candidate_score"]) if len(group) > 1 and has_value(group.iloc[1].get("candidate_score")) else 0
        top_score = int(best["candidate_score"])
        score_gap = top_score - second_score
        has_stadium_coords = has_value(best.get("stadium_lat")) and has_value(best.get("stadium_lon"))
        has_club_coords = has_value(best.get("club_lat")) and has_value(best.get("club_lon"))

        if top_score >= 82 and score_gap >= 8 and has_stadium_coords:
            match_status = "auto_candidate_high_stadium_coords"
            review_flag = "FALSE"
            review_reason = ""
        elif top_score >= 78 and has_stadium_coords:
            match_status = "candidate_stadium_coords_needs_spotcheck"
            review_flag = "TRUE"
            review_reason = "Good candidate with stadium coordinates, but ambiguity threshold was not fully met."
        elif top_score >= 72 and (has_stadium_coords or has_club_coords):
            match_status = "candidate_coords_need_review"
            review_flag = "TRUE"
            review_reason = "Candidate found with coordinates, but match confidence or coordinate basis needs review."
        elif top_score >= 68:
            match_status = "candidate_no_coordinates"
            review_flag = "TRUE"
            review_reason = "Candidate found, but no usable stadium or club coordinates were found."
        else:
            match_status = "needs_manual_match_review"
            review_flag = "TRUE"
            review_reason = "Low score or ambiguous candidate set. Manual match required."

        coord_basis = ""
        geo_source_url = ""
        final_lat = ""
        final_lon = ""
        if has_stadium_coords:
            coord_basis = "wikidata_home_venue_P115_to_stadium_P625"
            final_lat = best.get("stadium_lat", "")
            final_lon = best.get("stadium_lon", "")
            if has_value(best.get("stadium_wikidata_id")):
                geo_source_url = f"https://www.wikidata.org/wiki/{best.get('stadium_wikidata_id')}"
        elif has_club_coords:
            coord_basis = "wikidata_club_coordinate_P625_review_needed"
            final_lat = best.get("club_lat", "")
            final_lon = best.get("club_lon", "")
            geo_source_url = best.get("wikidata_url", "")

        row = dict(base)
        for col in [
            "candidate_score", "search_query", "search_rank", "search_label", "search_description",
            "wikidata_id", "wikidata_url", "wikidata_label", "wikidata_description", "instance_of",
            "country", "league", "stadium_wikidata_id", "stadium", "city", "stadium_lat",
            "stadium_lon", "club_lat", "club_lon", "wikipedia_url", "detail_status",
        ]:
            row[col] = best.get(col, "")
        row["match_status"] = match_status
        row["manual_review_flag"] = review_flag
        row["review_reason"] = review_reason
        row["coordinate_basis"] = coord_basis
        row["geo_source_url"] = geo_source_url
        row["proposed_club_lat"] = final_lat
        row["proposed_club_lon"] = final_lon
        row["approved_wikidata_id"] = ""
        row["approved_stadium"] = ""
        row["approved_lat"] = ""
        row["approved_lon"] = ""
        row["approved_geo_source_url"] = ""
        row["manual_notes"] = ""
        working_rows.append(row)

    working_df = pd.DataFrame(working_rows)
    review_df = working_df[working_df["manual_review_flag"].astype(str).str.upper() == "TRUE"].copy()
    no_candidate_df = working_df[working_df["match_status"].isin([
        "api_search_failed_all_queries",
        "no_wikidata_candidates_found",
        "no_candidate_rows_unexpected",
    ])].copy()
    return working_df, review_df, no_candidate_df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Step 6 Wikimedia/Wikidata club geocoding working files.")
    parser.add_argument("--workbook", required=True, help="Path to latest master workbook export (.xlsx).")
    parser.add_argument("--outdir", default="step6_working_outputs_v2", help="Output folder.")
    parser.add_argument("--contact", default=os.environ.get("WIKIMEDIA_CONTACT", ""), help="Contact email or URL for Wikimedia User-Agent. Strongly recommended.")
    parser.add_argument("--search-limit", type=int, default=10, help="Wikidata search candidates per query variant.")
    parser.add_argument("--max-query-variants", type=int, default=8, help="Max search query variants per club.")
    parser.add_argument("--search-delay", type=float, default=DEFAULT_SEARCH_DELAY_SECONDS, help="Delay after each Action API search request.")
    parser.add_argument("--sparql-delay", type=float, default=DEFAULT_SPARQL_DELAY_SECONDS, help="Delay after each SPARQL request.")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max retries per HTTP request.")
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not workbook_path.exists():
        print(f"ERROR: Workbook not found: {workbook_path}", file=sys.stderr)
        return 2

    if not args.contact:
        print("WARNING: --contact was not provided. Wikimedia recommends a User-Agent with contact information.", file=sys.stderr)

    client = WikimediaClient(
        contact=args.contact,
        search_delay_seconds=args.search_delay,
        sparql_delay_seconds=args.sparql_delay,
        max_retries=args.max_retries,
    )
    print(f"Using User-Agent: {client.user_agent}")

    clubs_df = pd.read_excel(workbook_path, sheet_name="clubs", dtype=str).fillna("")
    player_club_df = pd.read_excel(workbook_path, sheet_name="player_club_at_callup", dtype=str).fillna("")

    required_club_cols = {"club_id", "club_name", "club_name_ascii"}
    missing = required_club_cols - set(clubs_df.columns)
    if missing:
        raise ValueError(f"clubs sheet missing required columns: {sorted(missing)}")
    if "club_id" not in player_club_df.columns:
        raise ValueError("player_club_at_callup sheet missing club_id column")

    clubs_df["club_id"] = clubs_df["club_id"].astype(str).str.strip()
    player_club_df["club_id"] = player_club_df["club_id"].astype(str).str.strip()

    if clubs_df["club_id"].duplicated().any():
        dupes = clubs_df[clubs_df["club_id"].duplicated(keep=False)]["club_id"].tolist()
        raise ValueError(f"Duplicate club_id values found: {dupes[:20]}")

    missing_refs = sorted(set(player_club_df["club_id"]) - set(clubs_df["club_id"]))
    if missing_refs:
        raise ValueError(f"player_club_at_callup references missing club IDs: {missing_refs[:20]}")

    player_counts = player_club_df.groupby("club_id").size().rename("player_count").reset_index()
    clubs_df = clubs_df.merge(player_counts, on="club_id", how="left")
    clubs_df["player_count"] = clubs_df["player_count"].fillna(0).astype(int)

    write_csv(clubs_df, outdir / "clubs_step6_input_snapshot.csv")

    candidate_search_df, search_log_df = search_all_clubs(
        clubs_df=clubs_df,
        client=client,
        search_limit=args.search_limit,
        max_query_variants=args.max_query_variants,
    )

    write_csv(search_log_df, outdir / "club_wikidata_search_log_step6.csv")

    qids = sorted(set(candidate_search_df["qid"].dropna().astype(str))) if not candidate_search_df.empty and "qid" in candidate_search_df.columns else []
    details_df = fetch_candidate_details(qids, client=client) if qids else pd.DataFrame()

    candidates_df = build_candidate_rows(candidate_search_df, details_df)
    if not candidates_df.empty:
        candidates_df = candidates_df.sort_values(["club_id", "candidate_score", "search_rank"], ascending=[True, False, True])
    write_csv(candidates_df, outdir / "club_wikidata_candidates_step6.csv")

    working_df, review_df, no_candidate_df = classify_working_rows(clubs_df, candidates_df, search_log_df)
    write_csv(working_df, outdir / "clubs_step6_working.csv")
    write_csv(review_df, outdir / "club_geocoding_review_queue.csv")
    write_csv(no_candidate_df, outdir / "club_no_candidate_or_api_failure_queue.csv")

    client.write_request_log(outdir / "wikimedia_request_log_step6.csv")

    # Summary and invariant checks.
    candidate_clubs = candidates_df["club_id"].nunique() if not candidates_df.empty and "club_id" in candidates_df.columns else 0
    failed_requests = 0
    if client.request_log:
        failed_requests = sum(1 for row in client.request_log if row.status != "ok")

    status_counts = working_df["match_status"].value_counts(dropna=False).to_dict() if not working_df.empty else {}
    summary_rows = [
        {"metric": "clubs_input_rows", "value": len(clubs_df)},
        {"metric": "working_rows", "value": len(working_df)},
        {"metric": "wikidata_candidate_rows", "value": len(candidates_df)},
        {"metric": "clubs_with_candidate_rows", "value": candidate_clubs},
        {"metric": "clubs_with_no_candidates_or_api_failure", "value": len(no_candidate_df)},
        {"metric": "review_queue_rows", "value": len(review_df)},
        {"metric": "request_log_rows", "value": len(client.request_log)},
        {"metric": "failed_request_log_rows", "value": failed_requests},
    ]
    for status, count in sorted(status_counts.items()):
        summary_rows.append({"metric": f"match_status__{status}", "value": count})

    summary_df = pd.DataFrame(summary_rows)
    write_csv(summary_df, outdir / "step6_match_summary.csv")

    print("\nWrote Step 6 v2 working outputs to:", outdir)
    print(summary_df.to_string(index=False))

    if len(working_df) != len(clubs_df):
        print("ERROR: invariant failed: working rows do not equal input club rows.", file=sys.stderr)
        return 3

    print("\nInvariant check passed: clubs_step6_working.csv contains every input club.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
