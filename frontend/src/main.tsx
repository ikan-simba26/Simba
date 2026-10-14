import { MotionConfig } from "framer-motion";
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
// The interface face, bundled into the build (index.css, `--font-sans`).
import "@fontsource-variable/atkinson-hyperlegible-next";
import "./index.css";

// Nothing moves while the window is not focused or not shown (2026-10-14):
// motion nobody is watching is work for nothing, and a window put aside
// should be still when it comes back. The shape's turn reads this
// (`index.css`, `[data-motion="paused"]`).
const stillWhenAway = (): void => {
  const away = document.hidden || !document.hasFocus();
  document.documentElement.dataset.motion = away ? "paused" : "on";
};
window.addEventListener("focus", stillWhenAway);
window.addEventListener("blur", stillWhenAway);
document.addEventListener("visibilitychange", stillWhenAway);
stillWhenAway();

// The colour direction (2026-10-14): A, the default, or B with `?palette=b`.
// Both are in index.css; which one SIMBA keeps is still to be chosen.
if (new URLSearchParams(window.location.search).get("palette") === "b") {
  document.documentElement.dataset.palette = "b";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Framer Motion animates from JavaScript, so the reduced-motion rule in
        index.css never reached it: under that setting the presence mark still
        breathed and circled (frontend/test_calm.py, 2026-10-07). "user" makes
        every motion follow the person's system setting. */}
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </React.StrictMode>,
);
