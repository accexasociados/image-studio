import { useState, type MouseEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiUpload,
  type SceneBackground,
  type SceneSettings,
  type SceneStyle,
} from '@/shared/api/client'

const SCENE_STYLES: SceneStyle[] = ['white', 'studio', 'pedestal', 'color', 'photo']
const backgroundsKey = ['backgrounds'] as const

const COLOR_FIELDS = [
  ['studio_wall_hex', 'studioWall'],
  ['studio_floor_hex', 'studioFloor'],
  ['brand_hex', 'brandColor'],
  ['pedestal_hex', 'pedestalColor'],
] as const

// Mismos límites que `SceneBackgroundUpdate` en la API.
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const fieldClass =
  'mt-1.5 w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700'
const labelClass = 'text-sm font-medium text-slate-700 dark:text-slate-200'

/** Ajustes > Formatos de salida > Escena: estilo, colores, reflejo y biblioteca de fotos de fondo. */
export function SceneSettingsSection({
  value,
  onChange,
}: {
  value: SceneSettings
  onChange: (value: SceneSettings) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const backgrounds = useQuery({
    queryKey: backgroundsKey,
    queryFn: () => apiGet<SceneBackground[]>('/backgrounds'),
  })
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const update = <K extends keyof SceneSettings>(key: K, next: SceneSettings[K]) =>
    onChange({ ...value, [key]: next })
  const refresh = () => queryClient.invalidateQueries({ queryKey: backgroundsKey })

  const upload = async (file: File) => {
    setUploading(true)
    setError('')
    try {
      const created = await apiUpload<SceneBackground>('/backgrounds', [file], () => undefined, 'file')
      // La API deja el primer fondo como predeterminado; el borrador de esta página debe reflejarlo
      // para que "Guardar cambios" no lo vuelva a dejar vacío.
      if (!value.default_background_id) update('default_background_id', created.id)
      await refresh()
    } catch {
      setError(t('scenes.uploadError'))
    }
    setUploading(false)
  }

  const remove = async (item: SceneBackground) => {
    if (!window.confirm(t('scenes.confirmDelete', { name: item.name }))) return
    setError('')
    try {
      await apiDelete(`/backgrounds/${item.id}`)
      if (value.default_background_id === item.id) update('default_background_id', null)
      await refresh()
    } catch {
      setError(t('scenes.saveError'))
    }
  }

  const patch = async (id: string, body: Partial<SceneBackground>) => {
    setError('')
    try {
      await apiPatch(`/backgrounds/${id}`, body)
      await refresh()
    } catch {
      setError(t('scenes.saveError'))
    }
  }

  const items = backgrounds.data ?? []
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={labelClass}>
          {t('scenes.style')}
          <select
            value={value.style}
            onChange={(event) => update('style', event.target.value as SceneStyle)}
            className={fieldClass}
          >
            {SCENE_STYLES.map((style) => (
              <option key={style} value={style}>
                {t(`scenes.styles.${style}`)}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          {t('scenes.reflection')}
          <input
            type="range"
            min="0"
            max="60"
            value={value.reflection}
            onChange={(event) => update('reflection', Number(event.target.value))}
            className="mt-3 w-full"
          />
          <span className="text-xs text-slate-500">{value.reflection}%</span>
        </label>
        {COLOR_FIELDS.map(([key, label]) => (
          <label key={key} className={labelClass}>
            {t(`scenes.${label}`)}
            <input
              type="color"
              value={value[key]}
              onChange={(event) => update(key, event.target.value.toUpperCase())}
              className="mt-1.5 block h-10 w-full cursor-pointer rounded-lg border border-slate-300 dark:border-slate-700"
            />
          </label>
        ))}
        <label className={labelClass}>
          {t('scenes.defaultBackground')}
          <select
            value={value.default_background_id ?? ''}
            onChange={(event) => update('default_background_id', event.target.value || null)}
            className={fieldClass}
          >
            <option value="">{t('scenes.noBackground')}</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section className="space-y-3 border-t border-slate-200 pt-5 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-slate-950 dark:text-white">{t('scenes.library')}</h3>
            <p className="text-xs text-slate-500">{t('scenes.libraryHelp')}</p>
          </div>
          <label className="cursor-pointer rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">
            {uploading ? t('scenes.uploading') : t('scenes.upload')}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              disabled={uploading}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (file) void upload(file)
              }}
            />
          </label>
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        {items.length === 0 && <p className="text-sm text-slate-500">{t('scenes.empty')}</p>}
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <BackgroundCard key={item.id} item={item} onPatch={patch} onDelete={() => void remove(item)} />
          ))}
        </div>
      </section>
    </div>
  )
}

function BackgroundCard({
  item,
  onPatch,
  onDelete,
}: {
  item: SceneBackground
  onPatch: (id: string, body: Partial<SceneBackground>) => Promise<void>
  onDelete: () => void
}) {
  const { t } = useTranslation()
  const [name, setName] = useState(item.name)
  const [pieceHeight, setPieceHeight] = useState(Math.round(item.piece_height * 100))
  // La foto se muestra con su proporción exacta (sin bandas), así el clic cae donde se ve.
  const mark = (event: MouseEvent<HTMLImageElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    void onPatch(item.id, {
      center_x: clamp((event.clientX - rect.left) / rect.width, 0.1, 0.9),
      floor_y: clamp((event.clientY - rect.top) / rect.height, 0.3, 0.98),
    })
  }
  const commitHeight = () => {
    if (pieceHeight !== Math.round(item.piece_height * 100))
      void onPatch(item.id, { piece_height: pieceHeight / 100 })
  }

  return (
    <article className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
      <div className="mb-2 flex gap-2">
        <input
          aria-label={t('scenes.name')}
          value={name}
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-2 py-1 text-sm font-semibold dark:border-slate-700"
        />
        <button
          type="button"
          disabled={!name.trim() || name === item.name}
          onClick={() => void onPatch(item.id, { name: name.trim() })}
          className="text-xs font-semibold text-indigo-600 disabled:opacity-40"
        >
          {t('scenes.rename')}
        </button>
      </div>
      <p className="mb-1 text-xs text-slate-500">{t('scenes.markSupport')}</p>
      <div className="relative mx-auto w-fit">
        <img
          src={`${item.url}?w=640`}
          alt={item.name}
          onClick={mark}
          className="block max-h-72 max-w-full cursor-crosshair rounded-lg"
        />
        {/* Guía: la pieza se apoya en el punto y crece hacia arriba según el tamaño elegido. */}
        <span
          aria-hidden
          className="pointer-events-none absolute -translate-x-1/2 border-2 border-dashed border-indigo-500 bg-indigo-500/15"
          style={{
            left: `${item.center_x * 100}%`,
            bottom: `${(1 - item.floor_y) * 100}%`,
            height: `${Math.min(pieceHeight, item.floor_y * 100)}%`,
            aspectRatio: '3 / 4',
          }}
        />
        <span
          aria-label={t('scenes.supportPoint')}
          className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-indigo-600 shadow"
          style={{ left: `${item.center_x * 100}%`, top: `${item.floor_y * 100}%` }}
        />
      </div>
      <label className="mt-3 block text-xs font-medium text-slate-700 dark:text-slate-200">
        {t('scenes.pieceHeight')}
        <input
          type="range"
          min="20"
          max="90"
          value={pieceHeight}
          onChange={(event) => setPieceHeight(Number(event.target.value))}
          onPointerUp={commitHeight}
          onKeyUp={commitHeight}
          className="w-full"
        />
        <span className="text-slate-500">{pieceHeight}%</span>
      </label>
      <button type="button" onClick={onDelete} className="mt-2 text-xs font-semibold text-red-600">
        {t('scenes.delete')}
      </button>
    </article>
  )
}
