import { useEffect, useState, type ReactNode } from "react";
import { HashRouter, Link, NavLink, Route, Routes, useLocation } from "react-router";
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
        <SiteHeader />
        <main id="main" className="page" tabIndex={-1}>
          <RouteFade>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/field" element={<Field />} />
              <Route path="/plan" element={<Plan />} />
              <Route path="/results" element={<Results />} />
              <Route path="/learn" element={<Learn />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </RouteFade>
        </main>
        <footer className="site-footer">
          Data: NASA POWER, NASA SMAP, OpenLandMap, FAO EcoCrop · <a href="/docs">API docs</a>
        </footer>
      </PlanProvider>
    </HashRouter>
  );
}

/** Sticky brand bar. On phones the links collapse behind a menu button. */
function SiteHeader() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    setOpen(false); // close the menu after navigating
  }, [pathname]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`site-header${scrolled ? " site-header--scrolled" : ""}`}>
      <div className="site-header__inner">
        <Link to="/" className="brand">
          <img src={`${import.meta.env.BASE_URL}logo-mark.png`} alt="" width={70} height={48} />
          <span className="brand__text">
            <span className="brand__name">Terra Cosmos</span>
            <span className="brand__tagline">Earth insights from space</span>
          </span>
        </Link>
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="main-nav"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="nav-toggle__icon" aria-hidden="true" />
          {open ? "Close" : "Menu"}
        </button>
        <nav id="main-nav" className={`nav${open ? " nav--open" : ""}`} aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}

/** Re-mounts on each route so the page fades in (styles.css `.route`; off with reduced motion). */
function RouteFade({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <div key={pathname} className="route">
      {children}
    </div>
  );
}

function NotFound() {
  return (
    <p>
      This page does not exist. <Link to="/">Back to start</Link>
    </p>
  );
}
