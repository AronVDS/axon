"""
EmailManagerAgent — reads and replies to emails.
Stub: Gmail integration coming in a future sprint.
"""


class EmailManagerAgent:
    def run(self, params: dict) -> str:
        action = params.get("action", "read")
        query  = params.get("query", "")

        if action == "read":
            return (
                "[EmailManager — stub] Emails lezen is nog niet geïmplementeerd.\n"
                f"  Zoekopdracht : {query or '(geen)'}\n"
                "  Roadmap      : Gmail API inkomende emails ophalen en samenvatten."
            )

        if action == "reply":
            return (
                "[EmailManager — stub] Emails beantwoorden is nog niet geïmplementeerd.\n"
                f"  Zoekopdracht : {query or '(geen)'}\n"
                "  Roadmap      : automatisch antwoorden via Gmail API met llama3."
            )

        return f"[EmailManager — stub] Onbekende actie: {action!r}. Gebruik 'read' of 'reply'."
