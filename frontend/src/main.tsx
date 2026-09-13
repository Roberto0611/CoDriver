import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import Landing from './Landing.tsx'

import ElevenLabsTest from './ElevenLabsTest.tsx'
import SimView from './SimView.tsx'
import LiveSimView from './LiveSimView.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<App />} />
        <Route path="/elevenlabs" element={<ElevenLabsTest />} />
        <Route path="/sim" element={<SimView />} />
        <Route path="/live" element={<LiveSimView />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
)
