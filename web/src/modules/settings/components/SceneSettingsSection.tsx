import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  apiDelete,
  apiGet,
  apiPatch,
  type SceneBackground,
  type SceneSettings,
  type SceneStyle,
} from '@/shared/api/client'

const STYLES: SceneStyle[] = ['white', 'studio', 'pedestal', 'color', 'photo']

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
    queryKey: ['backgrounds'],
    queryFn: () => apiGet<SceneBackground[]>('/backgrounds'),
  })
  const [uploading, setUploading] = useState(false)
  const update = <K extends keyof SceneSettings>(key: K, next: SceneSettings[K]) =>
    onChange({ ...value, [key]: next })

  const upload = async (file: File, name: string) => {
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file, file.name)
      if (name.trim()) form.append('name', name.trim())
      const response = await fetch('/api/v1/backgrounds', { method: 'POST', body: form })
      if (!response.ok) throw new Error('upload')
      await queryClient.invalidateQueries({ queryKey: ['backgrounds'] })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">
          <span>{t('common.sceneStyle')}</span>
          <select
            className="mt-1.5 w-full rounded-lg border px-3 py-2"
            value={value.style}
            onChange={(e) => update('style', e.target.value as SceneStyle)}
          >
            {STYLES.map((style) => (
              <option key={style} value={style}>
                {t(`common.sceneStyles.${style}`)}
              </option>
            ))}
          </select>
        </label>
        {(
          [
            ['studio_wall_hex', 'studioWall'],
            ['studio_floor_hex', 'studioFloor'],
            ['brand_hex', 'brandColor'],
            ['pedestal_hex', 'pedestalColor'],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="text-sm font-medium">
            <span>{t(`common.${label}`)}</span>
            <input
              type="color"
              className="mt-1.5 block h-10 w-full"
              value={value[key]}
              onChange={(e) => update(key, e.target.value)}
            />
          </label>
        ))}
      </div>
      <label className="block text-sm font-medium">
        <span>{t('common.reflection')}</span>
        <input
          type="range"
          min="0"
          max="60"
          value={value.reflection}
          onChange={(e) => update('reflection', Number(e.target.value))}
          className="mt-2 w-full"
        />
        <span className="text-xs text-slate-500">{value.reflection}%</span>
      </label>
      <label className="block text-sm font-medium">
        <span>{t('common.defaultBackground')}</span>
        <select
          className="mt-1.5 w-full rounded-lg border px-3 py-2"
          value={value.default_background_id ?? ''}
          onChange={(e) => update('default_background_id', e.target.value || null)}
        >
          <option value="">{t('common.backgroundEmpty')}</option>
          {(backgrounds.data ?? []).map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <BackgroundLibrary
        items={backgrounds.data ?? []}
        uploading={uploading}
        onUpload={upload}
        onRefresh={() => void queryClient.invalidateQueries({ queryKey: ['backgrounds'] })}
      />
    </div>
  )
}

function BackgroundLibrary({
  items,
  uploading,
  onUpload,
  onRefresh,
}: {
  items: SceneBackground[]
  uploading: boolean
  onUpload: (file: File, name: string) => Promise<void>
  onRefresh: () => void
}) {
  const { t } = useTranslation()
  const [uploadName, setUploadName] = useState('')
  const patch = async (id: string, body: Record<string, unknown>) => {
    await apiPatch(`/backgrounds/${id}`, body)
    onRefresh()
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{t('common.backgroundLibrary')}</h3>
        <div className="flex items-center gap-2">
          <input
            aria-label={t('common.backgroundName')}
            value={uploadName}
            onChange={(e) => setUploadName(e.target.value)}
            placeholder={t('common.backgroundName')}
            className="w-36 rounded border px-2 py-1 text-sm"
          />
          <label className="cursor-pointer rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">
            {uploading ? t('common.loading') : t('common.uploadBackground')}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              disabled={uploading}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void onUpload(file, uploadName)
              }}
            />
          </label>
        </div>
      </div>
      {items.length === 0 && <p className="text-sm text-slate-500">{t('common.backgroundEmpty')}</p>}
      {items.map((item) => (
        <BackgroundCard key={item.id} item={item} patch={patch} />
      ))}
    </div>
  )
}

function BackgroundCard({
  item,
  patch,
}: {
  item: SceneBackground
  patch: (id: string, body: Record<string, unknown>) => Promise<void>
}) {
  const { t } = useTranslation()
  const [name, setName] = useState(item.name)
  const point = (event: React.MouseEvent<HTMLImageElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    void patch(item.id, {
      center_x: (event.clientX - rect.left) / rect.width,
      floor_y: (event.clientY - rect.top) / rect.height,
    })
  }
  return (
    <article className="rounded-xl border p-3">
      <div className="mb-2 flex gap-2">
        <input
          aria-label={t('common.backgroundName')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="min-w-0 flex-1 rounded border px-2 py-1 text-sm font-semibold"
        />
        <button
          type="button"
          className="text-xs text-indigo-600"
          onClick={() => void patch(item.id, { name })}
        >
          {t('common.rename')}
        </button>
      </div>
      <div className="relative">
        <img
          src={item.url}
          alt={item.name}
          onClick={point}
          className="max-h-64 w-full cursor-crosshair object-contain"
        />
        <span
          className="pointer-events-none absolute"
          style={{ left: `${item.center_x * 100}%`, top: `${item.floor_y * 100}%` }}
        >
          ✚
        </span>
      </div>
      <label className="mt-2 block text-xs">
        {t('common.pieceHeight')}
        <input
          type="range"
          min="20"
          max="90"
          value={Math.round(item.piece_height * 100)}
          onChange={(e) => void patch(item.id, { piece_height: Number(e.target.value) / 100 })}
          className="w-full"
        />
      </label>
      <button
        type="button"
        className="mt-2 text-xs text-red-600"
        onClick={() => {
          if (window.confirm(t('common.confirmDelete')))
            void apiDelete(`/backgrounds/${item.id}`).then(() => window.location.reload())
        }}
      >
        {t('common.delete')}
      </button>
    </article>
  )
}
