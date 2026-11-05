import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { defaultSettings, readSettings, saveSettings, type Settings } from './settings';
import './SettingsModal.css';

const ollamaModels = [
  ['llama3.1:8b', 'Llama 3.1 · Fast & Grounded'],
  ['deepseek-r1:8b', 'DeepSeek R1 · Deep Reasoning'],
  ['qwen2.5-coder:7b', 'Qwen 2.5 Coder · Code Analysis'],
];
const openaiModels = [
  ['gpt-4o', 'GPT-4o · Recommended'],
  ['gpt-4o-mini', 'GPT-4o mini · Fast'],
  ['o3-mini', 'o3-mini'],
];
const modelsFor = (provider: Settings['qa_provider']) => provider === 'openai' ? openaiModels : ollamaModels;

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const client = useApiClient();
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState(readSettings);
  const popularModels = modelsFor(draft.qa_provider);
  const [apiKey, setApiKey] = useState('');
  const [custom, setCustom] = useState(!popularModels.some(([model]) => model === draft.qa_model));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState<'idle' | 'testing' | 'connected' | 'failed'>('idle');
  const [models, setModels] = useState<string[]>([]);
  const testRequest = useRef<AbortController | null>(null);
  const saveRequest = useRef<AbortController | null>(null);
  const [reload, setReload] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current!;
    element.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      testRequest.current?.abort(); saveRequest.current?.abort();
      element.close(); document.body.style.overflow = overflow; previous?.focus();
    };
  }, []);
  useEffect(() => {
    const request = new AbortController();
    setLoading(true); setLoadFailed(false); setError('');
    if (!client.hasToken()) {
      setDraft(readSettings());
      setLoading(false);
      return;
    }
    void client.request('get', '/api/v1/settings', { signal: request.signal }).then(settings => {
      if (request.signal.aborted) return;
      setDraft(current => ({ ...current, ...settings }));
      setCustom(!modelsFor(settings.qa_provider).some(([model]) => model === settings.qa_model));
    }).catch(() => {
      if (!request.signal.aborted) {
        setDraft(readSettings());
      }
    }).finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [client, reload]);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setDraft(current => ({ ...current, [key]: value }));
    setError('');
    if (key === 'qa_url' || key === 'openai_base_url' || key === 'qa_provider') clearConnection();
  }
  function clearConnection() {
    testRequest.current?.abort(); setConnection('idle'); setModels([]);
  }
  async function testConnection() {
    testRequest.current?.abort();
    const request = new AbortController(); testRequest.current = request;
    setConnection('testing'); setModels([]);
    try {
      const result = await client.request('post', '/api/v1/settings/models', {
        body: { qa_provider: draft.qa_provider, ...(draft.qa_provider === 'openai'
          ? { openai_base_url: draft.openai_base_url, ...(apiKey.trim() ? { openai_api_key: apiKey.trim() } : {}) }
          : { qa_url: draft.qa_url }) }, signal: request.signal,
      });
      if (!request.signal.aborted) { setModels(result.models); setConnection('connected'); }
    } catch { if (!request.signal.aborted) setConnection('failed'); }
  }
  async function save(next = draft, close = true, key = apiKey) {
    const request = new AbortController(); saveRequest.current = request;
    setSaving(true); setError('');
    try {
      const saved = await saveSettings(client, next, request.signal, key);
      if (!request.signal.aborted) {
        setDraft(saved); setApiKey('');
        setCustom(!modelsFor(saved.qa_provider).some(([model]) => model === saved.qa_model));
        if (close) onClose();
      }
    }
    catch (cause) {
      if (!request.signal.aborted) setError(cause instanceof Error && cause.message.startsWith('Backend settings saved')
        ? cause.message : 'Could not save settings. Check the model name, endpoint and connection, then retry.');
    } finally { if (!request.signal.aborted) setSaving(false); }
  }
  const disabled = loading || saving || loadFailed;
  return <dialog ref={dialog} className="settings-modal" aria-labelledby="settings-title" onCancel={event => { event.preventDefault(); if (!saving) onClose(); }}>
    <form onSubmit={event => { event.preventDefault(); if (!disabled) void save(); }}>
      <header className="settings-heading"><div><span className="section-label">WORKSTATION PREFERENCES</span><h2 id="settings-title">Settings</h2></div>
        <button type="button" aria-label="Close settings" disabled={saving} onClick={onClose}>✕</button></header>
      <div className="settings-content">
        {loading && <p role="status">Loading current settings…</p>}
        {error && <p role="alert">{error}</p>}
        {loadFailed && <button type="button" onClick={() => setReload(value => value + 1)}>Retry loading settings</button>}
        <fieldset disabled={disabled}><legend>AI Copilot Configuration</legend>
          <p>Choose the provider and model used to answer questions about your evidence.</p>
          <label>Provider<select value={draft.qa_provider} onChange={event => {
            const provider = event.target.value as Settings['qa_provider'];
            update('qa_provider', provider);
            update('qa_model', provider === 'openai' ? 'gpt-4o' : defaultSettings.qa_model);
            setCustom(false);
          }}>
            <option value="ollama">Local (Ollama)</option>
            <option value="openai">Cloud / Custom (OpenAI-compatible)</option>
          </select></label>
          <label htmlFor="settings-model">Model</label>
          <select id="settings-model" value={custom ? 'custom' : draft.qa_model} onChange={event => {
            const value = event.target.value; setCustom(value === 'custom'); if (value !== 'custom') update('qa_model', value);
          }}>
            {popularModels.map(([value, label]) => <option key={value} value={value}>{label} ({value})</option>)}
            <option value="custom">Custom model…</option>
          </select>
          {custom && <label>Custom model name<input required maxLength={200} pattern="\S+" value={draft.qa_model} onChange={event => update('qa_model', event.target.value)} placeholder={draft.qa_provider === 'openai' ? 'Provider model ID' : 'e.g. mistral:7b'} /></label>}
          {draft.qa_provider === 'openai' ? <>
            <label>API Key<input type="password" value={apiKey} autoComplete="new-password" placeholder="sk-..." onChange={event => { setApiKey(event.target.value); setError(''); clearConnection(); }} /></label>
            <p className="settings-hint">{draft.has_openai_key ? 'A key is saved. Leave blank to keep it.' : 'Enter your provider API key.'} Keys are kept on the backend and are never saved in browser storage.</p>
            <label>Base URL<input required type="url" value={draft.openai_base_url} onChange={event => update('openai_base_url', event.target.value)} placeholder="https://api.openai.com/v1" /></label>
            <p className="settings-hint">Supports OpenAI, Groq, OpenRouter and custom compatible endpoints. Include the API path, such as /v1.</p>
          </> : <label>Ollama Endpoint URL<input required type="url" value={draft.qa_url} onChange={event => update('qa_url', event.target.value)} placeholder="http://127.0.0.1:11434" /></label>}
          <p className="settings-hint">The endpoint is reached from the backend workstation.</p>
          <div className="settings-connection"><button type="button" disabled={connection === 'testing'} onClick={() => void testConnection()}>{connection === 'testing' ? 'Connecting…' : 'Test Connection & Fetch Models'}</button>
            {connection === 'connected' && <span className="settings-connected" role="status">● Connected</span>}</div>
          {connection === 'failed' && <p role="alert">{draft.qa_provider === 'openai' ? 'Connection failed. Check the API key, base URL and provider access.' : 'Connection failed. Check the URL and that Ollama is running.'}</p>}
          {connection === 'connected' && <div className="settings-models"><span>Available models</span>{models.length ? <ul>{models.map(model => <li key={model}><button type="button" aria-pressed={draft.qa_model === model} onClick={() => { update('qa_model', model); setCustom(!popularModels.some(([value]) => value === model)); }}>{model}</button></li>)}</ul> : <p>No models available on this endpoint.</p>}</div>}
        </fieldset>
        <fieldset disabled={disabled}><legend>Visual Forensics & Media Settings</legend>
          <label htmlFor="settings-threshold" className="settings-slider-label">Detection confidence threshold <output>{Math.round(draft.detection_threshold * 100)}%</output></label>
          <input id="settings-threshold" type="range" min="50" max="95" step="1" value={draft.detection_threshold * 100} onChange={event => update('detection_threshold', Number(event.target.value) / 100)} />
          <div className="settings-range"><span>50% · More detections</span><span>95% · Higher confidence</span></div>
          <p className="settings-hint">Filters displayed bounding boxes; source observations remain available.</p>
          <label className="settings-toggle"><span>Show Bounding Boxes</span><input type="checkbox" role="switch" checked={draft.show_bounding_boxes} onChange={event => update('show_bounding_boxes', event.target.checked)} /></label>
        </fieldset>
        <fieldset disabled={disabled}><legend>Knowledge Graph Settings</legend>
          <label className="settings-toggle"><span>Show Provenance Rays<small>Lineage lines between evidence and extracted nodes.</small></span><input type="checkbox" role="switch" checked={draft.show_provenance_rays} onChange={event => update('show_provenance_rays', event.target.checked)} /></label>
          <label>Default Node Label<select value={draft.default_node_label} onChange={event => update('default_node_label', event.target.value as Settings['default_node_label'])}><option value="source_description">Source Description</option><option value="filename">Filename</option></select></label>
        </fieldset>
      </div>
      <footer className="settings-actions"><button type="button" disabled={disabled} onClick={() => {
        clearConnection();
        void save({ ...defaultSettings, has_openai_key: draft.has_openai_key }, false, '');
      }}>Reset to Defaults</button><div><button type="button" disabled={saving} onClick={onClose}>Cancel</button><button type="submit" className="settings-save" disabled={disabled}>{saving ? 'Saving…' : 'Save Settings'}</button></div></footer>
    </form>
  </dialog>;
}
