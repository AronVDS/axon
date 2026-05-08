"""
DocumentAgent — creates documents and reports.
Stub: document generation with llama3 coming in a future sprint.
"""


class DocumentAgent:
    def run(self, params: dict) -> str:
        document_type = params.get("document_type", "document")
        topic         = params.get("topic", "")

        return (
            "[DocumentAgent — stub] Documenten aanmaken is nog niet geïmplementeerd.\n"
            f"  Type       : {document_type}\n"
            f"  Onderwerp  : {topic or '(geen)'}\n"
            "  Roadmap    : offertes, rapporten en verslagen genereren met llama3 → exporteren naar PDF/Word."
        )
