import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { translations, type Language } from './translations'

const STORAGE_KEY = 'image-studio.language'

function storedLanguage(): Language {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'en' ? 'en' : 'es'
  } catch {
    return 'es'
  }
}

export function saveLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // Sin almacenamiento (modo privado): el idioma vale solo para esta sesión.
  }
}

i18n.use(initReactI18next).init({
  resources: translations,
  lng: storedLanguage(),
  fallbackLng: 'es',
  interpolation: { escapeValue: false },
})

export default i18n
