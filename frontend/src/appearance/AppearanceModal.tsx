import { useEffect, useState } from 'react';
import { accessibleAccent, accentPresets, applyAppearance, defaultAppearance, readAppearance, resolvedMode, saveAppearance } from './appearance';

export function AppearanceForm({ onClose }: { onClose: () => void }) {
  const close = onClose;
  const [draft, setDraft] = useState(readAppearance);
  const [hex, setHex] = useState(draft.accent);
  const [error, setError] = useState('');
  const valid = /^#[\da-f]{6}$/i.test(hex);
  const colors = accessibleAccent(draft.accent, resolvedMode(draft) === 'dark');
  useEffect(() => () => applyAppearance(readAppearance()), []);
  useEffect(() => {
    applyAppearance(draft);
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => applyAppearance(draft);
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [draft]);
  function choose(accent: string) { setHex(accent); setDraft(value => ({ ...value, accent })); setError(''); }
  return <form className="appearance-form" onSubmit={event => {
      event.preventDefault();
      if (!valid) return;
      try { saveAppearance(draft); close(); } catch { setError('Your browser could not save this preference. Enable local storage and try again.'); }
    }}>
      <div className="appearance-content">
        <fieldset className="appearance-modes"><legend>Display mode</legend><div>{(['light', 'dark', 'system'] as const).map(mode => <button key={mode} type="button" aria-pressed={draft.mode === mode} onClick={() => setDraft(value => ({ ...value, mode }))}><span className={`mode-preview mode-${mode}`} aria-hidden="true"><i /><i /><i /></span>{mode.slice(0, 1).toUpperCase() + mode.slice(1)}</button>)}</div></fieldset>
        <fieldset className="appearance-accents"><legend>Accent color</legend><div className="accent-presets">{accentPresets.map(preset => <button key={preset.name} type="button" aria-pressed={draft.accent === preset.color} onClick={() => choose(preset.color)}><span style={{ background: preset.color }} aria-hidden="true">{draft.accent === preset.color ? '✓' : ''}</span>{preset.name}</button>)}</div>
          <div className="custom-accent"><label htmlFor="accent-picker">Custom color<input id="accent-picker" type="color" value={draft.accent} onChange={event => choose(event.target.value)} /></label><label htmlFor="accent-hex">Hex code<input id="accent-hex" value={hex} maxLength={7} spellCheck={false} aria-invalid={!valid} aria-describedby={!valid ? 'accent-error' : undefined} onChange={event => { const value = event.target.value; setHex(value); if (/^#[\da-f]{6}$/i.test(value)) choose(value.toLowerCase()); }} /></label></div>
          {!valid && <p id="accent-error" role="alert">Use a six-digit color, such as #0f766e.</p>}
        </fieldset>
        {colors.adjusted && <p className="appearance-note" role="status">Color adjusted for readable text.</p>}
        {error && <p role="alert">{error}</p>}
      </div>
      <footer className="appearance-actions"><button type="button" onClick={() => { setDraft({ ...defaultAppearance }); setHex(defaultAppearance.accent); setError(''); }}>Reset</button><div><button type="button" onClick={close}>Cancel</button><button type="submit" disabled={!valid}>Apply appearance</button></div></footer>
    </form>;
}
