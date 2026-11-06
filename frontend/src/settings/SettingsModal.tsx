import { useDialogClose } from '../ui/useDialogClose';
import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import { defaultSettings, readSettings, saveSettings, type Settings } from './settings';
import './SettingsModal.css';
import { ChatGPTConnection } from './ChatGPTConnection';

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
const modelsFor = (provider: Settings['qa_provider']) => provider === 'chatgpt' ? [] : provider === 'openai' ? openaiModels : ollamaModels;

export function SettingsModal({ onClose }: { onClose: () => void }) {
  const client = useApiClient();
  const dialog = useRef<HTMLDialogElement>(null);
  const closeDialog = useDialogClose(dialog, onClose);
  const [draft, setDraft] = useState(readSettings);
  const popularModels = modelsFor(draft.qa_provider);
  const [apiKey, setApiKey] = useState('');
  const [custom, setCustom] = useState(!popularModels.some(([model]) => model === draft.qa_model));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState<'idle' | 'testing' | 'connected' | 'failed'>('idle');
  const [models, setModels] = useState<string[]>([]);
  const [visionModels, setVisionModels] = useState<string[] | undefined>();
  const [modelPicker, setModelPicker] = useState<'all' | 'vision'>('all');
  const [modelSearch, setModelSearch] = useState('');
  const [connectionError, setConnectionError] = useState('');
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
    testRequest.current?.abort(); setConnection('idle'); setModels([]); setVisionModels(undefined); setConnectionError(''); setModelSearch('');
  }
  async function testConnection(picker: 'all' | 'vision' = 'all') {
    testRequest.current?.abort();
    const request = new AbortController(); testRequest.current = request;
    setConnection('testing'); setModelPicker(picker); setModelSearch(''); setModels([]); setConnectionError(''); setVisionModels(undefined);
    try {
      const result = await client.request('post', '/api/v1/settings/models', {
        body: { offline_mode: draft.offline_mode !== false, qa_provider: draft.qa_provider, ...(draft.qa_provider === 'openai'
          ? { openai_base_url: draft.openai_base_url, ...(apiKey.trim() ? { openai_api_key: apiKey.trim() } : {}) }
          : draft.qa_provider==='ollama' ? { qa_url: draft.qa_url } : {}) }, signal: request.signal,
      });
      if (!request.signal.aborted) { setModels(result.models); setVisionModels(result.vision_models); setConnection('connected'); }
    } catch (cause) { if (!request.signal.aborted) {
      setConnectionError(cause instanceof ApiHttpError && cause.apiError ? cause.apiError.message : 'Could not reach the backend to test this connection.');
      setConnection('failed');
    } }
  }
  async function save(next = draft, close = true, key = apiKey) {
    const request = new AbortController(); saveRequest.current = request;
    setSaving(true); setError('');
    try {
      const saved = await saveSettings(client, next, request.signal, key);
      if (!request.signal.aborted) {
        setDraft(saved); setApiKey('');
        setCustom(!modelsFor(saved.qa_provider).some(([model]) => model === saved.qa_model));
        if (close) closeDialog();
      }
    }
    catch (cause) {
      if (!request.signal.aborted) setError(cause instanceof Error && cause.message.startsWith('Backend settings saved')
        ? cause.message : 'Could not save settings. Check the model name, endpoint and connection, then retry.');
    } finally { if (!request.signal.aborted) setSaving(false); }
  }
  const disabled = loading || saving || loadFailed;
  return <dialog ref={dialog} className="settings-modal" aria-labelledby="settings-title" onCancel={event => { event.preventDefault(); if (!saving) closeDialog(); }}>
    <form onSubmit={event => { event.preventDefault(); if (!disabled) void save(); }}>
      <header className="settings-heading"><div><span className="section-label">WORKSTATION PREFERENCES</span><h2 id="settings-title">Settings</h2></div>
        <button type="button" aria-label="Close settings" disabled={saving} onClick={closeDialog}>✕</button></header>
      <div className="settings-content">
        {loading && <p role="status">Loading current settings…</p>}
        {error && <p role="alert">{error}</p>}
        {loadFailed && <button type="button" onClick={() => setReload(value => value + 1)}>Retry loading settings</button>}
        <fieldset disabled={disabled}><legend>Model configuration</legend>
          <label className="settings-toggle"><span>Offline mode — local models only</span><input type="checkbox" role="switch" checked={draft.offline_mode !== false} onChange={event => {
            const offline = event.target.checked; update('offline_mode', offline);
            if (offline) { update('qa_provider', 'ollama'); setApiKey(''); update('qa_model', defaultSettings.qa_model); }
            clearConnection();
          }} /></label>
          <p className="settings-hint">Online mode permits the configured hosted provider. Image transmission requires a separate action and confirmation on the image.</p>
          <p>{draft.offline_mode !== false ? 'Offline mode: evidence questions use an installed local Ollama model. Cloud providers are disabled.' : 'Choose the provider and model used to answer questions about your evidence.'}</p>
          <label>Provider<select value={draft.qa_provider} onChange={event => {
            const provider = event.target.value as Settings['qa_provider'];
            if(provider==='chatgpt')setApiKey('');
            update('qa_provider', provider);
            update('qa_model', provider === 'chatgpt' ? '' : provider === 'openai' ? 'gpt-4o' : defaultSettings.qa_model);
            if(provider==='chatgpt')update('vision_use_qa_model',true);
            setCustom(provider==='chatgpt');
          }}>
            <option value="ollama">Local (Ollama)</option>
            {draft.offline_mode === false && <option value="openai">Cloud / Custom (OpenAI-compatible)</option>}
            {draft.offline_mode === false && <option value="chatgpt">ChatGPT plan</option>}
          </select></label>
          <label htmlFor="settings-model">Model</label>
          <select id="settings-model" value={custom ? 'custom' : draft.qa_model} onChange={event => {
            const value = event.target.value; setCustom(value === 'custom'); if (value !== 'custom') update('qa_model', value);
          }}>
            {popularModels.map(([value, label]) => <option key={value} value={value}>{label} ({value})</option>)}
            <option value="custom">Custom model…</option>
          </select>
          {custom && <label>Custom model name<input required maxLength={200} pattern="\S+" value={draft.qa_model} onChange={event => update('qa_model', event.target.value)} placeholder={draft.qa_provider === 'openai' ? 'Provider model ID' : 'e.g. mistral:7b'} /></label>}
          {draft.qa_provider==='chatgpt'&&<ChatGPTConnection onSharing={sharing=>setDraft(current=>({...current,has_chatgpt_connection:sharing}))} />}
          {draft.qa_provider === 'openai' ? <>
            <label>API Key<input type="password" value={apiKey} autoComplete="new-password" placeholder="sk-..." onChange={event => { setApiKey(event.target.value); setError(''); clearConnection(); }} /></label>
            <p className="settings-hint">{draft.has_openai_key ? 'A key is saved. Leave blank to keep it.' : 'Enter your provider API key.'} Keys are kept on the backend and are never saved in browser storage.</p>
            <label>Base URL<input required type="url" value={draft.openai_base_url} onChange={event => update('openai_base_url', event.target.value)} placeholder="https://api.openai.com/v1" /></label>
            <p className="settings-hint">Supports OpenAI, Groq, OpenRouter and custom compatible endpoints. Include the API path, such as /v1.</p>
            <p className="settings-hint">OpenRouter: https://openrouter.ai/api/v1. Select a full provider/model ID from the fetched list. Listing models does not verify credits or permission to run a model.</p>
          </> : draft.qa_provider==='ollama' ? <label>Ollama Endpoint URL<input required type="url" value={draft.qa_url} onChange={event => update('qa_url', event.target.value)} placeholder="http://127.0.0.1:11434" /></label> : <p>Text, images and sampled video frames use the connected plan through OpenAI. Speech stays local. Model access is confirmed by a completed request.</p>}
          <label className="settings-toggle"><span>Use selected model for image description and OCR</span><input type="checkbox" role="switch" checked={draft.vision_use_qa_model === true} onChange={event => update('vision_use_qa_model', event.target.checked)} /></label>
          {draft.vision_use_qa_model ? <>
            <p className="settings-hint">Image processing uses {draft.qa_model}. The selected model must accept images. Changing the Q&amp;A model also changes the model for future image requests.</p>
            {visionModels !== undefined && models.includes(draft.qa_model) && !visionModels.includes(draft.qa_model) && <p role="alert">The provider does not advertise image input for this model. Select an image-capable model or use a separate vision model.</p>}
          </> : <><label htmlFor="vision-model">Vision model</label>
          <input id="vision-model" value={draft.vision_model ?? ''} maxLength={200} pattern="\S*" onChange={event => update('vision_model', event.target.value)} placeholder="Vision-capable model ID from your provider" />
          <p className="settings-hint">Use a separate image-capable model, or leave blank to disable image understanding. The provider and endpoint are shared with Q&amp;A.</p></>}
          {draft.qa_provider === 'openai' && <>
            <button type="button" disabled={connection === 'testing'} onClick={() => void testConnection('vision')}>Fetch image-capable models</button>
            <p className="settings-hint">If your Q&amp;A model is text-only, select a separate model for images. Your Q&amp;A selection stays the same.</p>
            {connection === 'testing' && modelPicker === 'vision' && <p role="status">Fetching image-capable models…</p>}
            {connection === 'connected' && modelPicker === 'vision' && <section className="settings-models" aria-label="Image-capable models">
              {visionModels === undefined ? <p>The provider does not publish image capabilities in its model list. Enter a supported vision model manually.</p> : <>
                {models.includes(draft.qa_model) && !visionModels.includes(draft.qa_model) && <p>The provider does not advertise image input for your Q&amp;A model. Select a separate model below.</p>}
                <label>Filter image-capable models<input type="search" value={modelSearch} onChange={event => setModelSearch(event.target.value)} placeholder="Search provider or model name" /></label>
                <ul>{visionModels.filter(model => model.toLowerCase().includes(modelSearch.trim().toLowerCase())).map(model => <li key={model}><button type="button" aria-label={`Use ${model} for images`} aria-pressed={!draft.vision_use_qa_model && draft.vision_model === model} onClick={() => {
                  update('vision_model', model); update('vision_use_qa_model', false);
                }}>{model}</button></li>)}</ul>
                {visionModels.length === 0 ? <p>No image-capable models were advertised by this provider.</p> : !visionModels.some(model => model.toLowerCase().includes(modelSearch.trim().toLowerCase())) && <p>No image-capable models match this search.</p>}
                {!!draft.vision_model && !draft.vision_use_qa_model && <p role="status">Image model: {draft.vision_model}. Save Settings to apply.</p>}
              </>}
            </section>}
          </>}
          <p className="settings-hint">The endpoint is reached from the backend workstation.</p>
          <div className="settings-connection"><button type="button" disabled={connection === 'testing'} onClick={() => void testConnection()}>{connection === 'testing' ? 'Connecting…' : 'Test Connection & Fetch Models'}</button>
            {connection === 'connected' && <span className="settings-connected" role="status">● Connected</span>}</div>
          {connection === 'failed' && <p role="alert">{connectionError}</p>}
          {connection === 'connected' && modelPicker === 'all' && <div className="settings-models"><span>Available models</span>{models.length ? <ul>{models.map(model => <li key={model}><button type="button" aria-pressed={draft.qa_model === model} onClick={() => { update('qa_model', model); setCustom(!popularModels.some(([value]) => value === model)); }}>{model}{visionModels?.includes(model) ? ' · Image input' : ''}</button></li>)}</ul> : <p>No models available on this endpoint.</p>}</div>}
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
        void save({ ...defaultSettings, offline_mode: true, vision_model: '', vision_use_qa_model: false, has_openai_key: draft.has_openai_key }, false, '');
      }}>Reset to Defaults</button><div><button type="button" disabled={saving} onClick={closeDialog}>Cancel</button><button type="submit" className="settings-save" disabled={disabled}>{saving ? 'Saving…' : 'Save Settings'}</button></div></footer>
    </form>
  </dialog>;
}
