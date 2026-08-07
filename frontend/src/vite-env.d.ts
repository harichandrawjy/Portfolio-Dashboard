/// <reference types="vite/client" />

// No app-specific build-time variables.
//
// There used to be VITE_DEMO_EMAIL / VITE_DEMO_PASSWORD here, compiling a
// shared demo account's credentials into the bundle. The server now mints a
// private demo per visitor (POST /auth/demo), so there is nothing to inline —
// and one fewer thing that has to agree with a value hardcoded in Python.
interface ImportMetaEnv {}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
