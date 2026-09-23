from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task

from .config import settings
from .schemas import ShopIntake


def _llm() -> LLM:
    return LLM(model=settings.model, api_key=settings.openai_api_key or None)


def build_crew(intake: ShopIntake) -> Crew:
    llm = _llm()

    scout = Agent(
        role="Intake Scout",
        goal="Normalize one Johnson County / South DFW shop into a clean intake record.",
        backstory=(
            "You work Grandview, Cleburne, Alvarado, Burleson, Midlothian. "
            "You do not invent phone numbers. You only structure what you are given."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    analyst = Agent(
        role="Leak Analyst",
        goal="Name at most five post-lead leaks with monthly dollar cost and one fix each.",
        backstory=(
            "You diagnose response-time drop-offs, missed calls, silent estimates, "
            "and shared-lead races. You never pitch software stacks."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    writer = Agent(
        role="Fulfillment Writer",
        goal="Produce the six-section Contractor Lead Leak Audit ready to email in 48 hours.",
        backstory=(
            "You fill the Garcar delivery template. Section 6 is $497/wk and only "
            "appears after the map. You sign as Garrett Carrol, Grandview / Kopperl."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    closer = Agent(
        role="Closer",
        goal="Write one shop-owner SMS. Do not send it. Human gate required.",
        backstory=(
            "You sell the $47 map first. You do not email VCs. You do not mention "
            "CrewAI or agents to the shop owner."
        ),
        llm=llm,
        allow_delegation=False,
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
        agent=scout,
    )
    t_leaks = Task(
        description=(
            "From the intake, list max 5 leaks. Each leak: name, where it happens, "
            "monthly $ (jobs/week missed × close rate × average ticket), one fix. "
            "Recommend one first workflow only."
        ),
        expected_output="Five named leaks with monthly $ and one first workflow.",
        agent=analyst,
        context=[t_intake],
    )
    t_map = Task(
        description=(
            "Write the six-section Lead Leak Audit markdown using the official header "
            "and close. Include sprint link only in section 6: "
            f"{settings.sku_sprint}"
        ),
        expected_output="Complete markdown audit map.",
        agent=writer,
        context=[t_intake, t_leaks],
    )
    t_close = Task(
        description=(
            "Write one SMS using this frame: Hey [Name] — I’m Garrett in Grandview. "
            f"Link the storefront {settings.storefront}. Do not send. Mark HUMAN_SEND_REQUIRED."
        ),
        expected_output="One SMS plus HUMAN_SEND_REQUIRED flag.",
        agent=closer,
        context=[t_map],
    )

    return Crew(
        agents=[scout, analyst, writer, closer],
        tasks=[t_intake, t_leaks, t_map, t_close],
        process=Process.sequential,
        verbose=True,
    )
