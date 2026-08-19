import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "../public/locales/en/common.json";
import es from "../public/locales/es/common.json";
import fr from "../public/locales/fr/common.json";

const resources = {
  en: { translation: en },
  es: { translation: es },
  fr: { translation: fr },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["cookie", "localStorage", "navigator"],
      lookupCookie: "NEXT_LOCALE",
      lookupLocalStorage: "i18nextLng",
      caches: ["cookie", "localStorage"],
    },
  });

export default i18n;
