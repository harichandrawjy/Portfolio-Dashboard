# Frontend

React + Vite + Tailwind v4 + Recharts. Dark fintech UI ("Arus").

```sh
npm install
npm run dev     # http://localhost:5173, proxies /api -> localhost:8000
```

The backend must be running (`docker compose up`) for the app to work.

Structure: `src/api/client.ts` is the single typed API surface; pages in
`src/pages`, small components in `src/components`, chart colors
(dataviz-validated against the panel surface) in `src/colors.ts`.
