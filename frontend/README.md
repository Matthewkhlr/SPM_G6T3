# ConnectSphere — Vue frontend

Login, the venue catalogue, and event registration enforce the real acceptance
criteria given for those stories. API calls belong in `src/api/` (`axiosClient.js`
plus one file per microservice); screens still use co-located hardcoded data
until they are wired to the backend.

## Run it

From the repo root:

```
npm run dev:frontend
```

Or from this folder:

```
npm install
npm run dev
```

Demo credentials are shown on the login screen (also in `src/auth/users.data.js`).
Each account logs into a different role's dashboard.

## Folder structure

```
src/
  views/                   Route-level pages (Landing, Login, Dashboard shell)
  features/                One folder per dashboard TAB — mirrors the sidebar 1:1
    dashboard/
      DashboardHome.vue     "Dashboard" tab
    venue-catalogue/
      VenueCatalogue.vue    "Venue Catalogue" tab (Event Coordinator)
      venues.data.js         its hardcoded data, co-located with the component
    browse-events/
      BrowseEvents.vue      "Browse Events" tab (Attendee)
      events.data.js         its hardcoded data + eligibility rule logic
  auth/                    Cross-cutting, not a tab
    users.data.js          Demo account reference shown on the login page
  store/                   Cross-cutting, not a tab — reactive session state
    session.js
  api/                     Thin axios wrappers — not microservices
    axiosClient.js
    userService.js
    eventService.js
    venueService.js
    equipmentService.js
    registrationService.js
    notificationService.js
  firebase.js              Firebase init placeholder
  config/
    roles.js               Which tabs exist per role, and their Dashboard cards
  components/shared/       Used across multiple views/features
    AppLogo.vue
    AnimatedOrb.vue
  router/index.js          Routes + the auth guard on /app
```

**Why this split**: `auth` and `store` aren't under `features/` because they
aren't tied to one tab — every tab depends on the session, and login isn't a
dashboard tab at all. `config/roles.js` is separate from any one feature
because it's the thing that decides *which* feature folders are even reachable
for a given role. If you add a real "Reports" tab later, its component and
data file belong in a new `features/reports/` folder, following the same
pattern — don't add it to `components/shared/`.

## What's implemented against your three stories

**Login**
- Empty email/password blocks submission with inline errors
- Wrong credentials show one generic "Invalid email or password." message
- Correct credentials create a session and route to `/app`
- `/app` is guarded: no session redirects to `/login`. **This is a client-side
  guard, not an HTTP 401** — a real backend must independently reject
  unauthenticated API calls; front-end routing can always be bypassed by
  calling the API directly.
- Logout clears the session and replaces the history entry; the guard re-runs
  on every navigation (including back/forward), so Back after logout bounces
  to `/login` rather than showing the dashboard
- Password input is masked

**Event Coordinator venue catalogue**
- `features/venue-catalogue/` — list + detail panel showing location,
  capacity, facilities, accessibility, supported layouts, operating hours,
  and turnaround time

**Attendee registration**
- `features/browse-events/` — 4 hardcoded events specifically chosen to
  exercise each rule: one registrable normally, one already at capacity, one
  not yet confirmed, one whose registration window hasn't opened yet
- The Register button is disabled with the specific reason shown when a rule
  fails; submitting requires name + email; success shows a confirmation

## What's NOT here

- Refreshing the UI still resets client session state until login is wired to
  `/api/auth/login`
- Only Dashboard, Venue Catalogue, and Browse Events tabs have real behavior;
  every other tab shows "not built yet for this sprint"
- Capacity must also be re-validated on the server at submit time (see
  `event-service`)
- The orb is an original swirling-marble design with a single orbit ring —
  deliberately not shaped like a two-tone capsule or any branded "capture ball"
