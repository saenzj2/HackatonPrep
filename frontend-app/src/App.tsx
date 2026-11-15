import { useEffect, useState, type ReactNode } from "react";
import { HashRouter, Link, NavLink, Route, Routes, useLocation } from "react-router";
import { BackgroundVideo } from "./components/BackgroundVideo";
import { LanguageProvider, useI18n, type Lang } from "./i18n";
import { About } from "./pages/About";
import { Field } from "./pages/Field";
import { Home } from "./pages/Home";
import { Learn } from "./pages/Learn";
import { Plan } from "./pages/Plan";
import { Results } from "./pages/Results";
import { Terms } from "./pages/Terms";
import { PlanProvider } from "./state/PlanContext";

const NAV = [
  { to: "/", en: "Home", es: "Inicio", end: true },
  { to: "/field", en: "My field", es: "Mi campo", end: false },
  { to: "/plan", en: "Crops and priorities", es: "Cultivos y prioridades", end: false },
  { to: "/results", en: "Rotations", es: "Rotaciones", end: false },
  { to: "/learn", en: "Learn", es: "Aprenda", end: false },
];

// Hash routes (/app/#/results): the API serves static files only, so a path route
// like /app/results would 404 on reload or when a link is shared.
export function App() {
  return (
    <LanguageProvider>
      <HashRouter>
        <PlanProvider>
          <Shell />
        </PlanProvider>
      </HashRouter>
    </LanguageProvider>
  );
}

function Shell() {
  const { tr } = useI18n();
  return (
    <>
      <BackgroundVideo />
      <a href="#main" className="skip-link">
        {tr("Skip to content", "Ir al contenido")}
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
            <Route path="/about" element={<About />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </RouteFade>
      </main>
      <footer className="site-footer">
        <p className="site-footer__line">
          {tr("Data", "Datos")}: NASA POWER, NASA SMAP, NASA GPM IMERG, MERRA-2, OpenLandMap, FAO EcoCrop ·{" "}
          <a href="/docs">{tr("API docs", "Documentación de la API")}</a>
        </p>
        <p className="site-footer__line">
          <span className="ai-mark">{tr("AI generated", "Hecho con IA")}</span>{" "}
          {tr("Logo, brand artwork and background videos", "Logo, imagen de marca y videos de fondo")} ·{" "}
          <Link to="/learn" state={{ section: "ai-use" }}>
            {tr("How we used AI", "Cómo usamos IA")}
          </Link>
        </p>
        <p className="site-footer__line">
          <Link to="/about">{tr("About", "Acerca de")}</Link> ·{" "}
          <Link to="/terms">{tr("Terms and Conditions", "Términos y condiciones")}</Link> · Guardians of the Harvest ·
          NASA Space Apps 2026
        </p>
      </footer>
    </>
  );
}

/** EN | ES switch. English is the default; the choice is remembered in this browser. */
function LanguageSwitch() {
  const { lang, setLang, tr } = useI18n();
  const options: { value: Lang; label: string; name: string }[] = [
    { value: "en", label: "EN", name: "English" },
    { value: "es", label: "ES", name: "Español" },
  ];
  return (
    <div className="lang-switch" role="group" aria-label={tr("Language", "Idioma")}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          lang={o.value}
          aria-pressed={lang === o.value}
          aria-label={o.name}
          onClick={() => setLang(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Sticky brand bar. On phones the links collapse behind a menu button. */
function SiteHeader() {
  const { tr } = useI18n();
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
            <span className="brand__tagline">{tr("Earth insights from space", "La Tierra vista desde el espacio")}</span>
          </span>
        </Link>
        <div className="header-tools">
          <LanguageSwitch />
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={open}
            aria-controls="main-nav"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="nav-toggle__icon" aria-hidden="true" />
            {open ? tr("Close", "Cerrar") : tr("Menu", "Menú")}
          </button>
        </div>
        <nav id="main-nav" className={`nav${open ? " nav--open" : ""}`} aria-label={tr("Main", "Principal")}>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {tr(item.en, item.es)}
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
  const { tr } = useI18n();
  return (
    <p>
      {tr("This page does not exist.", "Esta página no existe.")}{" "}
      <Link to="/">{tr("Back to start", "Volver al inicio")}</Link>
    </p>
  );
}
