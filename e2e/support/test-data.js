import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

function parseCredentialFile(filename) {
  const source = fs.readFileSync(path.join(ROOT, 'Test Data', filename), 'utf8')
  const records = []
  let current = null

  for (const rawLine of source.split(/\r?\n/)) {
    const line = rawLine.trim()
    const section = line.match(/^\[([^\]]+)\]$/)
    if (section) {
      current = { id: section[1] }
      records.push(current)
      continue
    }
    if (!current || !line.includes(':')) continue

    const separator = line.indexOf(':')
    const key = line.slice(0, separator).trim().toLowerCase()
    const value = line.slice(separator + 1).trim()
    const property = {
      email: 'email',
      password: 'password',
      'display name': 'displayName',
      'role label': 'roleLabel',
    }[key]
    if (property) current[property] = value
  }

  return records
}

export const validCredentials = parseCredentialFile('credentials-valid.txt')
export const invalidCredentials = parseCredentialFile('credentials-invalid.txt')

export function account(id) {
  const found = validCredentials.find((record) => record.id === id)
  if (!found) throw new Error(`No valid test credential named ${id}`)
  return found
}

export const expectedTabs = {
  'EO-01': ['Dashboard', 'My Events', 'New Request', 'Drafts', 'Notifications', 'Profile'],
  'EO-02': ['Dashboard', 'My Events', 'New Request', 'Drafts', 'Notifications', 'Profile'],
  'EO-03': ['Dashboard', 'My Events', 'New Request', 'Drafts', 'Notifications', 'Profile'],
  'EO-04': ['Dashboard', 'My Events', 'New Request', 'Drafts', 'Notifications', 'Profile'],
  'EC-01': [
    'Dashboard',
    'Assigned Events',
    'Review Queue',
    'Venue Catalogue',
    'Venue Requests',
    'Reports',
    'Profile',
  ],
  'EC-02': [
    'Dashboard',
    'Assigned Events',
    'Review Queue',
    'Venue Catalogue',
    'Venue Requests',
    'Reports',
    'Profile',
  ],
  'VS-01': [
    'Dashboard',
    'Venue Calendar',
    'Booking Requests',
    'Unavailability',
    'Venue Catalogue',
    'Profile',
  ],
  'VS-02': [
    'Dashboard',
    'Venue Calendar',
    'Booking Requests',
    'Unavailability',
    'Venue Catalogue',
    'Profile',
  ],
  'TS-01': [
    'Dashboard',
    'Upcoming Events',
    'Equipment Catalogue',
    'Reservations',
    'My Assignments',
    'Maintenance Status',
    'Profile',
  ],
  'TS-02': [
    'Dashboard',
    'Upcoming Events',
    'Equipment Catalogue',
    'Reservations',
    'My Assignments',
    'Maintenance Status',
    'Profile',
  ],
  'ATT-01': ['Dashboard', 'Browse Events', 'My Registrations', 'Waiting List', 'Profile'],
  'ATT-02': ['Dashboard', 'Browse Events', 'My Registrations', 'Waiting List', 'Profile'],
}
