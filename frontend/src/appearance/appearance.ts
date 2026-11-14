import { useMemo, useSyncExternalStore } from 'react';

export type Appearance = { version: 1; mode: 'light' | 'dark' | 'system'; accent: string };
export const APPEARANCE_KEY = 'evora-appearance';
const eventName = 'evora-appearance-changed';
export const defaultAppearance: Appearance = { version: 1, mode: 'light', accent: '#7c3aed' };
export const accentPresets = [
  { name: 'Teal', color: '#0f766e' }, { name: 'Blue', color: '#2859b8' },
  { name: 'Purple', color: '#7c3aed' }, { name: 'Amber', color: '#996515' },
  { name: 'Rose', color: '#b33f65' },
];

export function parseAppearance(raw: string | null): Appearance {
  try {
    const value = JSON.parse(raw ?? 'null');
    if (value?.version !== 1) return { ...defaultAppearance };
    return { version: 1,
      mode: ['light', 'dark', 'system'].includes(value.mode) ? value.mode : 'light',
      accent: typeof value.accent === 'string' && /^#[\da-f]{6}$/i.test(value.accent) ? value.accent.toLowerCase() : defaultAppearance.accent };
  } catch { return { ...defaultAppearance }; }
}
function stored(): string | null {
  try {
    const raw = window.localStorage.getItem(APPEARANCE_KEY);
    if (raw !== null) return raw;
    const legacy = window.localStorage.getItem('evora-theme');
    return JSON.stringify({ ...defaultAppearance, mode: legacy === 'dark' ? 'dark' : 'light' });
  } catch { return null; }
}
export const readAppearance = () => parseAppearance(stored());

function rgb(hex: string) {
  return [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
}
export function contrast(a: string, b: string): number {
  const luminance = (color: string) => {
    const values = rgb(color).map(value => { const n = value / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4; });
    return .2126 * values[0]! + .7152 * values[1]! + .0722 * values[2]!;
  };
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0]! + .05) / (values[1]! + .05);
}

/** Keep custom accents readable as both text and filled controls in either mode. */
export function accessibleAccent(requested: string, dark: boolean) {
  const valid = /^#[\da-f]{6}$/i.test(requested) ? requested : defaultAppearance.accent;
  const channels = rgb(valid);
  let accent = valid;
  const background = dark ? '#1b2528' : '#f4f6f8';
  for (let step = 0; step <= 100; step++) {
    const ratio = step / 100;
    accent = '#' + channels.map(channel => Math.round(channel + ((dark ? 255 : 0) - channel) * ratio).toString(16).padStart(2, '0')).join('');
    if (contrast(accent, background) >= 5.3) break;
  }
  const foreground = contrast(accent, '#ffffff') >= 4.5 ? '#ffffff' : '#102a27';
  return { accent, foreground, adjusted: accent.toLowerCase() !== valid.toLowerCase() };
}
export function resolvedMode(appearance: Appearance): 'light' | 'dark' {
  return appearance.mode === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : appearance.mode;
}
export function applyAppearance(appearance: Appearance) {
  const mode = resolvedMode(appearance), colors = accessibleAccent(appearance.accent, mode === 'dark');
  document.documentElement.dataset.theme = mode;
  document.body.dataset.theme = mode;
  document.documentElement.style.setProperty('--appearance-accent', colors.accent);
  document.documentElement.style.setProperty('--appearance-accent-fg', colors.foreground);
  document.documentElement.style.colorScheme = mode;
}
export function saveAppearance(appearance: Appearance) {
  const valid = parseAppearance(JSON.stringify(appearance));
  window.localStorage.setItem(APPEARANCE_KEY, JSON.stringify(valid));
  applyAppearance(valid);
  window.dispatchEvent(new Event(eventName));
}
function subscribe(listener: () => void) {
  const storage = (event: StorageEvent) => { if (event.key === APPEARANCE_KEY || event.key === 'evora-theme' || event.key === null) listener(); };
  window.addEventListener(eventName, listener);
  window.addEventListener('storage', storage);
  return () => { window.removeEventListener(eventName, listener); window.removeEventListener('storage', storage); };
}
export function useAppearance() {
  const raw = useSyncExternalStore(subscribe, stored, () => null);
  return useMemo(() => parseAppearance(raw), [raw]);
}
function subscribeSystemMode(listener: () => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', listener);
  return () => media.removeEventListener('change', listener);
}
export function useResolvedMode(appearance: Appearance): 'light' | 'dark' {
  const systemDark = useSyncExternalStore(subscribeSystemMode, () => window.matchMedia('(prefers-color-scheme: dark)').matches, () => false);
  return appearance.mode === 'system' ? (systemDark ? 'dark' : 'light') : appearance.mode;
}
export function initializeAppearance() {
  const apply = () => applyAppearance(readAppearance());
  apply();
  const unsubscribe = subscribe(apply);
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener('change', apply);
  return () => { unsubscribe(); media.removeEventListener('change', apply); };
}
