import type { components } from './schema'

export type Health = components['schemas']['Health']
export type Batch = components['schemas']['Batch']
export type ProcessOptions = components['schemas']['ProcessOptions']
export type Preset = NonNullable<ProcessOptions['presets']>[number]
export type AppSettingsPublic = components['schemas']['AppSettingsPublic']
export type ImageItem = components['schemas']['ImageItem']

const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new ApiError(response.status, await response.text())
  }
  return (await response.json()) as T
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, await response.text())
  return (await response.json()) as T
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, await response.text())
  return (await response.json()) as T
}

export function apiUpload<T>(path: string, files: File[], onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${API_BASE}${path}`)
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    request.onerror = () => reject(new ApiError(0, 'Network error'))
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new ApiError(request.status, request.responseText))
        return
      }
      resolve(JSON.parse(request.responseText) as T)
    }
    const form = new FormData()
    files.forEach((file) => form.append('files', file, file.name))
    request.send(form)
  })
}
