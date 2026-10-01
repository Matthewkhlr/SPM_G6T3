// Plain-language event status labels. Anything not listed shows as stored.
const LABELS = {
  // SPM-71 AC6: a confirmed event whose date, time, attendance, layout,
  // accessibility or equipment changed no longer reads as fully confirmed.
  reconsidering: 'Arrangements being reconsidered',
}

export const eventStatusLabel = (status) => LABELS[status] || String(status || 'Unknown')

// SPM-71 AC7: completed, cancelled and rejected events can't be edited. A draft
// is the organiser's to edit, and a discarded draft is gone.
export const LOCKED_EVENT_STATUSES = ['completed', 'cancelled', 'rejected', 'draft', 'discarded']
