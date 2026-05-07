# Axon — AI Chief of Staff Landing Page

Landing page + waitlist backend for **Axon**, an AI Chief of Staff for Belgian freelancers and SMBs.

## Stack

- **Frontend** — Vanilla HTML/CSS/JS, pixel-perfect from design handoff
- **Backend** — Node.js + Express
- **Storage** — `data/waitlist.json` (JSON file, swap for a database when you scale)

## Getting started

```bash
# Install dependencies
npm install

# Start the server
npm start

# Or with auto-restart on file changes (Node 18+)
npm run dev
```

The server runs on **http://localhost:3000** by default.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | Port the server listens on |
| `ADMIN_USER` | `admin` | Admin panel username |
| `ADMIN_PASSWORD` | `axon2026` | Admin panel password — **change this in production** |

Set them in a `.env` file or export before starting:

```bash
ADMIN_PASSWORD=mijn-geheim-wachtwoord npm start
```

## API endpoints

| Method | Route | Auth | Description |
|---|---|---|---|
| `POST` | `/api/waitlist` | — | Register a signup (name + email) |
| `GET` | `/admin` | Basic Auth | Admin panel UI |
| `GET` | `/api/admin/signups` | Basic Auth | All signups as JSON |
| `DELETE` | `/api/admin/signups/:id` | Basic Auth | Remove a signup by ID |

### POST /api/waitlist

```json
{ "name": "Jan Janssens", "email": "jan@bedrijf.be" }
```

Returns `201` on success, `409` if email already registered, `400` on invalid input.

## Admin panel

Visit **http://localhost:3000/admin** and log in with the credentials above.

Features:
- Live stats (total, today, this week)
- Searchable table of all signups
- Delete individual entries
- CSV export

## Project structure

```
axon/
├── public/
│   ├── index.html      # Landing page
│   └── admin.html      # Admin panel (served by Express with auth)
├── data/
│   └── waitlist.json   # Signup data (gitignored)
├── server.js           # Express backend
├── package.json
└── .gitignore
```

## Deploying

Any Node.js host works (Railway, Render, Fly.io, VPS). Make sure to:

1. Set `ADMIN_PASSWORD` as an environment variable
2. Persist the `data/` directory or switch to a proper database
3. Put the app behind HTTPS (most hosts handle this automatically)
