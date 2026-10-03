// Event request fields as people read them, in form order. The server keeps
// the matching lists (EventCreate's fields, CHANGEABLE_FIELDS).
export const FIELD_LABELS = {
  eventName: 'Name',
  purpose: 'Purpose',
  description: 'Description',
  category: 'Category',
  proposedStartAt: 'Start',
  proposedEndAt: 'End',
  expectedAttendance: 'Expected attendance',
  venueRequirements: 'Venue requirements',
  accessibilityNeeds: 'Accessibility needs',
  equipmentRequirements: 'Equipment requirements',
  layoutPreference: 'Layout',
  registrationEnabled: 'Registration',
  registrationOpensAt: 'Registration opens',
  registrationClosesAt: 'Registration closes',
  capacity: 'Capacity',
}

export const fieldLabel = (field) => FIELD_LABELS[field] || field

// SPM-106: the fields a change request can propose (GET /events/changeable-fields lists the same).
export const CHANGEABLE_FIELDS = [
  'eventName', 'description', 'purpose', 'category', 'proposedStartAt', 'proposedEndAt',
  'expectedAttendance', 'layoutPreference', 'accessibilityNeeds', 'equipmentRequirements',
]

export const EVENT_CATEGORIES = ['conference', 'workshop', 'networking', 'meeting']

// Same guided list as the venue form; any other layout can still be typed.
export const LAYOUT_TYPES = [
  'Theatre', 'Classroom', 'Boardroom', 'U-Shape', 'Hollow Square',
  'Banquet', 'Cabaret', 'Exhibition', 'Reception / Cocktail', 'Herringbone',
  'Auditorium', 'Workshop / Breakout Pods',
]
