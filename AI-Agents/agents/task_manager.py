"""
TaskManagerAgent — creates, lists, completes, and deletes tasks stored in tasks.json.
Supports smart creation from Dutch natural language via Ollama llama3.
"""

import json
import os
import re
import uuid
from datetime import date, datetime

import ollama

_TASKS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tasks.json")
)
_PRIORITIES = ("hoog", "normaal", "laag")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _load() -> list[dict]:
    if not os.path.exists(_TASKS_PATH):
        return []
    with open(_TASKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(tasks: list[dict]) -> None:
    with open(_TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Ollama: smart parse
# ---------------------------------------------------------------------------

def _smart_parse(text: str) -> dict:
    """Parse a Dutch natural-language task description into structured fields."""
    today_str = date.today().isoformat()
    response  = ollama.chat(
        model="llama3",
        format="json",
        messages=[{
            "role": "user",
            "content": (
                f"Vandaag is {today_str}.\n"
                "Analyseer de volgende taakomschrijving en geef een JSON-object terug met:\n"
                '  "title"       : korte taaktitel (max 60 tekens)\n'
                '  "description" : extra details of lege string\n'
                '  "priority"    : "hoog", "normaal", of "laag"\n'
                '  "due_date"    : vervaldatum als ISO-string YYYY-MM-DD, of null\n\n'
                "Regels:\n"
                '- "morgen" → dag na vandaag als ISO-datum\n'
                '- "volgende week" → aankomende maandag als ISO-datum\n'
                '- Urgente/dringende woorden → priority "hoog"\n'
                "- Antwoord UITSLUITEND met een geldig JSON-object, geen uitleg.\n\n"
                f"Taakomschrijving: {text}"
            ),
        }],
    )
    raw     = response["message"]["content"].strip()
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    match   = re.search(r"\{[\s\S]*\}", cleaned)

    if match:
        try:
            data     = json.loads(match.group())
            priority = str(data.get("priority", "normaal")).lower()
            if priority not in _PRIORITIES:
                priority = "normaal"

            due_date = None
            raw_date = data.get("due_date")
            if raw_date:
                try:
                    datetime.fromisoformat(str(raw_date))
                    due_date = str(raw_date)[:10]
                except ValueError:
                    pass

            return {
                "title":       str(data.get("title", text))[:60],
                "description": str(data.get("description", "")),
                "priority":    priority,
                "due_date":    due_date,
            }
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: raw text as title
    return {"title": text[:60], "description": "", "priority": "normaal", "due_date": None}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _add_task(title: str, description: str, priority: str, due_date: str | None) -> dict:
    task = {
        "id":          uuid.uuid4().hex[:8],
        "title":       title,
        "description": description,
        "priority":    priority,
        "due_date":    due_date,
        "done":        False,
        "created_at":  datetime.now().isoformat(timespec="seconds"),
    }
    tasks = _load()
    tasks.append(task)
    _save(tasks)
    return task


def _find(tasks: list[dict], query: str) -> dict | None:
    """Match by ID prefix or case-insensitive title substring."""
    q = query.strip().lower()
    for t in tasks:
        if t["id"].startswith(q) or q in t["title"].lower():
            return t
    return None


_MONTHS_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]
_DAYS_NL = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def _fmt_due(due_str: str) -> str:
    """ISO date → friendly Dutch string: ', morgen' / ', dinsdag' / ', volgende week' / ', 16 mei'."""
    try:
        due   = date.fromisoformat(due_str)
        delta = (due - date.today()).days
    except ValueError:
        return f", {due_str}"

    if delta < 0:
        n = abs(delta)
        return f", {n} dag{'en' if n != 1 else ''} te laat"
    if delta == 0:  return ", vandaag"
    if delta == 1:  return ", morgen"
    if delta <= 6:  return f", {_DAYS_NL[due.weekday()]}"
    if delta <= 13: return ", volgende week"
    return f", {due.day} {_MONTHS_NL[due.month - 1]}"


def _fmt(t: dict) -> str:
    due  = _fmt_due(t["due_date"]) if t.get("due_date") else ""
    desc = f"\n  {t['description']}" if t.get("description") else ""
    return f"• {t['title']}{due}{desc}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class TaskManagerAgent:
    def run(self, params: dict) -> str:
        action = params.get("action", "list")

        if action == "add":
            return self._do_add(params)
        if action == "list":
            return self._do_list(params)
        if action == "complete":
            return self._do_complete(params)
        if action == "delete":
            return self._do_delete(params)

        return (
            f"[TaskManager] Onbekende actie: {action!r}. "
            "Gebruik 'add', 'list', 'complete' of 'delete'."
        )

    # ------------------------------------------------------------------

    def _do_add(self, params: dict) -> str:
        title    = params.get("title", "")
        raw_text = params.get("task") or params.get("text") or title

        if not raw_text:
            return "[TaskManager] Geen taakomschrijving opgegeven."

        if title:
            # Structured input — no need for llama3
            priority = params.get("priority", "normaal").lower()
            if priority not in _PRIORITIES:
                priority = "normaal"
            due_date = params.get("due_date") or None
            task = _add_task(title, params.get("description", ""), priority, due_date)
        else:
            # Natural language → smart parse with llama3
            print(f"  Analyseer taak met llama3: {raw_text[:60]}...")
            parsed = _smart_parse(raw_text)
            task   = _add_task(**parsed)

        due_line = _fmt_due(task["due_date"]) if task.get("due_date") else ""
        return f"✓ Taak aangemaakt: {task['title']}{due_line}."

    def _do_list(self, params: dict) -> str:
        tasks   = _load()
        filter_ = (params.get("filter") or "all").lower()
        today   = date.today().isoformat()

        if filter_ == "today":
            subset = [t for t in tasks if not t["done"] and t.get("due_date") == today]
            header = f"Taken voor vandaag ({today}):"
        elif filter_ in _PRIORITIES:
            subset = [t for t in tasks if not t["done"] and t["priority"] == filter_]
            header = f"Taken met prioriteit '{filter_}':"
        elif filter_ == "done":
            subset = [t for t in tasks if t["done"]]
            header = "Voltooide taken:"
        else:
            subset = [t for t in tasks if not t["done"]]
            header = f"Openstaande taken ({len(subset)}):"

        if not subset:
            return f"{header}\n  (geen)"

        lines = [header]
        for t in subset:
            lines.append(_fmt(t))
        return "\n".join(lines)

    def _do_complete(self, params: dict) -> str:
        query = params.get("task") or params.get("query") or params.get("title", "")
        if not query:
            return "[TaskManager] Geef een taaknaam of ID op om als klaar te markeren."

        tasks  = _load()
        target = _find([t for t in tasks if not t["done"]], query)
        if not target:
            return f"[TaskManager] Geen openstaande taak gevonden voor: {query!r}"

        target["done"] = True
        _save(tasks)
        return f"✓ {target['title']} — gemarkeerd als klaar."

    def _do_delete(self, params: dict) -> str:
        query = params.get("task") or params.get("query") or params.get("title", "")
        if not query:
            return "[TaskManager] Geef een taaknaam of ID op om te verwijderen."

        tasks  = _load()
        target = _find(tasks, query)
        if not target:
            return f"[TaskManager] Geen taak gevonden voor: {query!r}"

        tasks.remove(target)
        _save(tasks)
        return f"✓ {target['title']} — verwijderd."
