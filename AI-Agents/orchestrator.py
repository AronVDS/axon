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

4. document_agent — Genereert PDF- en TXT-documenten met llama3. Slaat op in docs/.
   Parameters:
     - document_type (str): "offerte", "weekrapport", "email", of "samenvatting"
     - company       (str, optioneel): bedrijfsnaam (voor offerte en email)
     - services      (str, optioneel): te offeren diensten (voor offerte)
     - price         (str, optioneel): prijs of budget (voor offerte)
     - recipient     (str, optioneel): ontvanger naam of bedrijf (voor email)
     - text          (str, optioneel): te samenvatten tekst (voor samenvatting)
     - context       (str, optioneel): extra context of beschrijving
     - topic         (str, optioneel): algemeen onderwerp of taakomschrijving

Kies altijd de meest passende agent op basis van de taak.
Als de taak gaat over leads zoeken of emails sturen naar nieuwe bedrijven → lead_generator.
Als de taak gaat over inkomende emails lezen of samenvatten → email_manager met action="read".
Als de taak gaat over inbox categoriseren of sorteren → email_manager met action="categorize".
Als de taak gaat over emails beantwoorden → email_manager met action="reply"; voeg query="vandaag" toe als de taak "van vandaag" vermeldt.
Als de taak gaat over een taak aanmaken of toevoegen → task_manager met action="add" en task=<omschrijving>.
Als de taak gaat over taken tonen of opvragen → task_manager met action="list"; zet filter="today" als "van vandaag" in de taak staat, filter="hoog" voor hoogprioritaire taken.
Als de taak gaat over een taak afronden of als klaar markeren → task_manager met action="complete" en task=<naam>.
Als de taak gaat over een taak verwijderen of wissen → task_manager met action="delete" en task=<naam>.
Als de taak gaat over een offerte of prijsopgave maken → document_agent met document_type="offerte"; extraheer company, services en price indien aanwezig.
Als de taak gaat over een weekrapport of activiteitsrapport → document_agent met document_type="weekrapport".
Als de taak gaat over een email opstellen of schrijven (niet beantwoorden van inbox) → document_agent met document_type="email"; zet recipient en context.
Als de taak gaat over tekst samenvatten → document_agent met document_type="samenvatting" en text=<te samenvatten tekst>.

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


def _sanitize_json(s: str) -> str:
    """Replace bare control characters inside JSON string values with escape sequences.

    llama3 sometimes outputs literal newlines/tabs inside string values, making
    the JSON invalid.  This walks character-by-character and fixes them only while
    inside a JSON string so we don't touch structural whitespace.
    """
    result = []
    in_string = False
    escaped = False
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
        elif ch == '\\' and in_string:
            result.append(ch)
            escaped = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\r':
            result.append('\\r')
        elif in_string and ch == '\t':
            result.append('\\t')
        else:
            result.append(ch)
    return ''.join(result)


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
        return json.loads(_sanitize_json(match.group()))

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
