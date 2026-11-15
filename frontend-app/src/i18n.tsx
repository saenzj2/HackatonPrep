// Language support. English is the default, base and main language; Spanish (Costa Rica, "usted")
// is shown only when the visitor picks it. The choice is remembered in this browser.
//
// UI strings are written in place as English/Spanish pairs: tr("Next", "Siguiente"). Texts that
// come from the API or the data files are already { en, es } objects: pick(text).
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "es";
export interface Bilingual {
  en: string;
  es?: string;
}

const STORAGE_KEY = "terracosmos-lang";

function loadLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "es" ? "es" : "en";
  } catch {
    return "en";
  }
}

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** English/Spanish pair written in place. */
  tr: (en: string, es: string) => string;
  /** A { en, es } text from the API or data files; falls back to English. */
  pick: (text: Bilingual | null | undefined) => string;
  /** Number with the language's decimal mark: 0.91 (en) or 0,91 (es). */
  num: (value: number, digits?: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(loadLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // Storage blocked: the choice lasts for this visit only.
    }
  }, [lang]);

  const locale = lang === "es" ? "es-CR" : "en-US";
  const value: I18n = {
    lang,
    setLang: setLangState,
    tr: (en, es) => (lang === "es" ? es : en),
    pick: (text) => (text ? (lang === "es" && text.es ? text.es : text.en) : ""),
    num: (value, digits = 2) =>
      value.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }),
  };
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside LanguageProvider");
  return value;
}
