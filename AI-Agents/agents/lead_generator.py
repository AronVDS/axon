"""
LeadGeneratorAgent — wraps the existing AILeadGenerator pipeline.
Adds the AILeadGenerator directory to sys.path so its modules can be imported directly.
"""

import os
import sys

_AGENTS_DIR   = os.path.dirname(os.path.abspath(__file__))          # AI-Agents/agents/
_LEAD_GEN_DIR = os.path.normpath(os.path.join(_AGENTS_DIR, "..", "AILeadGenerator"))

if _LEAD_GEN_DIR not in sys.path:
    sys.path.insert(0, _LEAD_GEN_DIR)


class LeadGeneratorAgent:
    def run(self, params: dict) -> str:
        business_type = params.get("business_type", "bedrijf")
        location      = params.get("location", "Gent")
        limit         = int(params.get("limit", 10))
        dry_run       = bool(params.get("dry_run", True))

        from maps_client    import OSMClient
        from email_generator import EmailGenerator
        from leads_manager  import LeadsManager

        maps      = OSMClient()
        email_gen = EmailGenerator()
        leads_csv = os.path.join(_LEAD_GEN_DIR, "leads.csv")
        leads     = LeadsManager(leads_csv)

        gmail = None
        if not dry_run:
            sender_email = os.getenv("SENDER_EMAIL", "axon.aiagents@gmail.com")
            from gmail_client import GmailClient
            gmail = GmailClient(sender_email)

        mode = "dry-run (geen emails verstuurd)" if dry_run else "live"
        print(f"  Zoeken naar {business_type!r} in {location!r} — max {limit} — {mode}")

        businesses = maps.search_businesses(business_type, location, limit)
        print(f"  Gevonden: {len(businesses)} bedrijf/bedrijven\n")

        sent = failed = skipped = no_email = 0

        for biz in businesses:
            name = biz["name"]

            if leads.is_duplicate(name, biz["address"]):
                print(f"  SKIP (al verwerkt): {name}")
                skipped += 1
                continue

            email_content = email_gen.generate_cold_email(biz)

            if dry_run:
                print(f"  DRY-RUN: {name} — {biz.get('email') or 'geen email gevonden'}")
                leads.add_lead(biz, email_content, "dry_run")
                sent += 1
                continue

            if not biz.get("email"):
                print(f"  GEEN EMAIL: {name}")
                leads.add_lead(biz, email_content, "no_email")
                no_email += 1
                continue

            success = gmail.send_email(
                biz["email"],
                email_content["subject"],
                email_content["body"],
                email_content.get("html"),
            )
            status = "sent" if success else "failed"
            print(f"  {'OK' if success else 'FAIL'} ({biz['email']}): {name}")
            leads.add_lead(biz, email_content, status)

            if success:
                sent += 1
            else:
                failed += 1

        return (
            f"Lead Generator ({mode}) afgerond.\n"
            f"  Gezocht  : {business_type!r} in {location!r}\n"
            f"  Gevonden : {len(businesses)}\n"
            f"  Verwerkt : {sent}  |  Mislukt: {failed}  "
            f"|  Geen email: {no_email}  |  Overgeslagen: {skipped}\n"
            f"  Resultaten opgeslagen in: {leads_csv}"
        )
