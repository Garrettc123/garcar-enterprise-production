from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task

from .config import settings
from .router import Route, RouteDecision
from .schemas import ShopIntake


def _llm() -> LLM:
    return LLM(model=settings.model, api_key=settings.openai_api_key or None)


def _agents(llm: LLM) -> dict[str, Agent]:
    return {
        "scout": Agent(
            role="Intake Scout",
            goal="Normalize one Johnson County / South DFW shop into a clean intake record.",
            backstory=(
                "You work Grandview, Cleburne, Alvarado, Burleson, Midlothian. "
                "You do not invent phone numbers. You only structure what you are given."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "analyst": Agent(
            role="Leak Analyst",
            goal="Name at most five post-lead leaks with monthly dollar cost and one fix each.",
            backstory=(
                "You diagnose response-time drop-offs, missed calls, silent estimates, "
                "and shared-lead races. You never pitch software stacks."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "writer": Agent(
            role="Fulfillment Writer",
            goal="Produce the six-section Contractor Lead Leak Audit ready to email in 48 hours.",
            backstory=(
                "You fill the Garcar delivery template. Section 6 is $497/wk and only "
                "appears after the map. You sign as Garrett Carrol, Grandview / Kopperl."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "closer": Agent(
            role="Closer",
            goal="Write one shop-owner SMS. Do not send it. Human gate required.",
            backstory=(
                "You sell the entry offer first. You do not email VCs. You do not mention "
                "CrewAI or agents to the buyer."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "re_analyst": Agent(
            role="RE List Analyst",
            goal="Report only what one lead export can prove; never invent call times.",
            backstory=(
                "You work DFW team leads. If the list has no call log, write "
                "'cannot tell from this list.' You do not promise closings."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
        "architect": Agent(
            role="Systems Architect",
            goal="Scope an ATLAS organ: hops, gates, detach path — no chatbot wrapper.",
            backstory=(
                "You design BioForge Revenue organs. Money and send hops stay gated."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        ),
    }


def build_crew(intake: ShopIntake, decision: RouteDecision) -> Crew:
    """Build a sequential crew for the selected route. No silent send hops."""
    llm = _llm()
    a = _agents(llm)
    link = decision.storefront_url
    route = decision.route

    if route == Route.REJECT:
        t = Task(
            description=(
                f"Intake rejected: shop={intake.shop}, trade={intake.trade}, "
                f"reason={decision.reason}. Write a one-paragraph operator note "
                "telling Garrett what --sku or --route to pass. Do not write buyer SMS."
            ),
            expected_output="Operator note only. No buyer-facing copy.",
            agent=a["scout"],
        )
        return Crew(agents=[a["scout"]], tasks=[t], process=Process.sequential, verbose=True)

    if route == Route.RE_497:
        t1 = Task(
            description=(
                f"Normalize RE team intake: name={intake.shop}, city={intake.city}, "
                f"owner={intake.owner}. Compact intake block only."
            ),
            expected_output="Clean RE intake block.",
            agent=a["scout"],
        )
        t2 = Task(
            description=(
                "Describe what a $497 one-list review will and will not prove. "
                "Emphasize: no guessing that agents missed calls."
            ),
            expected_output="Review scope + cannot-tell rules.",
            agent=a["re_analyst"],
            context=[t1],
        )
        t3 = Task(
            description=(
                f"Write one SMS to the team lead selling the $497 review. "
                f"Link {link}. Mark HUMAN_SEND_REQUIRED. Do not send."
            ),
            expected_output="One SMS + HUMAN_SEND_REQUIRED.",
            agent=a["closer"],
            context=[t2],
        )
        return Crew(
            agents=[a["scout"], a["re_analyst"], a["closer"]],
            tasks=[t1, t2, t3],
            process=Process.sequential,
            verbose=True,
        )

    if route == Route.RE_2500:
        t1 = Task(
            description=(
                f"Team={intake.shop}, city={intake.city}. Draft the $2,500 CRM Safeguard "
                "install outline: owner, timer, backup person, manager view."
            ),
            expected_output="Install outline for Follow Up Boss or current CRM.",
            agent=a["re_analyst"],
        )
        t2 = Task(
            description=(
                f"One SMS inviting them to the $2,500 install. Link {link}. "
                "HUMAN_SEND_REQUIRED. Do not send."
            ),
            expected_output="One SMS + HUMAN_SEND_REQUIRED.",
            agent=a["closer"],
            context=[t1],
        )
        return Crew(
            agents=[a["re_analyst"], a["closer"]],
            tasks=[t1, t2],
            process=Process.sequential,
            verbose=True,
        )

    if route == Route.ATLAS_CUSTOM:
        t1 = Task(
            description=(
                f"Scope ATLAS for {intake.shop} ({intake.trade}, {intake.city}): "
                "list hops intake→fulfill, mark which hops need HUMAN_SEND or payment gate."
            ),
            expected_output="Scoped hop list with gates.",
            agent=a["architect"],
        )
        t2 = Task(
            description=(
                f"Short operator email draft to scope a paid architecture engagement. "
                f"Link {link}. HUMAN_SEND_REQUIRED."
            ),
            expected_output="Operator-facing email draft + HUMAN_SEND_REQUIRED.",
            agent=a["closer"],
            context=[t1],
        )
        return Crew(
            agents=[a["architect"], a["closer"]],
            tasks=[t1, t2],
            process=Process.sequential,
            verbose=True,
        )

    if route == Route.TRADES_SPRINT:
        t1 = Task(
            description=(
                f"Shop={intake.shop}. Assume $47 map already delivered. "
                "Scope the $497/wk one-workflow sprint (default: missed-call SMS <60s)."
            ),
            expected_output="Sprint scope + done definition.",
            agent=a["analyst"],
        )
        t2 = Task(
            description=(
                f"One SMS for the $497/wk sprint. Link {link}. "
                "HUMAN_SEND_REQUIRED. Do not send."
            ),
            expected_output="One SMS + HUMAN_SEND_REQUIRED.",
            agent=a["closer"],
            context=[t1],
        )
        return Crew(
            agents=[a["analyst"], a["closer"]],
            tasks=[t1, t2],
            process=Process.sequential,
            verbose=True,
        )

    t_intake = Task(
        description=(
            f"Normalize this shop: name={intake.shop}, trade={intake.trade}, "
            f"city={intake.city}, owner={intake.owner}, sources={intake.sources}, "
            f"ticket={intake.ticket}, jobs_week={intake.jobs_week}, close_rate={intake.close_rate}. "
            "Return a compact intake block."
        ),
        expected_output="Clean intake: shop, trade, city, owner, sources, ticket math inputs.",
        agent=a["scout"],
    )
    t_leaks = Task(
        description=(
            "From the intake, list max 5 leaks. Each leak: name, where it happens, "
            "monthly $ (jobs/week missed × close rate × average ticket), one fix. "
            "Recommend one first workflow only."
        ),
        expected_output="Five named leaks with monthly $ and one first workflow.",
        agent=a["analyst"],
        context=[t_intake],
    )
    t_map = Task(
        description=(
            "Write the six-section Lead Leak Audit markdown using the official header "
            "and close. Include sprint link only in section 6: "
            f"{settings.sku_sprint}"
        ),
        expected_output="Complete markdown audit map.",
        agent=a["writer"],
        context=[t_intake, t_leaks],
    )
    t_close = Task(
        description=(
            "Write one SMS using this frame: Hey [Name] — I’m Garrett in Grandview. "
            f"Link {link}. Do not send. Mark HUMAN_SEND_REQUIRED."
        ),
        expected_output="One SMS plus HUMAN_SEND_REQUIRED flag.",
        agent=a["closer"],
        context=[t_map],
    )
    return Crew(
        agents=[a["scout"], a["analyst"], a["writer"], a["closer"]],
        tasks=[t_intake, t_leaks, t_map, t_close],
        process=Process.sequential,
        verbose=True,
    )
