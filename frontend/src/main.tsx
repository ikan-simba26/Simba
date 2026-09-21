import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
// The interface face, bundled into the build (index.css, `--font-sans`).
import "@fontsource-variable/atkinson-hyperlegible-next";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
