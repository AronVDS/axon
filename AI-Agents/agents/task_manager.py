"""
TaskManagerAgent — manages tasks and to-do lists.
Stub: Notion / local DB integration coming in a future sprint.
"""


class TaskManagerAgent:
    def run(self, params: dict) -> str:
        action = params.get("action", "list")
        task   = params.get("task", "")

        if action == "list":
            return (
                "[TaskManager — stub] Taken ophalen is nog niet geïmplementeerd.\n"
                "  Roadmap : integratie met Notion of lokale JSON-takenlijst."
            )

        if action == "add":
            return (
                "[TaskManager — stub] Taak toevoegen is nog niet geïmplementeerd.\n"
                f"  Taak    : {task or '(geen)'}\n"
                "  Roadmap : taken opslaan in Notion of lokale database."
            )

        if action == "complete":
            return (
                "[TaskManager — stub] Taak afronden is nog niet geïmplementeerd.\n"
                f"  Taak    : {task or '(geen)'}\n"
                "  Roadmap : taakstatus bijwerken in Notion of lokale database."
            )

        return f"[TaskManager — stub] Onbekende actie: {action!r}. Gebruik 'list', 'add' of 'complete'."
