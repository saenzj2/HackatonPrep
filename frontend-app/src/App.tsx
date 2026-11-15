import { HashRouter, Link, NavLink, Route, Routes } from "react-router";
import { BackgroundVideo } from "./components/BackgroundVideo";
import { Field } from "./pages/Field";
import { Home } from "./pages/Home";
import { Learn } from "./pages/Learn";
import { Plan } from "./pages/Plan";
import { Results } from "./pages/Results";
import { PlanProvider } from "./state/PlanContext";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/field", label: "My field", end: false },
  { to: "/plan", label: "Crops and priorities", end: false },
  { to: "/results", label: "Rotations", end: false },
  { to: "/learn", label: "Learn", end: false },
];

// Hash routes (/app/#/results): the API serves static files only, so a path route
// like /app/results would 404 on reload or when a link is shared.
export function App() {
  return (
    <HashRouter>
      <PlanProvider>
        <BackgroundVideo />
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <header className="site-header">
          <div className="site-header__inner">
            <Link to="/" className="brand">
              <img src={`${import.meta.env.BASE_URL}logo-96.png`} alt="" width={40} height={40} />
              Terra Cosmos
            </Link>
            <nav className="nav" aria-label="Main">
              {NAV.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </header>
        <main id="main" className="page" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/field" element={<Field />} />
            <Route path="/plan" element={<Plan />} />
            <Route path="/results" element={<Results />} />
            <Route path="/learn" element={<Learn />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="site-footer">
          Data: NASA POWER, NASA SMAP, OpenLandMap, FAO EcoCrop · <a href="/docs">API docs</a>
        </footer>
      </PlanProvider>
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
