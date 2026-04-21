# ErgoPilot Final Demo Video Plan

## Goal

Produce a professional final demo video (10+ minutes) that:

- Walks through user scenarios from the primary persona viewpoint
- Shows final implementation (no prototypes/Figma)
- Explains high-level technical details clearly
- Discusses real challenges and how they were resolved

Recommended total length: **~12 minutes**.

## Team Split (Fair 3-Way)

- **You:** ~4:00 (all recording-screen content only)
- **Guy 1:** ~4:00
- **Guy 2:** ~4:00
- **Total:** ~12:00

Rationale: you own the recording feature end-to-end (most camera/CV-sensitive section), while Guy 1 and Guy 2 split intro, dashboard, architecture, and challenge narratives.

## Primary Persona Framing

Use the primary persona as a **frontline worker** who wants fast posture guidance during real tasks without uploading sensitive video data to the cloud.

## Timestamped Run of Show

### 0:00-0:45 — Guy 1 — Intro + Persona + Problem

- Introduce ErgoPilot and the primary persona context
- State user pain point: posture risk is hard to monitor in real time
- Explain value proposition: live feedback + trend tracking + privacy-first approach
- Explicitly state this demo shows the implemented system, not a prototype

### 0:45-2:15 — Guy 1 — User Flow Part 1 (Entry + Auth)

- Show `landing.html` to set product context
- Show account creation/sign-in flow (`signup.html`, `signin.html`)
- Mention single-account-per-device lock behavior and why it prevents data mixing
- Confirm successful navigation into dashboard

### 2:15-6:15 — You — User Flow Part 2 (Recording Screen, Full Ownership)

Show full recording workflow on `index.html`:

- Start camera and enter full-body framing
- Prestart baseline countdown (20 seconds)
- Tap overlay to extend countdown (+20 seconds) as needed
- Show transition from setup to active analysis
- Demonstrate live metrics:
  - RULA
  - REBA
  - RWL
  - NIOSH ratio
- Show risk state changes (`safe`, `warning`, `danger`)
- Demonstrate risk clip creation and "Recent Risk Clips" list
- Demonstrate local clip controls:
  - Refresh list
  - Delete a clip
  - Clear all clip-related data
- Mention configurable clip retention ("Max Clips Kept")

Technical points to narrate while showing the UI:

- Raw frames are analyzed in-browser with MediaPipe Pose
- Privacy clip stream masks/blurs the worker region and overlays skeleton landmarks
- Clips are stored in browser IndexedDB (`risk_clips`) instead of cloud storage
- Backend receives landmarks + derived scores, not raw video frames

### 6:15-8:15 — Guy 2 — User Flow Part 3 (Dashboard + Insights)

- Show dashboard (`dashboard.html`) time range selector (7/30/90 days)
- Show average RULA and REBA trends
- Show "Areas for Improvement" summary behavior
  - Mention local LLM (Ollama) path when available
  - Mention fallback summary when LLM unavailable
- Show recent risk clips and explain metadata (risk level, scores, timestamp)
- Demonstrate deleting a clip and mention linked backend cleanup impact on averages

### 8:15-10:15 — Guy 2 — High-Level Technical Details

Architecture overview:

- **Frontend**
  - Static pages (`landing`, `signin`, `signup`, `index`, `dashboard`)
  - `app.js` handles live camera inference, countdown, clip capture, retention
  - `auth.js` handles token/session/account-lock helpers
- **Backend**
  - FastAPI app (`backend/app/main.py`)
  - Endpoints for auth, calibration, analysis, events, summaries, averages
- **Scoring Engine**
  - `ergonomics.py` computes proxy RULA/REBA/NIOSH using landmark geometry
  - Calibration profile adjusts baseline trunk tilt per worker
- **Persistence**
  - SQLite tables for users, risk events, posture samples (`storage.py`)
  - IndexedDB for local risk clips
- **Security/Auth**
  - JWT bearer auth (`auth.py`)
  - account lock logic on browser side to prevent cross-account mixing

### 10:15-12:00 — Guy 1 — Challenges, Resolutions, and Close

Challenge and resolution examples:

1. **Privacy vs useful review clips**
   - Challenge: need context for coaching without exposing worker identity
   - Resolution: anonymized clip pipeline (worker masked/blurred + skeleton overlay)

2. **Baseline inconsistency and noisy early scoring**
   - Challenge: immediate scoring can be unstable before user settles posture
   - Resolution: prestart baseline capture countdown + calibration endpoint

3. **Data consistency when users delete clips**
   - Challenge: local clip deletion can leave backend metrics stale
   - Resolution: linked deletion of local clip + backend event/sample data

4. **CV reliability validation**
   - Challenge: need quantitative evidence beyond visual inspection
   - Resolution: COCO benchmark script (`benchmark_pose_coco.py`) with PCK and normalized error metrics

Close:

- Reaffirm full software lifecycle: idea -> implementation -> validation -> deliverable
- Mention future improvements (production-grade scoring, broader validation, deployment hardening)

## Rubric Coverage Mapping

### Final Project Demo - User Scenarios (50 pts)

Covered by:

- Persona-framed walkthrough from landing/auth -> recording -> dashboard
- Live use of major features across both user-facing core screens

### Final Project Demo - High Level Technical Details (50 pts)

Covered by:

- Dedicated architecture segment with concrete implementation details
- Demonstration uses final running app, not mockups/prototyping tools

### Final Project Demo - Challenges and Resolutions (50 pts)

Covered by:

- 4 explicit technical challenges with implementation-level fixes

### Overall Effectiveness and Professionalism (50 pts)

Covered by:

- Planned 12-minute script with clean handoffs
- Balanced speaker participation and polished narrative arc

## Speaker Handoff Script (Short)

- **Guy 1 -> You:** "Now that we've shown how users enter the platform, [Your Name] will demonstrate the live recording and posture analysis workflow."
- **You -> Guy 2:** "With risk clips and live metrics captured, [Guy 2] will show how those results appear in the dashboard and how teams review trends."
- **Guy 2 -> Guy 1:** "Now [Guy 1] will close with the core technical challenges we faced and how we resolved them."
