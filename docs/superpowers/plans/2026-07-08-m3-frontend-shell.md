# M3 — Frontend Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the React (TypeScript) single-page-app shell — Vite build, Tailwind with brand color tokens, a typed API client with CSRF handling, a route guard, and a working login → dashboard flow against the M2 Flask auth API.

**Architecture:** A Vite + React + TS app under `frontend/`. A small typed `fetch` wrapper (`api/client.ts`) sends `credentials: 'include'` and injects the CSRF token on mutations. TanStack Query holds server state (`useMe` over `/api/auth/me`); `RequireAuth` redirects unauthenticated users to `/login`. In dev, Vite proxies `/api` to Flask on :5000 (same-origin, cookies just work). The React login page consumes the M2 endpoints.

**Tech Stack:** Vite, React 19, TypeScript, React Router 7, TanStack Query 5, Tailwind CSS 4 (`@tailwindcss/vite`), Vitest. Backend from M1/M2.

## Global Constraints

- Inherits all prior constraints. **Styling: brand color tokens only** (navy `#0B2A4A`, blue `#2E6DF0`, sky `#8FB2FF`) — **no logo, no favicon, no special typeface** (system sans).
- **Same-origin in dev via Vite proxy** (`/api` → `http://localhost:5000`); never hardcode the backend origin in app code.
- All API calls go through `api/client.ts`: `credentials: 'include'`, `X-CSRFToken` header on non-GET.
- **Windows/`&`-path note:** the repo path contains `&`, which breaks `npm run <script>` (npm's default cmd shell). Run Vite via the binary directly (`node_modules/.bin/vite`) or set `npm_config_script_shell` to Git Bash. `npm install` itself is unaffected.

---

### Task 1: Vite + React + TS scaffold, Tailwind brand tokens, dev proxy

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/.gitignore`
- Create: `frontend/src/index.css`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx` (temporary placeholder, replaced in Task 3)

**Interfaces:**
- Consumes: nothing (frontend root).
- Produces: a buildable Vite app; `npm run dev` serves on :5173 with `/api` proxied to :5000; `npm run build` type-checks and builds; `npm test` runs Vitest.

- [ ] **Step 1: Write package.json**

`frontend/package.json`:
```json
{
  "name": "capex-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "typecheck": "tsc"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 2: Write the TypeScript config**

A single `tsconfig.json` (no project references / composite — that path makes `tsc -b` emit `vite.config.js`/`.d.ts`/`.tsbuildinfo` artifacts). One config covers `src` and `vite.config.ts` with `noEmit`.

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals"]
  },
  "include": ["src", "vite.config.ts"]
}
```

- [ ] **Step 3: Write the Vite config (proxy + Vitest)**

`frontend/vite.config.ts`:
```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
  test: {
    environment: 'node',
    globals: true,
  },
})
```

- [ ] **Step 4: Write index.html (no favicon link — color-only branding)**

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CAPEX Tracking — United Uptime Services</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write the Tailwind entry with brand tokens**

`frontend/src/index.css`:
```css
@import "tailwindcss";

@theme {
  --color-brand-navy: #0B2A4A;
  --color-brand-blue: #2E6DF0;
  --color-brand-sky: #8FB2FF;
}
```

- [ ] **Step 6: Write main.tsx and a placeholder App**

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

`frontend/src/App.tsx` (placeholder — replaced in Task 3):
```tsx
export default function App() {
  return <div className="p-6 text-brand-navy">CAPEX shell</div>
}
```

- [ ] **Step 7: Write .gitignore**

`frontend/.gitignore`:
```
node_modules/
dist/
*.local
.env
*.tsbuildinfo
```

- [ ] **Step 8: Install and verify build + dev server**

Run (from `frontend/`, Git Bash):
```bash
npm install
npm run build
```
Expected: `npm run build` completes with no TypeScript errors and writes `dist/`.

Then verify the dev server serves (run Vite via the binary to dodge the `&`-path npm-script issue):
```bash
./node_modules/.bin/vite --port 5173 &
sleep 3
curl -s http://localhost:5173/ | grep -q "CAPEX Tracking" && echo "dev server OK" || echo "FAIL"
kill %1
```
Expected: `dev server OK`.

- [ ] **Step 9: Commit**

```bash
git add frontend/ ':!frontend/node_modules'
git commit -m "feat(frontend): Vite + React + TS scaffold with Tailwind brand tokens and API proxy"
```

---

### Task 2: Typed API client with CSRF handling

**Files:**
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: browser `fetch`.
- Produces:
  - `api<T>(path: string, options?: { method?: string; body?: unknown }): Promise<T>` — prefixes `/api`, sends `credentials: 'include'`, sets `Content-Type` + `X-CSRFToken` on mutations, throws `ApiError` on non-2xx.
  - `class ApiError extends Error { status: number }`.
  - `resetCsrf(): void` — clears the cached CSRF token (call on logout / 401).

- [ ] **Step 1: Write the failing tests**

`frontend/src/api/client.test.ts`:
```ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api, resetCsrf } from './client'

function fakeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'x',
    json: async () => body,
  } as Response
}

beforeEach(() => {
  resetCsrf()
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('GET includes credentials and no CSRF header', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(fakeResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    const data = await api<{ ok: boolean }>('/auth/me')
    expect(data).toEqual({ ok: true })
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/me')
    expect(opts.credentials).toBe('include')
    expect(opts.headers['X-CSRFToken']).toBeUndefined()
  })

  it('POST fetches CSRF token then attaches X-CSRFToken', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(fakeResponse(200, { csrfToken: 'tok123' }))
      .mockResolvedValueOnce(fakeResponse(200, { id: '1' }))
    vi.stubGlobal('fetch', fetchMock)
    await api('/auth/login', { method: 'POST', body: { username: 'a' } })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/csrf')
    const loginOpts = fetchMock.mock.calls[1][1]
    expect(loginOpts.headers['X-CSRFToken']).toBe('tok123')
    expect(loginOpts.headers['Content-Type']).toBe('application/json')
    expect(loginOpts.body).toBe(JSON.stringify({ username: 'a' }))
  })

  it('throws ApiError with server error message on non-ok', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(fakeResponse(401, { error: 'nope' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(api('/auth/me')).rejects.toMatchObject({ status: 401, message: 'nope' })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `./client`.

- [ ] **Step 3: Write the client**

`frontend/src/api/client.ts`:
```ts
let csrfToken: string | null = null

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function resetCsrf(): void {
  csrfToken = null
}

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken
  const res = await fetch('/api/auth/csrf', { credentials: 'include' })
  const data = await res.json()
  csrfToken = data.csrfToken as string
  return csrfToken
}

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = await ensureCsrf()

  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!res.ok) {
    if (res.status === 401) csrfToken = null
    let message = res.statusText
    try {
      const data = await res.json()
      if (data && data.error) message = data.error
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): typed API client with CSRF handling"
```

---

### Task 3: Auth UI — client hooks, route guard, login + dashboard

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/auth/useMe.ts`
- Create: `frontend/src/auth/RequireAuth.tsx`
- Create: `frontend/src/components/ui/Button.tsx`
- Create: `frontend/src/components/ui/Input.tsx`
- Create: `frontend/src/routes/LoginPage.tsx`
- Create: `frontend/src/routes/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx` (replace placeholder with routes)

**Interfaces:**
- Consumes: `api`, `ApiError`, `resetCsrf` (Task 2); TanStack Query; React Router.
- Produces:
  - `CurrentUser` type `{ id, username, name, email, roles: string[] }`.
  - `fetchMe()`, `login(username, password)`, `logout()` in `api/auth.ts`.
  - `useMe()` query hook.
  - `RequireAuth` component (redirects to `/login` when unauthenticated).
  - Routes: `/login` → `LoginPage`; `/` → guarded `DashboardPage`.

- [ ] **Step 1: Write the auth API module**

`frontend/src/api/auth.ts`:
```ts
import { api, resetCsrf } from './client'

export interface CurrentUser {
  id: string
  username: string
  name: string
  email: string
  roles: string[]
}

export function fetchMe(): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/me')
}

export function login(username: string, password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/login', { method: 'POST', body: { username, password } })
}

export async function logout(): Promise<void> {
  await api('/auth/logout', { method: 'POST' })
  resetCsrf()
}
```

- [ ] **Step 2: Write the useMe hook**

`frontend/src/auth/useMe.ts`:
```ts
import { useQuery } from '@tanstack/react-query'
import { fetchMe } from '../api/auth'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    retry: false,
    staleTime: Infinity,
  })
}
```

- [ ] **Step 3: Write the route guard**

`frontend/src/auth/RequireAuth.tsx`:
```tsx
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useMe } from './useMe'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data, isLoading, isError } = useMe()
  if (isLoading) return <div className="p-6 text-sm text-slate-500">Loading…</div>
  if (isError || !data) return <Navigate to="/login" replace />
  return <>{children}</>
}
```

- [ ] **Step 4: Write the UI primitives**

`frontend/src/components/ui/Button.tsx`:
```tsx
import type { ButtonHTMLAttributes } from 'react'

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md bg-brand-blue px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50 ${className}`}
      {...props}
    />
  )
}
```

`frontend/src/components/ui/Input.tsx`:
```tsx
import type { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-blue ${className}`}
      {...props}
    />
  )
}
```

- [ ] **Step 5: Write the login page**

`frontend/src/routes/LoginPage.tsx`:
```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { login } from '../api/auth'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate('/', { replace: true })
    },
  })

  const error =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Login failed.'
        : null

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6 text-center">
          <div className="text-xl font-bold text-brand-navy">United Uptime Services</div>
          <div className="text-sm text-slate-500">CAPEX Tracking</div>
        </div>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); mutation.mutate() }}>
          <div className="space-y-1">
            <label htmlFor="username" className="text-sm font-medium">Username</label>
            <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)}
              autoComplete="username" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">Password</label>
            <Input id="password" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </main>
  )
}
```

- [ ] **Step 6: Write the dashboard page**

`frontend/src/routes/DashboardPage.tsx`:
```tsx
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { logout } from '../api/auth'
import { Button } from '../components/ui/Button'

export default function DashboardPage() {
  const { data: user } = useMe()
  const navigate = useNavigate()
  const qc = useQueryClient()

  async function handleLogout() {
    await logout()
    qc.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b bg-brand-navy px-6 py-3 text-white">
        <div className="font-bold">United Uptime Services · CAPEX Tracking</div>
        <div className="flex items-center gap-3 text-sm">
          <span>{user?.name}</span>
          <Button onClick={handleLogout} className="bg-white/10">Sign out</Button>
        </div>
      </header>
      <main className="p-6">
        <h1 className="mb-2 text-2xl font-semibold text-brand-navy">Dashboard</h1>
        <p className="text-slate-600">Welcome, {user?.name}. Request queues arrive in a later milestone.</p>
      </main>
    </div>
  )
}
```

- [ ] **Step 7: Wire the routes in App.tsx**

`frontend/src/App.tsx` (replace placeholder):
```tsx
import { Routes, Route } from 'react-router-dom'
import LoginPage from './routes/LoginPage'
import DashboardPage from './routes/DashboardPage'
import { RequireAuth } from './auth/RequireAuth'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
    </Routes>
  )
}
```

- [ ] **Step 8: Type-check / build**

Run (from `frontend/`): `npm run build`
Expected: no TypeScript errors; build succeeds.

- [ ] **Step 9: Live end-to-end smoke (backend + frontend + browser)**

Start the backend (from `backend/`, venv active): `flask run` (:5000) — ensure `flask db upgrade` and `python seed.py` have been run.
Start the frontend (from `frontend/`): `./node_modules/.bin/vite --port 5173`.
Then drive a browser (Playwright): navigate to `http://localhost:5173/`.
Expected:
1. Unauthenticated → redirected to `/login` (login card visible: "United Uptime Services / CAPEX Tracking").
2. Fill `admin` / `ChangeMe123!`, submit → lands on Dashboard showing "Welcome, Administrator".
3. Take a screenshot and confirm the navy header renders (brand color) and there is NO logo/favicon.
4. Click "Sign out" → back to `/login`.

- [ ] **Step 10: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): auth UI — login, dashboard, route guard"
```

---

### Task 4: Dev launcher and frontend README

**Files:**
- Create: `frontend/README.md`
- Modify (overwrite): `run-app.bat` (was the obsolete Next.js launcher)

**Interfaces:**
- Consumes: the `backend/` venv and `frontend/` node_modules.
- Produces: a double-clickable launcher that first-run-installs both apps and opens the Flask API (:5000) and the Vite dev server (:5173) in separate windows.

- [ ] **Step 1: Write the frontend README**

`frontend/README.md`:
```markdown
# CAPEX Frontend (React + Vite)

## Setup (Git Bash — repo path contains `&`)

    cd frontend
    npm install

## Run

    npm run dev        # http://localhost:5173  (proxies /api -> http://localhost:5000)

The backend (see ../backend/README.md) must be running on :5000.
Dev login: admin / ChangeMe123!

## Test / build

    npm test
    npm run build
```

- [ ] **Step 2: Overwrite run-app.bat for the Flask + React stack**

`run-app.bat`:
```bat
@echo off
setlocal enableextensions
title CAPEX Tracking (Flask API + React)

rem The repo path contains '&', which breaks npm's default cmd script-shell.
rem Point npm's script-shell at Git Bash so "npm run dev" works.
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
if exist "%GITBASH%" set "npm_config_script_shell=%GITBASH%"

rem --- Backend first-run setup + launch ---
if not exist "%~dp0backend\.venv\" (
  echo Creating Python venv and installing backend deps...
  pushd "%~dp0backend" && python -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && flask db upgrade && python seed.py && popd
)
start "CAPEX API" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate && flask run"

rem --- Frontend first-run setup + launch ---
if not exist "%~dp0frontend\node_modules\" (
  echo Installing frontend deps ^(first run^)...
  pushd "%~dp0frontend" && call npm install && popd
)
start "CAPEX Web" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ================================================================
echo   Backend:  http://localhost:5000/api/health
echo   Frontend: http://localhost:5173   (login: admin / ChangeMe123!)
echo ================================================================
```

- [ ] **Step 3: Commit**

```bash
git add frontend/README.md run-app.bat
git commit -m "chore: dev launcher for Flask + React and frontend README"
```

Note: the launcher opens interactive windows and is not part of the automated test flow; it is verified by the Task 3 live smoke driving the two processes directly.

---

## Self-Review

**Spec coverage (spec §8 frontend, §13 dev experience, §14 M3 slice):**
- Vite + React + TS + Tailwind brand tokens (color only, no logo/favicon/typeface) → Task 1. ✓
- Typed API client with `credentials: 'include'` + CSRF header → Task 2 (tested). ✓
- TanStack Query server state + route guard on `/api/auth/me` → Task 3. ✓
- React Router routes + login page wired to M2 endpoints → Task 3. ✓
- Dev proxy `/api` → :5000 (same-origin) → Task 1 (`vite.config.ts`). ✓
- Launcher replacing `run-app.bat` → Task 4. ✓
- react-hook-form/zod are deferred to M4/M6 (forms get complex there); the 2-field login uses plain state — intentional YAGNI.

**Placeholder scan:** No TBD/TODO. The `App.tsx` placeholder in Task 1 is explicitly replaced in Task 3 Step 7. Every step has full code and expected output. ✓

**Type consistency:** `api`/`ApiError`/`resetCsrf` signatures match between `client.ts`, its test, and `auth.ts`. `CurrentUser` shape matches the M2 `_user_json` (`id, username, name, email, roles`). `useMe` query key `['me']` matches the `setQueryData(['me'], ...)` in LoginPage. Route paths (`/login`, `/`) consistent between `App.tsx`, `RequireAuth`, and the pages. ✓
