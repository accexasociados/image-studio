/**
 * Misma forma que `es`: una clave que falte o sobre en `en` hace fallar `tsc`.
 * Los valores son siempre texto (i18next resuelve plurales con los sufijos `_one` / `_other`).
 */
type TranslationShape<T> = {
  [K in keyof T]: T[K] extends string ? string : TranslationShape<T[K]>
}

const es = {
  common: {
    loading: 'Cargando…',
    retry: 'Reintentar',
    language: 'Idioma',
    spanish: 'Español',
    english: 'Inglés',
  },
  app: {
    title: 'Image Studio',
    subtitle: 'Fotos de impresión 3D con fondo blanco, listas para la tienda e Instagram',
  },
  health: {
    title: 'Estado del sistema',
    api: 'API',
    apiOk: 'Conectada (v{{version}})',
    apiDown: 'Sin conexión con la API',
    pipelineMode: 'Modo de proceso',
    modeReal: 'Real (IA en la GPU)',
    modeStub: 'Simulado (sin IA)',
    gpu: 'GPU',
    gpuValue: '{{name}} · {{vram}} MB',
    gpuUnavailable: 'No disponible: el proceso usará la CPU',
  },
}

const en: TranslationShape<typeof es> = {
  common: {
    loading: 'Loading…',
    retry: 'Retry',
    language: 'Language',
    spanish: 'Spanish',
    english: 'English',
  },
  app: {
    title: 'Image Studio',
    subtitle: '3D print photos on a white background, ready for the store and Instagram',
  },
  health: {
    title: 'System status',
    api: 'API',
    apiOk: 'Connected (v{{version}})',
    apiDown: 'Cannot reach the API',
    pipelineMode: 'Processing mode',
    modeReal: 'Real (AI on the GPU)',
    modeStub: 'Simulated (no AI)',
    gpu: 'GPU',
    gpuValue: '{{name}} · {{vram}} MB',
    gpuUnavailable: 'Not available: processing will use the CPU',
  },
}

export const translations = {
  es: { translation: es },
  en: { translation: en },
}

export type Language = keyof typeof translations
