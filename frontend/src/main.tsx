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

// The colour direction: B, the deep teal, by default since 2026-10-15; A, the
// warm palette, with `?palette=a` (index.css).
if (new URLSearchParams(window.location.search).get("palette") === "a") {
  document.documentElement.dataset.palette = "a";
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
