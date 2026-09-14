# CoDrive (HackMTY)

<p align="center">
  <img src="frontend/public/navie.png" alt="CoDrive Navie Logo" width="150"/>
</p>

<p align="center">
  <strong>Advanced logistics and smart routing simulator</strong>
  <br>
  Optimizing delivery decisions and real-time dispatching against unexpected events.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite"/>
  <img src="https://img.shields.io/badge/ElevenLabs-000000?style=for-the-badge&logo=elevenlabs&logoColor=white" alt="ElevenLabs"/>
</p>

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Problem & Solution](#problem--solution)
- [Technical Architecture](#technical-architecture)
- [Tech Stack](#tech-stack)
- [Key Features](#key-features)
- [Use Cases](#use-cases)
- [Team](#team)

---

## Executive Summary

**CoDrive** is a logistics simulation platform that allows modeling delivery shifts, evaluating courier constraints, and reacting to live incidents (shocks).

- **Dual Modality:** Historical Simulator (`/sim`) to analyze past courier shifts, and Live Simulator (`/live`) for real-time dispatch control.
- **Multilingual AI Narrator (Navie):** Recounts key decisions using ElevenLabs, dynamically supporting English, Spanish, and Hindi.
- **Physics and Hard Rules:** The engine evaluates vehicle capacity, fatigue, night risk zones, and extreme temperatures before accepting orders.
- **Random Events (Shocks):** Injects contingencies such as the closing of the Constitución bridge, demand surges, and restaurant delays.

---

## Problem & Solution

### The Problem
Delivery platforms face an unpredictable environment: traffic, extreme weather, and the courier's physical or safety limits hinder efficiency. Traditional dispatching systems often send orders ignoring if the package fits in the vehicle, or if the courier has exceeded their maximum safe driving time under the sun.

### Our Solution
An interactive environment and decision engine that:
- Anticipates physical (full vehicles) and human (mandatory breaks, extreme heat) constraints.
- Dynamically visualizes routes and decisions on high-performance maps.
- Allows testing how the system reacts to macro events through a clean, gamified interface.
- Gives a voice to these decisions through AI (Navie) to naturally audit why an order is rejected or accepted in real-time.

---

## Technical Architecture

CoDrive consists of a Python analytical engine coupled with an ultra-fast reactive frontend, communicating through asynchronous APIs and powered by cached speech synthesis technology.

### Implemented Components

#### 1. **Backend Engine (Python + FastAPI)**
- **Dispatch Rules:** Algorithms that calculate constraints, financial compensations, and the viability of each order.
- **Simulation Generation:** Recreates historical routes, coordinates, and events from local databases.
- **TTS Caching:** Intermediate storage layer for ElevenLabs that reduces latency to 0 ms for previously generated responses, ideal for offline pitches.

#### 2. **Navie AI Narrator**
- **Multilingual TTS:** Integration with ElevenLabs' Multilingual v2 models.
- **Narration Logic:** Navie AI prioritizes important messages (rejections due to time/weight limits) and skips trivial events (low-profit rejections) to avoid overwhelming the user, automatically translating into the selected language.

#### 3. **SPA Frontend (React 19)**
- **Geospatial Rendering:** MapLibre GL JS renders routes, topological layers, and courier states at a fluid +60FPS.
- **Simulation Controls:** Interactive video-player-like timeline with playback capabilities at multiple speeds (1x - 300x).

### Data Flow
```
User → Frontend (React + Vite)
            ↓ (Events / Timeline Controls)
       FastAPI Backend (Python Engine)
            ↓ (Validates hard rules and routes)
       ElevenLabs (Synthesis) → Local Cache
            ↓ 
    MapLibre GL (Visual Render) and HTML5 Audio
```

---

## Tech Stack

### Frontend Stack
- **React 19 & TypeScript:** Strict typing and modern reactive rendering.
- **Vite:** Ultra-fast build tool for instant HMR.
- **MapLibre GL JS:** Vector map rendering via WebGL.
- **Vanilla CSS (Glassmorphism):** Fluid styling without heavy frameworks, featuring dynamic animations and glass components.

### Backend & AI Stack
- **Python (FastAPI):** Asynchronous and efficient APIs.
- **ElevenLabs API:** Photorealistic AI voices.
- **Uvicorn:** ASGI server for Python.

---

## Key Features

### Interactive Simulator (`/sim`)
Control the timeline of a courier's full shift. Observe every decision made minute-by-minute, with the timeline revealing the location of restaurants and customers.

### Live Dispatch (`/live`)
Real-time mode where you can trigger contingencies ("Shocks") to test system resilience:
- **Constitución Closure:** Simulates severe traffic and re-routing.
- **Trigger Surge:** Suddenly increases order volume and pricing.
- **Delay:** Applies random delays at restaurants.

### Multilingual Navie Narration
The voice button (Navie) includes a modern dropdown menu for languages. By choosing between 🇲🇽 Spanish, 🇺🇸 English, or 🇮🇳 Hindi, the engine translates justifications and synthesizes them using the correct language and accent without reloading the app.

---

## Use Cases

**Scenario: Heat Wave & Full Vehicle (Sim Mode)**
1. The user plays back a motorcycle shift at noon during a massive heat wave.
2. After 90 continuous minutes, the interface marks new orders in red (Rejected).
3. Navie explains in English: *"Skip. Heat rule. 90 minutes riding in this heat is the limit"*.
4. After the break, a massive order is denied and Navie steps in again: *"Skip. That order won't fit on your motorbike"*, guaranteeing ethical and safe decisions.

---

## Team

| Role | Name | Contribution | LinkedIn |
|-----|--------|--------------|----------|
| **Full Stack Developer** | Roberto Ochoa Cuevas | Engine Architecture, Simulation Logic, Dispatch Rules (Python), UI/UX Design | [LinkedIn](https://www.linkedin.com/in/roberto-ochoa-cuevas-9082a129b) |
| **Full Stack Developer** | Aldo Karim Garcia Zapata | ElevenLabs Integration, React/Vite Frontend, MapLibre Geospatial Rendering, AI Agent, UI/UX Design | [LinkedIn](https://www.linkedin.com/in/aldo-karim-2178072b7) |
| **Full Stack Developer** | Juan Pablo Fernandez | Live Dispatch (`/live`), Minute-by-Minute Engine Clock, Shocks & Counterfactual, Voice & Decision Explanations, Gemini Status, CI & Quality Gates, Results Integrity | [LinkedIn](https://www.linkedin.com/in/jpfdzc/) |
| **Frontend Developer** | Eli Celaya Montalvo | Navie Character & Playground, Landing Page, Live Events Menu, Decision Notifications, UI Updates | [GitHub](https://github.com/eli-cm) |

**Contributions: Juan Pablo Fernandez**

- **Live Dispatch (`/live`):**
  - Greedy and Navie run side by side on the same fresh offer stream.
  - Backend: live session, `/live` API and router hardening.
  - Frontend: the page, snapshot accumulator and shock banner.
  - Shift lengths: 2 h, 8 h and 8.5 h.
- **Engine clock:** `reloj.Turno` steps a shift one minute at a time. Recorded and live runs share it with identical results.
- **Mid-shift disruptions:** road closure, surge and restaurant delay, applied to both agents at the same minute. Map highlights clean up in any order.
- **Live counterfactual:** at the end of a live shift, it re-simulates that exact shift (seed, shocks, strategy) once for each order Navie skipped for money.
- **Official event log for live runs:** the live JSONL uses the Courier schema and passes `validate_format`.
- **Voice and explanations:**
  - ElevenLabs TTS/STT routes (`/api/voice`).
  - Live narration of safety blocks and shock reactions, with repeats suppressed.
  - Decision explanations and decision toasts.
- **Gemini status and end-of-shift counterfactual on `/sim`:** strategy-thread lifecycle fixes and TigerData schema init fixes.
- **CI and quality gates:**
  - GitHub Actions with one job per check (ruff, mypy, pytest, Vitest, prettier, 500-line limit, contract codegen).
  - Engine golden and ratchet tests.
  - Pinned dependencies.
  - The frontend split and UI restyle.
- **Results integrity:**
  - Named tuning and reporting seed sets.
  - Honest Oracle wording.
  - Back-by time computed from the shift config.
  - README "Results" and "What we cut" sections.
- **Integration:** rebased the 8.5 h shift / probe-pack requirements onto the live demo engine.

**Contributions: Eli Celaya Montalvo**

- **Navie character:** the animated compass mascot (body, eyes and needle assets, happy and error states) and the Navie playground.
- **Landing page:** the landing page and its pixel-canvas background.
- **Live Events menu:** the Events dropdown on `/live` for triggering road closure, surge and restaurant delay.
- **Decision notifications:** restyled the accepted/blocked decision toasts.
- **UI updates:** panel, live and toast styling, and design tokens.

---

<p align="center">
  <strong>Developed by the CoDrive Team</strong>
  <br>
  <sub>HackMTY 2026</sub>
</p>
