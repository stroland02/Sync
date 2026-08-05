import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import './index.css'
import App from '@/App'
import { queryClient } from '@/lib/query-client'
import { initTheme } from '@/lib/theme'

/* index.html already stamped the class before this module loaded, to beat first paint.
   This call is what attaches the "system" listener, so an OS-level change is followed
   without a reload. */
initTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
