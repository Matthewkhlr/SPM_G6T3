// Server timestamps (decisions, clarifications) are stamped in UTC and sent
// without a zone marker, which new Date() would read as local time.
export function formatUtc(value) {
  if (!value) return ''
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`).toLocaleString()
}
