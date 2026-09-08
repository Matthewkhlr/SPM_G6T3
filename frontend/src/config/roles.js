// Hardcoded data — stand-in for what would come from auth + API.
export const roles = {
  organiser: {
    label: 'Event Organiser',
    tabs: ['Dashboard', 'My Events', 'New Request', 'Drafts', 'Notifications', 'Profile'],
    cards: [
      { title: 'Drafts awaiting submission', sub: '3 requests saved but not yet sent' },
      { title: 'Pending coordinator review', sub: '2 requests under review' },
      { title: 'Upcoming confirmed events', sub: '1 event confirmed for next week' },
      { title: 'Recent comments', sub: 'Coordinator asked about AV needs' }
    ]
  },
  coordinator: {
    label: 'Event Coordinator',
    tabs: ['Dashboard', 'Assigned Events', 'Review Queue', 'Venue Catalogue', 'Venue Requests', 'Reports', 'Profile'],
    cards: [
      { title: 'Review queue', sub: '4 requests need clarification' },
      { title: 'Venue requests in progress', sub: '2 awaiting Venue Staff decision' },
      { title: 'Outstanding arrangements', sub: '1 event missing equipment sign-off' },
      { title: 'Recently confirmed', sub: 'Q3 Partner Summit confirmed' }
    ]
  },
  venue: {
    label: 'Venue Staff',
    tabs: ['Dashboard', 'Venue Calendar', 'Booking Requests', 'Unavailability', 'Venue Catalogue', 'Profile'],
    cards: [
      { title: 'Pending booking requests', sub: '3 requests to approve or reject' },
      { title: 'Blocked for maintenance', sub: 'Hall B closed until Friday' },
      { title: 'Turnaround conflicts', sub: 'Tight changeover flagged for Rm 204' },
      { title: "This week's setups", sub: '5 events need setup confirmation' }
    ]
  },
  techsupport: {
    label: 'Technical Support Staff',
    tabs: ['Dashboard', 'Equipment Catalogue', 'Reservations', 'My Assignments', 'Maintenance Status', 'Profile'],
    cards: [
      { title: 'Equipment requests', sub: '2 requests pending review' },
      { title: 'Damaged / under maintenance', sub: '1 projector flagged unavailable' },
      { title: 'Upcoming on-site assignments', sub: "You're assigned to 2 events this week" },
      { title: 'Low availability alert', sub: 'Wireless mics fully booked Thu' }
    ]
  },
  attendee: {
    label: 'Attendee',
    tabs: ['Dashboard', 'Browse Events', 'My Registrations', 'Waiting List', 'Profile'],
    cards: [
      { title: 'Open for registration', sub: '6 upcoming events accepting sign-ups' },
      { title: 'My registrations', sub: '2 confirmed events' },
      { title: 'Waiting list status', sub: '1 event — position 3' },
      { title: 'Closing soon', sub: 'Registration for AI Summit closes in 2 days' }
    ]
  }
}
