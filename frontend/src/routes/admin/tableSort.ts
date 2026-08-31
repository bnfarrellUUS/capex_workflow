// Generic client-side sorting for the small admin tables (Divisions, Regions,
// Users). Strings compare naturally ("2" < "10"), booleans put Yes before No
// ascending, and blanks (null/undefined/'') always sort last so a half-filled
// column stays readable in either direction.

export type SortDir = 'asc' | 'desc'
export type SortValue = string | number | boolean | null | undefined

function isBlank(v: SortValue): boolean {
  return v === null || v === undefined || v === ''
}

function compare(a: SortValue, b: SortValue): number {
  if (typeof a === 'string' && typeof b === 'string') {
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
  }
  if (typeof a === 'boolean' && typeof b === 'boolean') {
    return Number(b) - Number(a) // true ("Yes") before false ascending
  }
  return Number(a) - Number(b)
}

export function sortRows<T>(rows: T[], get: (row: T) => SortValue, dir: SortDir): T[] {
  const sign = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = get(a)
    const bv = get(b)
    if (isBlank(av) && isBlank(bv)) return 0
    if (isBlank(av)) return 1
    if (isBlank(bv)) return -1
    return sign * compare(av, bv)
  })
}
