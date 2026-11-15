import { HashRouter, Link, Route, Routes } from "react-router";
import { Home } from "./pages/Home";

// Hash routes (/app/#/results): the API serves static files only, so a path route
// like /app/results would 404 on reload or when a link is shared.
export function App() {
  return (
    <HashRouter>
      <header className="site-header">
        <Link to="/" className="brand">
          Guardians of the Harvest
        </Link>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="site-footer">
        API: <a href="/docs">/docs</a> · Data: NASA POWER, NASA SMAP, OpenLandMap, FAO EcoCrop
      </footer>
    </HashRouter>
  );
}

function NotFound() {
  return (
    <p>
      This page does not exist. <Link to="/">Back to start</Link>
    </p>
  );
}
