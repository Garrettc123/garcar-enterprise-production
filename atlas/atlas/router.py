"""Explicit multi-agent routing for ATLAS.

Pure function selects the route. Optional LLM router agent may propose
a route on ambiguous intake; the result is always clamped to Route.
No path may select a silent send.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import settings
from .schemas import ShopIntake


class Route(str, Enum):
    TRADES_47 = "trades_47"
    TRADES_SPRINT = "trades_sprint"
    RE_497 = "re_497"
    RE_2500 = "re_2500"
    ATLAS_CUSTOM = "atlas_custom"
    REJECT = "reject"


ROUTE_URLS: dict[Route, str] = {
    Route.TRADES_47: "https://garrettc123.github.io/1",
    Route.TRADES_SPRINT: "https://garrettc123.github.io/2",
    Route.RE_497: "https://garrettc123.github.io/3",
    Route.RE_2500: "https://garrettc123.github.io/4",
    Route.ATLAS_CUSTOM: "https://garrettc123.github.io/5",
    Route.REJECT: settings.storefront,
}

ROUTE_SKUS: dict[Route, str] = {
    Route.TRADES_47: "47-audit",
    Route.TRADES_SPRINT: "497-week",
    Route.RE_497: "497-re",
    Route.RE_2500: "2500-re",
    Route.ATLAS_CUSTOM: "atlas",
    Route.REJECT: "none",
}

_TRADE_TRADES = {
    "hvac",
    "plumbing",
    "electrical",
    "electric",
    "gc",
    "general contracting",
    "general contractor",
    "roofing",
    "roof",
    "mechanical",
}
_TRADE_RE = {
    "real estate",
    "realty",
    "broker",
    "brokerage",
    "realtor",
    "agent",
    "re",
}


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str
    storefront_url: str
    sku: str
    source: str  # "rules" | "agent" | "cli"


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def select_route(
    intake: ShopIntake,
    sku: str | None = None,
    force: str | None = None,
) -> RouteDecision:
    """Deterministic router. Prefer explicit sku / force over inference."""
    if force:
        try:
            r = Route(force.strip().lower())
            return RouteDecision(
                route=r,
                reason=f"forced via CLI/API: {force}",
                storefront_url=ROUTE_URLS[r],
                sku=ROUTE_SKUS[r],
                source="cli",
            )
        except ValueError:
            return RouteDecision(
                route=Route.REJECT,
                reason=f"unknown force route: {force}",
                storefront_url=ROUTE_URLS[Route.REJECT],
                sku=ROUTE_SKUS[Route.REJECT],
                source="cli",
            )

    sku_key = _norm(sku or "")
    sku_map = {
        "47": Route.TRADES_47,
        "47-audit": Route.TRADES_47,
        "audit": Route.TRADES_47,
        "497-week": Route.TRADES_SPRINT,
        "497/wk": Route.TRADES_SPRINT,
        "sprint": Route.TRADES_SPRINT,
        "497-re": Route.RE_497,
        "re-review": Route.RE_497,
        "2500": Route.RE_2500,
        "2500-re": Route.RE_2500,
        "crm": Route.RE_2500,
        "safeguard": Route.RE_2500,
        "atlas": Route.ATLAS_CUSTOM,
        "custom": Route.ATLAS_CUSTOM,
    }
    if sku_key in sku_map:
        r = sku_map[sku_key]
        return RouteDecision(
            route=r,
            reason=f"sku={sku_key}",
            storefront_url=ROUTE_URLS[r],
            sku=ROUTE_SKUS[r],
            source="rules",
        )

    trade = _norm(intake.trade)
    if trade in _TRADE_RE or any(x in trade for x in _TRADE_RE):
        r = Route.RE_497
        return RouteDecision(
            route=r,
            reason=f"trade looks real-estate: {intake.trade}",
            storefront_url=ROUTE_URLS[r],
            sku=ROUTE_SKUS[r],
            source="rules",
        )
    if trade in _TRADE_TRADES or any(x in trade for x in _TRADE_TRADES):
        r = Route.TRADES_47
        return RouteDecision(
            route=r,
            reason=f"trade looks contractor: {intake.trade}",
            storefront_url=ROUTE_URLS[r],
            sku=ROUTE_SKUS[r],
            source="rules",
        )

    return RouteDecision(
        route=Route.REJECT,
        reason=f"could not classify trade={intake.trade!r}; pass --sku or --route",
        storefront_url=ROUTE_URLS[Route.REJECT],
        sku=ROUTE_SKUS[Route.REJECT],
        source="rules",
    )


def clamp_route_label(label: str) -> Route | None:
    raw = _norm(label).replace(" ", "_").replace("-", "_")
    for r in Route:
        if r.value == raw or r.name.lower() == raw:
            return r
    for r in Route:
        if r.value in raw:
            return r
    return None


def route_with_agent(intake: ShopIntake, sku: str | None = None) -> RouteDecision:
    """LLM router agent proposes a route; result is clamped to Route."""
    baseline = select_route(intake, sku=sku)
    if baseline.route != Route.REJECT:
        return baseline

    if not settings.openai_api_key or settings.dry_run:
        return baseline

    try:
        from crewai import Agent, Crew, LLM, Process, Task

        llm = LLM(model=settings.model, api_key=settings.openai_api_key)
        router = Agent(
            role="Route Dispatcher",
            goal=(
                "Output exactly one route key for this intake. "
                "Never invent phone numbers. Never choose a silent send."
            ),
            backstory=(
                "You are the ATLAS control-plane router for Garcar Enterprise. "
                "Allowed keys only: trades_47, trades_sprint, re_497, re_2500, "
                "atlas_custom, reject. Prefer reject over wrong product."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )
        task = Task(
            description=(
                f"Shop={intake.shop}; trade={intake.trade}; city={intake.city}; "
                f"owner={intake.owner}; sku_hint={sku or 'none'}. "
                "Reply with ONLY the route key on the first line, then one reason."
            ),
            expected_output="First line: trades_47|trades_sprint|re_497|re_2500|atlas_custom|reject",
            agent=router,
        )
        crew = Crew(
            agents=[router],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        raw = str(crew.kickoff()).strip()
        first = raw.splitlines()[0] if raw else ""
        parsed = clamp_route_label(first) or clamp_route_label(raw)
        if parsed is None:
            return baseline
        return RouteDecision(
            route=parsed,
            reason=f"agent: {raw[:240]}",
            storefront_url=ROUTE_URLS[parsed],
            sku=ROUTE_SKUS[parsed],
            source="agent",
        )
    except Exception as exc:  # noqa: BLE001
        return RouteDecision(
            route=baseline.route,
            reason=f"agent failed ({exc}); used rules: {baseline.reason}",
            storefront_url=baseline.storefront_url,
            sku=baseline.sku,
            source="rules",
        )
