import '@testing-library/jest-dom/vitest'

/* Node >= 22 ships an EXPERIMENTAL globalThis.localStorage that is undefined
   unless node is started with --localstorage-file, and vitest's jsdom
   environment does not overwrite an existing global. Under a new-enough node
   every test touching localStorage therefore finds node's dead stub instead of
   a working one. jsdom's own implementation is not reachable either, because
   vitest's `window` IS `globalThis`, so the fix is a plain in-memory Storage.
   (Ported from SCORE's test-setup.ts, which hit this on node 26.) */
class MemoryStorage implements Storage {
  private map = new Map<string, string>()
  get length() { return this.map.size }
  clear() { this.map.clear() }
  getItem(key: string) { return this.map.get(key) ?? null }
  key(index: number) { return [...this.map.keys()][index] ?? null }
  removeItem(key: string) { this.map.delete(key) }
  setItem(key: string, value: string) { this.map.set(key, String(value)) }
}

for (const name of ['localStorage', 'sessionStorage'] as const) {
  if (typeof globalThis[name]?.clear !== 'function') {
    Object.defineProperty(globalThis, name, {
      value: new MemoryStorage(),
      configurable: true,
      writable: true,
    })
  }
}
