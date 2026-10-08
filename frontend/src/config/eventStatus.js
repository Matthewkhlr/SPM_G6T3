// Plain-language event status labels. Anything not listed shows as stored.
const LABELS = {
  // SPM-71 AC6: a confirmed event whose date, time, attendance, layout,
  // accessibility or equipment changed no longer reads as fully confirmed.
  reconsidering: 'Arrangements being reconsidered',
  // SPM-120: waiting on a Safety Officer.
  'safety review': 'Safety review',
}

export const eventStatusLabel = (status) => LABELS[status] || String(status || 'Unknown')

// SPM-71 AC7: completed, cancelled and rejected events can't be edited. A draft
// is the organiser's to edit, and a discarded draft is gone.
export const LOCKED_EVENT_STATUSES = ['completed', 'cancelled', 'rejected', 'draft', 'discarded']

// SPM-90: registration is set up from planning until the event is confirmed
// ("approved" is planning's older name; a reconsidering event is still confirmed).
export const REGISTRATION_SETUP_STATUSES = [
  'approved', 'planning', 'safety review', 'preparing', 'prepared', 'confirmed', 'reconsidering',
]

// SPM-106: an organiser can request a change while the event is under review,
// approved, in planning, or confirmed. Drafts are edited directly.
export const CHANGE_REQUEST_STATUSES = [
  'under review', 'changes requested', 'approved', 'planning', 'safety review', 'preparing', 'prepared', 'confirmed',
  'reconsidering',
]

// SPM-120: the assigned coordinator submits a planning event for a safety
// review once its venue and equipment are confirmed ("approved" is planning's older name).
export const SAFETY_SUBMITTABLE_STATUSES = ['approved', 'planning']

// An assigned request under review, or waiting on the organiser. Its assigned
// coordinator can raise clarifications on it (SPM-68) or approve it (SPM-69).
export const IN_REVIEW_EVENT_STATUSES = ['under review', 'changes requested']
