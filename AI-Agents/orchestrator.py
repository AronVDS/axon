#!/usr/bin/env python3
"""
Axon Orchestrator — central brain that routes Dutch tasks to the right agent.
Usage: python orchestrator.py "Vind 10 leads in Gent en stuur ze een email"
"""

import json
import re
import sys

import ollama

from agents.lead_generator import LeadGeneratorAgent
from agents.email_manager import EmailManagerAgent
from agents.task_manager import TaskManagerAgent
from agents.document_agent import DocumentAgent

_SYSTEM_PROMPT = """\
Je bent de centrale orchestrator van Axon, een AI Chief of Staff voor Belgische KMO's.
Je krijgt een taak in het Nederlands en beslist welk agent je inzet.

Beschikbare agents:
1. lead_generator — Zoekt bedrijven in een stad en genereert/verstuurt koude acquisitie-emails.
   Parameters:
     - business_type (str, verplicht): type bedrijf, bv. "marketingbureau", "accountant"
     - location      (str, verplicht): stad of regio, bv. "Gent", "Brussel"
     - limit         (int, optioneel, standaard 10): max aantal leads
     - dry_run       (bool, optioneel, standaard true): true = geen echte emails versturen

2. email_manager — Leest, categoriseert of beantwoordt emails in de Gmail inbox.
   Parameters:
     - action (str): "read" (ongelezen emails tonen), "categorize" (inbox categoriseren), of "reply" (emails beantwoorden)
     - query  (str, optioneel): extra filter, bv. "vandaag" voor emails van vandaag, of een Gmail-zoekterm
     - limit  (int, optioneel, standaard 10): max aantal emails

3. task_manager — Beheert taken en to-do's opgeslagen in tasks.json.
   Parameters:
     - action      (str): "add", "list", "complete", of "delete"
     - task        (str, optioneel): taakomschrijving of naam (voor add/complete/delete); bij add zonder title wordt dit slim geparsed door llama3
     - title       (str, optioneel): expliciete taaktitel (voor add, overschrijft smart parse)
     - description (str, optioneel): extra toelichting (voor add)
     - priority    (str, optioneel): "hoog", "normaal", of "laag" (voor add, standaard "normaal")
     - due_date    (str, optioneel): vervaldatum als YYYY-MM-DD (voor add)
     - filter      (str, optioneel): "all", "today", "hoog", "normaal", "laag", of "done" (voor list; standaard "all")

4. document_agent — Maakt documenten of rapporten aan.
   Parameters:
     - document_type (str): bv. "offerte", "rapport", "verslag"
     - topic         (str): onderwerp van het document

Kies altijd de meest passende agent op basis van de taak.
Als de taak gaat over leads zoeken of emails sturen naar nieuwe bedrijven → lead_generator.
Als de taak gaat over inkomende emails lezen of samenvatten → email_manager met action="read".
Als de taak gaat over inbox categoriseren of sorteren → email_manager met action="categorize".
Als de taak gaat over emails beantwoorden → email_manager met action="reply"; voeg query="vandaag" toe als de taak "van vandaag" vermeldt.
Als de taak gaat over een taak aanmaken of toevoegen → task_manager met action="add" en task=<omschrijving>.
Als de taak gaat over taken tonen of opvragen → task_manager met action="list"; zet filter="today" als "van vandaag" in de taak staat, filter="hoog" voor hoogprioritaire taken.
Als de taak gaat over een taak afronden of als klaar markeren → task_manager met action="complete" en task=<naam>.
Als de taak gaat over een taak verwijderen of wissen → task_manager met action="delete" en task=<naam>.
Als de taak gaat over documenten, offertes, rapporten aanmaken → document_agent.

Antwoord UITSLUITEND met een geldig JSON-object, geen markdown, geen uitleg erbuiten:
{
  "agent": "<agent_naam>",
  "parameters": { ... },
  "reden": "<één zin waarom je dit agent kiest>"
}"""


AGENTS: dict = {
    "lead_generator": LeadGeneratorAgent(),
    "email_manager":  EmailManagerAgent(),
    "task_manager":   TaskManagerAgent(),
    "document_agent": DocumentAgent(),
}


def route_task(task: str) -> dict:
    """Ask llama3 which agent and parameters to use for the given Dutch task."""
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Taak: {task}"},
        ],
    )
    raw = response["message"]["content"].strip()

    # Strip markdown code fences that llama3 sometimes adds
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        return json.loads(match.group())

    raise ValueError(
        f"llama3 gaf geen geldig JSON-object terug.\nAntwoord was:\n{raw}"
    )


def run(task: str) -> str:
    print("\nAxon Orchestrator")
    print(f"  Taak : {task}\n")

    print("Analyseren met llama3...")
    try:
        routing = route_task(task)
    except Exception as exc:
        msg = f"[FOUT] Kan taak niet analyseren: {exc}"
        print(msg)
        return msg

    agent_name = routing.get("agent", "")
    parameters = routing.get("parameters", {})
    reden      = routing.get("reden", "")

    print(f"  Agent  : {agent_name}")
    print(f"  Params : {json.dumps(parameters, ensure_ascii=False)}")
    print(f"  Reden  : {reden}\n")

    if agent_name not in AGENTS:
        available = ", ".join(AGENTS.keys())
        msg = f"[FOUT] Onbekende agent: {agent_name!r}. Beschikbaar: {available}"
        print(msg)
        return msg

    result = AGENTS[agent_name].run(parameters)

    print("\n--- Samenvatting ---")
    print(result)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Gebruik: python orchestrator.py "<taak in het Nederlands>"')
        print('Voorbeeld: python orchestrator.py "Vind 10 leads in Gent en stuur ze een email"')
        sys.exit(1)

    run(" ".join(sys.argv[1:]))
