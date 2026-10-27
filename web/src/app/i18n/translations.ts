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
    enableDarkTheme: 'Activar tema oscuro',
    enableLightTheme: 'Activar tema claro',
  },
  app: {
    title: 'Image Studio',
    subtitle: 'Fotos de impresión 3D con fondo blanco, listas para la tienda e Instagram',
    workspace: 'Espacio de producción visual',
  },
  batches: {
    eyebrow: 'Producción',
    title: 'Lotes de imágenes',
    description: 'Organiza, procesa y revisa las fotos de producto antes de publicarlas.',
    create: 'Crear lote',
    createComingSoon: 'Disponible en el siguiente paso',
    recent: 'Lotes recientes',
    count_one: '{{count}} lote',
    count_other: '{{count}} lotes',
    emptyTitle: 'Todavía no hay lotes',
    emptyDescription: 'Crea tu primer lote para empezar a transformar fotos de piezas.',
    loadError: 'No pudimos cargar los lotes.',
    total: 'Total',
    ready: 'Listas',
    review: 'Revisar',
    failed: 'Fallidas',
    status: {
      draft: 'Borrador',
      queued: 'En cola',
      processing: 'Procesando',
      done: 'Terminado',
      failed: 'Fallido',
      cancelled: 'Cancelado',
    },
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
    enableDarkTheme: 'Enable dark theme',
    enableLightTheme: 'Enable light theme',
  },
  app: {
    title: 'Image Studio',
    subtitle: '3D print photos on a white background, ready for the store and Instagram',
    workspace: 'Visual production workspace',
  },
  batches: {
    eyebrow: 'Production',
    title: 'Image batches',
    description: 'Organize, process, and review product photos before publishing them.',
    create: 'Create batch',
    createComingSoon: 'Available in the next step',
    recent: 'Recent batches',
    count_one: '{{count}} batch',
    count_other: '{{count}} batches',
    emptyTitle: 'No batches yet',
    emptyDescription: 'Create your first batch to start transforming your product photos.',
    loadError: 'We could not load the batches.',
    total: 'Total',
    ready: 'Ready',
    review: 'Review',
    failed: 'Failed',
    status: {
      draft: 'Draft',
      queued: 'Queued',
      processing: 'Processing',
      done: 'Completed',
      failed: 'Failed',
      cancelled: 'Cancelled',
    },
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
