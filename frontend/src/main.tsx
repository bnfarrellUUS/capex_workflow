import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import App from './App'
import { ApiError } from './api/client'
import { loginPathWithNext } from './auth/loginRedirect'
import './index.css'

// On a 401 anywhere (expired session), bounce to login instead of letting
// pages hang on "Loading…"; ?next= brings the user back here afterwards.
// On a PASSWORD_CHANGE_REQUIRED error (backend locks out other endpoints
// until the forced password change completes), bounce to that page instead.
function handleAuthError(error: unknown) {
  if (!(error instanceof ApiError)) return
  if (error.status === 401 && window.location.pathname !== '/login') {
    window.location.assign(loginPathWithNext(window.location.pathname, window.location.search))
  } else if (error.code === 'PASSWORD_CHANGE_REQUIRED'
      && window.location.pathname !== '/change-password') {
    window.location.assign('/change-password')
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleAuthError }),
  mutationCache: new MutationCache({ onError: handleAuthError }),
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
