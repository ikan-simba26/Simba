import { MotionConfig } from "framer-motion";
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
// The interface face, bundled into the build (index.css, `--font-sans`).
import "@fontsource-variable/atkinson-hyperlegible-next";
import "./index.css";

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
