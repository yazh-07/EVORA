import { useDialogClose } from '../ui/useDialogClose';
import { useEffect, useRef, useState } from 'react';
import { useApiClient } from '../api/ApiProvider';
import { ApiHttpError } from '../api/client';
import { defaultSettings, readSettings, saveSettings, saveViewerSettings, type Settings } from './settings';
import './SettingsModal.css';
import { ChatGPTConnection } from './ChatGPTConnection';
import { AppearanceForm } from '../appearance/AppearanceModal';
import { UpdatesPanel } from './Updates';

const ollamaModels = [
  ['llama3.1:8b', 'Llama 3.1'],
  ['deepseek-r1:8b', 'DeepSeek R1'],
  ['qwen2.5-coder:7b', 'Qwen 2.5 Coder'],
];
const openaiModels = [
  ['gpt-4o', 'GPT-4o'],
  ['gpt-4o-mini', 'GPT-4o mini'],
  ['o3-mini', 'o3-mini'],
];
const modelsFor = (provider: Settings['qa_provider']) => provider === 'chatgpt' ? [] : provider === 'openai' ? openaiModels : ollamaModels;

export type SettingsSection = 'appearance' | 'models' | 'display' | 'updates';
export function SettingsModal({ onClose, initialSection = 'appearance' }: { onClose: () => void; initialSection?: SettingsSection }) {
  const client = useApiClient();
  const canConfigure = !client.isLocalAuth() || client.getUser()?.role === 'administrator';
  const [section, setSection] = useState<SettingsSection>(initialSection === 'models' && !canConfigure ? 'appearance' : initialSection);
  const dialog = useRef<HTMLDialogElement>(null);
  const closeDialog = useDialogClose(dialog, onClose);
  const [draft, setDraft] = useState(readSettings);
  const popularModels = modelsFor(draft.qa_provider);
  const [apiKey, setApiKey] = useState('');
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
    if (!client.hasToken() || !canConfigure) {
      setDraft(readSettings());
      setLoading(false);
      return;
    }
    void client.request('get', '/api/v1/settings', { signal: request.signal }).then(settings => {
      if (request.signal.aborted) return;
      setDraft(current => ({ ...current, ...settings,
        detection_threshold: current.detection_threshold, plate_detection_threshold: current.plate_detection_threshold, show_provenance_rays: current.show_provenance_rays,
        show_bounding_boxes: current.show_bounding_boxes, default_node_label: current.default_node_label,
      }));
    }).catch(() => {
      if (!request.signal.aborted) {
        setLoadFailed(true); setError('Could not load model settings.');
      }
    }).finally(() => { if (!request.signal.aborted) setLoading(false); });
    return () => request.abort();
  }, [client, reload, canConfigure]);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setDraft(current => ({ ...current, [key]: value }));
    setError('');
    if (key === 'qa_url' || key === 'openai_base_url' || key === 'qa_provider') clearConnection();
  }
  function clearConnection() {
    testRequest.current?.abort(); setConnection('idle'); setModels([]); setVisionModels(undefined); setConnectionError(''); setModelSearch('');
  }
  async function testConnection() {
    testRequest.current?.abort();
    const request = new AbortController(); testRequest.current = request;
    setConnection('testing'); setModelPicker('all'); setModelSearch(''); setModels([]); setConnectionError(''); setVisionModels(undefined);
    try {
      const result = await client.request('post', '/api/v1/settings/models', {
        body: { offline_mode: draft.offline_mode !== false, qa_provider: draft.qa_provider, ...(draft.qa_provider === 'openai'
          ? { openai_base_url: draft.openai_base_url, ...(apiKey.trim() ? { openai_api_key: apiKey.trim() } : {}) }
          : draft.qa_provider==='ollama' ? { qa_url: draft.qa_url } : {}) }, signal: request.signal,
      });
      if (!request.signal.aborted) { setModels(result.models); setVisionModels(result.vision_models); setConnection('connected'); }
    } catch (cause) { if (!request.signal.aborted) {
      setConnectionError(cause instanceof ApiHttpError && cause.apiError ? cause.apiError.message : 'Connection failed. Retry.');
      setConnection('failed');
    } }
  }
  async function save(next = draft, close = true, key = apiKey) {
    const request = new AbortController(); saveRequest.current = request;
    setSaving(true); setError('');
    try {
      const saved = section === 'display' ? saveViewerSettings(next) : await saveSettings(client, next, request.signal, key);
      if (!request.signal.aborted) {
        setDraft(saved); setApiKey('');
        if (close) closeDialog();
      }
    }
    catch (cause) {
      if (!request.signal.aborted) setError(cause instanceof Error && cause.message.startsWith('Backend settings saved')
        ? cause.message : 'Could not save. Check the model and connection.');
    } finally { if (!request.signal.aborted) setSaving(false); }
  }
  const disabled = saving || (section === 'models' && (loading || loadFailed));
  return <dialog ref={dialog} className="settings-modal" aria-labelledby="settings-title" onCancel={event => { event.preventDefault(); if (!saving) closeDialog(); }}>
      <header className="settings-heading"><div><h2 id="settings-title">Settings</h2></div>
        <button type="button" aria-label="Close settings" disabled={saving} onClick={closeDialog}>✕</button></header>
      <nav className="settings-sections" aria-label="Settings sections">
        {(['appearance', ...(canConfigure ? ['models'] : []), ...(client.hasToken() ? ['display', 'updates'] : [])] as SettingsSection[]).map(item => <button key={item} type="button" aria-pressed={section === item} disabled={saving} onClick={() => setSection(item)}>{item === 'appearance' ? 'Appearance' : item === 'models' ? 'Models' : item === 'updates' ? 'Updates' : 'Viewer'}</button>)}
      </nav>
      {section === 'appearance' ? <AppearanceForm onClose={closeDialog} /> : section === 'updates' ? <><UpdatesPanel /><footer className="settings-actions"><button type="button" onClick={closeDialog}>Done</button></footer></> : <form onInvalidCapture={event => { const field = event.target as HTMLElement; const options = field.closest('details'); if (options) options.open = true; }} onSubmit={event => { event.preventDefault(); if (!disabled) void save(); }}>
      <div className="settings-content">
        {loading && section === 'models' && <p role="status">Loading settings…</p>}
        {error && <p role="alert">{error}</p>}
        {loadFailed && section === 'models' && <button type="button" onClick={() => setReload(value => value + 1)}>Retry</button>}
        <fieldset hidden={section !== 'models'} disabled={disabled || section !== 'models'}><legend className="sr-only">Models</legend>
          <label className="settings-toggle"><span>Local models only</span><input type="checkbox" role="switch" checked={draft.offline_mode !== false} onChange={event => {
            const offline = event.target.checked; update('offline_mode', offline);
            if (offline) { update('qa_provider', 'ollama'); setApiKey(''); update('qa_model', defaultSettings.qa_model); }
            clearConnection();
          }} /></label>
          <label htmlFor="settings-provider">Provider</label><select id="settings-provider" value={draft.qa_provider} onChange={event => {
            const provider = event.target.value as Settings['qa_provider'];
            if(provider==='chatgpt')setApiKey('');
            update('qa_provider', provider);
            update('qa_model', provider === 'chatgpt' ? '' : provider === 'openai' ? 'gpt-4o' : defaultSettings.qa_model);
            if(provider==='chatgpt')update('vision_use_qa_model',true);
          }}>
            <option value="ollama">Ollama</option>
            {draft.offline_mode === false && <option value="openai">OpenAI-compatible</option>}
            {draft.offline_mode === false && <option value="chatgpt">ChatGPT</option>}
          </select>
          <label htmlFor="settings-model">Model</label>
          <input id="settings-model" list="settings-model-options" required maxLength={200} pattern="\S+" value={draft.qa_model} onChange={event => update('qa_model', event.target.value)} placeholder="Model name" />
          <datalist id="settings-model-options">{[...new Set([...popularModels.map(([model]) => model), ...models])].map(model => <option key={model} value={model} />)}</datalist>
          {draft.qa_provider==='chatgpt'&&<ChatGPTConnection onSharing={sharing=>setDraft(current=>({...current,has_chatgpt_connection:sharing}))} />}
          {draft.qa_provider === 'openai' && <label>API key<input type="password" value={apiKey} autoComplete="new-password" placeholder={draft.has_openai_key ? 'Saved · enter to replace' : 'API key'} onChange={event => { setApiKey(event.target.value); setError(''); clearConnection(); }} /></label>}
          {draft.qa_provider !== 'chatgpt' && <details className="settings-advanced"><summary>Connection options</summary>
            {draft.qa_provider === 'openai' ? <label>Base URL<input required type="url" value={draft.openai_base_url} onChange={event => update('openai_base_url', event.target.value)} /></label>
              : <label>Ollama URL<input required type="url" value={draft.qa_url} onChange={event => update('qa_url', event.target.value)} /></label>}
          </details>}
          <label className="settings-toggle"><span>Use this model for images</span><input type="checkbox" role="switch" checked={draft.vision_use_qa_model === true} onChange={event => update('vision_use_qa_model', event.target.checked)} /></label>
          {draft.vision_use_qa_model ? <>
            {visionModels !== undefined && models.includes(draft.qa_model) && !visionModels.includes(draft.qa_model) && <p role="alert">This model does not support images. Choose a vision model.</p>}
          </> : <><label htmlFor="vision-model">Vision model</label>
          <input id="vision-model" value={draft.vision_model ?? ''} maxLength={200} pattern="\S*" onChange={event => update('vision_model', event.target.value)} placeholder="Model name" />
</>}
          <div className="settings-connection"><button type="button" disabled={connection === 'testing'} onClick={() => void testConnection()}>{connection === 'testing' ? 'Checking…' : 'Test connection'}</button>
            {connection === 'connected' && <span className="settings-connected" role="status">Connected</span>}</div>
          {connection === 'failed' && <p role="alert">{connectionError}</p>}
          {connection === 'connected' && <section className="settings-models" aria-label="Available models">
            <label className="sr-only" htmlFor="model-list-kind">Model list</label>
            <select id="model-list-kind" value={modelPicker} onChange={event => setModelPicker(event.target.value as 'all' | 'vision')}><option value="all">All models</option><option value="vision">Image models</option></select>
            {modelPicker === 'vision' && visionModels === undefined ? <p>Image support unknown. Enter a vision model above.</p> : <>
              <label className="sr-only" htmlFor="model-search">Find a model</label><input id="model-search" type="search" value={modelSearch} onChange={event => setModelSearch(event.target.value)} placeholder="Find a model" />
              <ul>{(modelPicker === 'vision' ? visionModels ?? [] : models).filter(model => model.toLowerCase().includes(modelSearch.trim().toLowerCase())).map(model => <li key={model}><button type="button" aria-label={modelPicker === 'vision' ? `Use ${model} for images` : `Use ${model}`} aria-pressed={modelPicker === 'vision' ? !draft.vision_use_qa_model && draft.vision_model === model : draft.qa_model === model} onClick={() => {
                if (modelPicker === 'vision') { update('vision_model', model); update('vision_use_qa_model', false); }
                else update('qa_model', model);
              }}>{model}</button></li>)}</ul>
              {!(modelPicker === 'vision' ? visionModels ?? [] : models).some(model => model.toLowerCase().includes(modelSearch.trim().toLowerCase())) && <p>No matching models.</p>}
            </>}
          </section>}
        </fieldset>
        <fieldset hidden={section !== 'display'} disabled={disabled || section !== 'display'}><legend>Media</legend>
          <label htmlFor="settings-threshold" className="settings-slider-label">Detection confidence <output>{Math.round(draft.detection_threshold * 100)}%</output></label>
          <input id="settings-threshold" type="range" min="50" max="95" step="1" value={draft.detection_threshold * 100} onChange={event => update('detection_threshold', Number(event.target.value) / 100)} />
          <label htmlFor="plate-threshold" className="settings-slider-label">Plate confidence <output>{Math.round((draft.plate_detection_threshold ?? .4) * 100)}%</output></label>
          <input id="plate-threshold" type="range" min="10" max="95" value={(draft.plate_detection_threshold ?? .4) * 100} onChange={event => update('plate_detection_threshold', Number(event.target.value) / 100)} />
          <label className="settings-toggle"><span>Bounding boxes</span><input type="checkbox" role="switch" checked={draft.show_bounding_boxes} onChange={event => update('show_bounding_boxes', event.target.checked)} /></label>
        </fieldset>
        <fieldset hidden={section !== 'display'} disabled={disabled || section !== 'display'}><legend>Connections</legend>
          <label className="settings-toggle"><span>Source connections</span><input type="checkbox" role="switch" checked={draft.show_provenance_rays} onChange={event => update('show_provenance_rays', event.target.checked)} /></label>
          <label>Node labels<select value={draft.default_node_label} onChange={event => update('default_node_label', event.target.value as Settings['default_node_label'])}><option value="source_description">Source description</option><option value="filename">Filename</option></select></label>
        </fieldset>
      </div>
      <footer className="settings-actions"><button type="button" disabled={disabled} onClick={() => {
        clearConnection();
        void save(section === 'display' ? { ...draft, detection_threshold: defaultSettings.detection_threshold, plate_detection_threshold: defaultSettings.plate_detection_threshold, show_provenance_rays: defaultSettings.show_provenance_rays, show_bounding_boxes: defaultSettings.show_bounding_boxes, default_node_label: defaultSettings.default_node_label } : { ...defaultSettings, offline_mode: true, vision_model: '', vision_use_qa_model: false, has_openai_key: draft.has_openai_key }, false, '');
      }}>Reset</button><div><button type="button" disabled={saving} onClick={closeDialog}>Cancel</button><button type="submit" className="settings-save" disabled={disabled}>{saving ? 'Saving…' : 'Save'}</button></div></footer>
    </form>}
  </dialog>;
}
