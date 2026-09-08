// Hardcoded demo accounts. A real build would check these against a backend,
// hash passwords, and issue a real session token — this is a front-end-only stand-in.
export const users = [
  { username: 'organiser@connectsphere.com', password: 'organiser123', role: 'organiser', name: 'Alice Tan' },
  { username: 'coordinator@connectsphere.com', password: 'coord123', role: 'coordinator', name: 'Ben Lee' },
  { username: 'venue@connectsphere.com', password: 'venue123', role: 'venue', name: 'Vinod Kumar' },
  { username: 'tech@connectsphere.com', password: 'tech123', role: 'techsupport', name: 'Tia Ho' },
  { username: 'attendee@connectsphere.com', password: 'attend123', role: 'attendee', name: 'Amy Wong' }
]

export function findUser(username, password) {
  return users.find(u => u.username === username && u.password === password) || null
}
