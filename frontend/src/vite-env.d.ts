/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Set BOTH to surface a one-click demo sign-in on the login page. Leave
   * either unset and the affordance disappears entirely — a private
   * deployment never ships a shared account it did not ask for.
   *
   * These are build-time values and end up in the client bundle, so only
   * ever point them at a throwaway demo account.
   */
  readonly VITE_DEMO_EMAIL?: string;
  readonly VITE_DEMO_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
