export function kindLabel(kind: string): string {
  switch (kind) {
    case "auto_reply":
      return "Agreed reply";
    case "booking_draft":
      return "Booking";
    case "email_draft":
      return "Email";
    default:
      return kind.replace(/_/g, " ");
  }
}
