from clerk.schemas.agent import AgentProposal, PolicyOutcome, PolicyOutcomeKind, ProposalKind
from clerk.services.pages import PageStore

BOUNDARY_REPLY_ID = "what_clerk_can_answer"


class PolicyService:
    """Only this module may decide auto-send vs queue vs block."""

    def __init__(self, page_store: PageStore) -> None:
        self._pages = page_store

    def apply(self, proposal: AgentProposal) -> PolicyOutcome:
        if proposal.kind == ProposalKind.MISSING_FACT:
            return self._boundary_reply(
                reason="missing_fact",
                staff_message=proposal.missing_fact_message or "More information is required.",
            )

        if proposal.kind == ProposalKind.AUTO_REPLY:
            return self._apply_auto_reply(proposal)

        if proposal.kind in {
            ProposalKind.BOOKING_DRAFT,
            ProposalKind.EMAIL_DRAFT,
            ProposalKind.WHATSAPP_DRAFT,
        }:
            return self._apply_draft(proposal)

        return PolicyOutcome(
            kind=PolicyOutcomeKind.BLOCKED,
            message="Unsupported action.",
            block_reason="unsupported_kind",
        )

    def _apply_auto_reply(self, proposal: AgentProposal) -> PolicyOutcome:
        reply_id = proposal.auto_reply_id
        if not reply_id:
            return PolicyOutcome(
                kind=PolicyOutcomeKind.BLOCKED,
                message="No approved reply id was provided.",
                block_reason="missing_auto_reply_id",
            )
        catalog = self._pages.load_approved_replies()
        reply = catalog.by_id(reply_id)
        if reply is None:
            return PolicyOutcome(
                kind=PolicyOutcomeKind.BLOCKED,
                message=f"Unknown approved reply: {reply_id}",
                block_reason="unknown_auto_reply",
            )
        return PolicyOutcome(
            kind=PolicyOutcomeKind.SENT_AUTO,
            message="Agreed reply sent.",
            auto_reply_text=reply.text,
        )

    def _apply_draft(self, proposal: AgentProposal) -> PolicyOutcome:
        if not proposal.draft_body:
            return self._boundary_reply(
                reason="empty_draft",
                staff_message="Draft body is empty.",
            )
        if not proposal.cited_pages:
            return self._boundary_reply(
                reason="missing_citation",
                staff_message="Draft must cite at least one page.",
            )

        page_bodies: dict[str, str] = {}
        for page_name in proposal.cited_pages:
            try:
                page_bodies[page_name] = self._pages.read_page(page_name)
            except FileNotFoundError:
                return self._boundary_reply(
                    reason="missing_page",
                    staff_message=f"Cited page not found: {page_name}",
                )

        for amount in proposal.claimed_amounts:
            if not any(amount in body for body in page_bodies.values()):
                return self._boundary_reply(
                    reason="invented_price",
                    staff_message=f"Price {amount} is not on the cited pages.",
                )

        for day_count in proposal.claimed_day_counts:
            if not any(day_count in body for body in page_bodies.values()):
                return self._boundary_reply(
                    reason="invented_leave_days",
                    staff_message=f"Leave amount {day_count} is not on the cited pages.",
                )

        if proposal.kind == ProposalKind.WHATSAPP_DRAFT:
            label = "Nothing has been sent yet. Press Approve."
        else:
            label = "Nothing has been sent yet. Press Approve and send."
        return PolicyOutcome(
            kind=PolicyOutcomeKind.QUEUED,
            message=label,
            draft_subject=proposal.draft_subject,
            draft_body=proposal.draft_body,
            cited_pages=list(proposal.cited_pages),
            slot_held=False,
        )

    def _boundary_reply(self, *, reason: str, staff_message: str) -> PolicyOutcome:
        """Tell the client the exact stored limit. Do not invent an answer."""
        reply = self._pages.load_approved_replies().by_id(BOUNDARY_REPLY_ID)
        if reply is None:
            return PolicyOutcome(
                kind=PolicyOutcomeKind.BLOCKED,
                message=staff_message,
                block_reason=reason,
            )
        return PolicyOutcome(
            kind=PolicyOutcomeKind.SENT_AUTO,
            message=staff_message,
            auto_reply_text=reply.text,
            block_reason=reason,
        )
