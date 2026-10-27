export type InboxMessage = {
  id: string;
  sampleId: string;
  from: string;
  subject: string;
  receivedLabel: string;
  body: string;
  channel: "Email" | "Web form";
};

/** Inbound queue for the connected workspace (Cape Town Physio). */
export const INBOX: InboxMessage[] = [
  {
    id: "in-1",
    sampleId: "after_hours_thursday",
    from: "Sarah Nkomo",
    subject: "Anything on Thursday?",
    receivedLabel: "Today 21:04",
    body: "Do you have anything on Thursday?",
    channel: "Email",
  },
  {
    id: "in-2",
    sampleId: "booking_thursday_10",
    from: "James Patel",
    subject: "Booking request — Thursday morning",
    receivedLabel: "Today 14:18",
    body: "Please book me for Thursday at 10:00.",
    channel: "Web form",
  },
  {
    id: "in-3",
    sampleId: "tax_return_email",
    from: "Lindiwe Mokoena",
    subject: "Tax return — what to send",
    receivedLabel: "Yesterday 16:42",
    body: "Email me what you need for the tax return.",
    channel: "Email",
  },
  {
    id: "in-4",
    sampleId: "leave_hr_email",
    from: "Internal — front desk",
    subject: "Leave carry-over — action needed",
    receivedLabel: "Today 09:15",
    body: "Email HR that I want those 5 days carry-over leave.",
    channel: "Email",
  },
];
