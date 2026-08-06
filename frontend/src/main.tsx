// One family, both axes. `wdth.css` carries the width axis (62–125%) as well
// as the weight axis, which is what lets display type be drawn condensed and
// captions be drawn wide without shipping a second typeface.
import "@fontsource-variable/archivo/wdth.css";
import "./styles.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth";
import { ToastProvider } from "./components/ui";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      {/* outside AuthProvider so a toast survives sign-out and route changes */}
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
);
