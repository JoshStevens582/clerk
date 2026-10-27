from clerk.schemas.agent import ClerkRunResult, ProposalKind

SAMPLE_MESSAGES: dict[str, str] = {
    "after_hours_thursday": "Do you have anything on Thursday?",
    "booking_thursday_10": "Please book me for Thursday at 10:00.",
    "tax_return_email": "Email me what you need for the tax return.",
    "leave_hr_email": "Email HR that I want those 5 days carry-over leave.",
}


def result_for_sample(sample_id: str) -> ClerkRunResult | None:
    if sample_id == "after_hours_thursday":
        return ClerkRunResult(kind=ProposalKind.AUTO_REPLY, auto_reply_id="after_hours_ack")
    if sample_id == "booking_thursday_10":
        return ClerkRunResult(
            kind=ProposalKind.BOOKING_DRAFT,
            draft_subject="Booking request — Thursday 10:00",
            draft_body=(
                "Patient requested Thursday at 10:00. "
                "Standard session fee R650 per fees page. Time not held until approved."
            ),
            cited_pages=["fees.md"],
            claimed_amounts=["R650"],
            booking_day="Thursday",
            booking_time="10:00",
        )
    if sample_id == "tax_return_email":
        return ClerkRunResult(
            kind=ProposalKind.EMAIL_DRAFT,
            draft_subject="Documents needed for your tax return",
            draft_body=(
                "Please send the documents listed on our tax return page: "
                "IRP5/IT3(a), bank statements, medical aid certificate, "
                "retirement annuity certificates, donation receipts, rental schedule, "
                "and travel logbook if applicable."
            ),
            cited_pages=["tax-return-documents.md"],
        )
    if sample_id == "leave_hr_email":
        return ClerkRunResult(
            kind=ProposalKind.EMAIL_DRAFT,
            draft_subject="Leave carry-over request",
            draft_body=(
                "Please record my request to use 5 days carry-over leave "
                "as set out in the leave policy."
            ),
            cited_pages=["leave-policy.md"],
            claimed_day_counts=["5 days"],
        )
    return None
