import { useMemo, useSyncExternalStore } from 'react';
import type { ApiClient } from '../api/client';

export type Settings = {
  offline_mode?: boolean;
  vision_model?: string;
  vision_use_qa_model?: boolean;
  qa_provider: 'ollama' | 'openai' | 'chatgpt';
  has_chatgpt_connection?: boolean;
  openai_base_url: string;
  has_openai_key: boolean;
  qa_model: string;
  qa_url: string;
  detection_threshold: number;
  show_provenance_rays: boolean;
  show_bounding_boxes: boolean;
  default_node_label: 'source_description' | 'filename';
};
export const defaultSettings: Settings = {
  qa_provider: 'ollama', openai_base_url: 'https://api.openai.com/v1', has_openai_key: false,
  qa_model: 'deepseek-r1:8b', qa_url: 'http://127.0.0.1:11434',
  detection_threshold: 0.7, show_provenance_rays: true,
  show_bounding_boxes: true, default_node_label: 'source_description',
};
export const SETTINGS_KEY = 'evora-settings';
const changeEvent = 'evora-settings-changed';

function storedSettings(): string | null {
  try { return window.localStorage.getItem(SETTINGS_KEY); } catch { return null; }
}
export function parseSettings(raw: string | null): Settings {
  const settings = { ...defaultSettings };
  try {
    const saved = JSON.parse(raw ?? '{}');
    if (!saved || typeof saved !== 'object') return settings;
    if (typeof saved.offline_mode === 'boolean') settings.offline_mode = saved.offline_mode;
    if (typeof saved.vision_model === 'string' && saved.vision_model.length <= 200) settings.vision_model = saved.vision_model;
    if (typeof saved.vision_use_qa_model === 'boolean') settings.vision_use_qa_model = saved.vision_use_qa_model;
    if (saved.qa_provider === 'openai') settings.qa_provider = 'openai';
    if (saved.qa_provider === 'chatgpt') settings.qa_provider = 'chatgpt';
    if (typeof saved.has_chatgpt_connection === 'boolean') settings.has_chatgpt_connection=saved.has_chatgpt_connection;
    if (typeof saved.openai_base_url === 'string' && /^https?:\/\//.test(saved.openai_base_url)) settings.openai_base_url = saved.openai_base_url;
    if (typeof saved.has_openai_key === 'boolean') settings.has_openai_key = saved.has_openai_key;
    if (typeof saved.qa_model === 'string' && saved.qa_model.trim()) settings.qa_model = saved.qa_model;
    if (typeof saved.qa_url === 'string' && /^https?:\/\//.test(saved.qa_url)) settings.qa_url = saved.qa_url;
    if (typeof saved.detection_threshold === 'number' && saved.detection_threshold >= .1 && saved.detection_threshold <= 1) settings.detection_threshold = saved.detection_threshold;
    for (const key of ['show_provenance_rays', 'show_bounding_boxes'] as const) {
      if (typeof saved[key] === 'boolean') settings[key] = saved[key];
    }
    if (saved.default_node_label === 'filename') settings.default_node_label = 'filename';
  } catch { /* Corrupt or unavailable storage uses defaults. */ }
  return settings;
}
export const readSettings = () => parseSettings(storedSettings());
export function subscribeSettings(listener: () => void) {
  const storage = (event: StorageEvent) => { if (event.key === SETTINGS_KEY || event.key === null) listener(); };
  window.addEventListener('storage', storage);
  window.addEventListener(changeEvent, listener);
  return () => { window.removeEventListener('storage', storage); window.removeEventListener(changeEvent, listener); };
}
export function useSettings() {
  const raw = useSyncExternalStore(subscribeSettings, storedSettings, () => null);
  return useMemo(() => parseSettings(raw), [raw]);
}
export async function saveSettings(client: ApiClient, settings: Settings, signal?: AbortSignal, apiKey?: string) {
  const { qa_provider, qa_model, qa_url, openai_base_url, detection_threshold, show_provenance_rays } = settings;
  const saved = await client.request('put', '/api/v1/settings', {
    body: { qa_provider, qa_model, qa_url, openai_base_url, detection_threshold, show_provenance_rays,
      ...(settings.offline_mode !== undefined ? { offline_mode: settings.offline_mode } : {}),
      ...(settings.vision_model !== undefined ? { vision_model: settings.vision_model } : {}),
      ...(settings.vision_use_qa_model !== undefined ? { vision_use_qa_model: settings.vision_use_qa_model } : {}),
      ...(apiKey?.trim() ? { openai_api_key: apiKey.trim() } : {}) }, signal,
  });
  // Persist only known, non-secret preferences, even if a server returns extra fields.
  const preferences = parseSettings(JSON.stringify({ ...settings, ...saved }));
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(preferences));
    window.dispatchEvent(new Event(changeEvent));
  } catch {
    throw new Error('Backend settings saved, but browser storage is unavailable. Enable local storage and save again.');
  }
  return preferences;
}
