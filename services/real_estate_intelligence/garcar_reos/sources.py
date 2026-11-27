"""Curated official record entrypoints, not scraped APIs or verified property facts.

The operator must review record accuracy, permitted use, terms and data freshness.
"""
SOURCES = [
    {
        "id": "johnson_cad", "name": "Johnson County Appraisal District Property Search",
        "region": "Johnson County, Texas", "kind": "appraisal",
        "url": "https://johnsoncad.com/property-search/",
        "limitations": "Appraisal values are for ad valorem tax purposes, not an appraisal of market resale value; verify parcel descriptions."
    },
    {
        "id": "johnson_clerk", "name": "Johnson County Clerk Online Records",
        "region": "Johnson County, Texas", "kind": "recorded_deeds",
        "url": "https://www.johnsoncountytx.org/government/county-clerk/online-records",
        "limitations": "Online records are not necessarily the complete or authoritative official repository; request certified records/title review."
    },
    {
        "id": "johnson_record_search", "name": "Johnson County Clerk Official Record Search",
        "region": "Johnson County, Texas", "kind": "recorded_deeds",
        "url": "https://johnson.tx.publicsearch.us/",
        "limitations": "Record search is a research entrypoint only; confirm authenticity and coverage with the clerk/title company."
    },
    {
        "id": "tx_occupation_1101", "name": "Texas Occupations Code, Ch. 1101 — Equitable Interests",
        "region": "Texas", "kind": "legal_reference",
        "url": "https://statutes.capitol.texas.gov/Docs/OC/html/OC.1101.htm",
        "limitations": "Legal reference only; seek independent Texas counsel for transaction structure and disclosure."
    },
    {
        "id": "tx_trec_5356", "name": "TREC Rules — Equitable Interests in Real Property",
        "region": "Texas", "kind": "legal_reference",
        "url": "https://www.trec.texas.gov/agency-information/rules-and-laws/trec-rules",
        "limitations": "Regulatory guidance; does not authorize unlicensed brokerage or replace legal review."
    },
]

def list_sources(region: str | None = None) -> list[dict]:
    if region:
        return [s for s in SOURCES if region.casefold() in s["region"].casefold()]
    return SOURCES
