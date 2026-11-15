import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Brand type (Terracosmos brand book): Montserrat for headings and the logotype, Inter for body
// and data. Self-hosted, Latin subset only, so no request goes to a font CDN.
import "@fontsource/montserrat/latin-600.css";
import "@fontsource/montserrat/latin-700.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing #root");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
