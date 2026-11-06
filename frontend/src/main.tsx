import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import { createApiClient } from './api/client';
import './styles.css';
import './workspace.css';
import './motion.css';

const root = document.getElementById('root');
if (!root) throw new Error('EVORA root element is missing.');
const baseUrl =
  typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin !== 'null'
    ? window.location.origin
    : __EVORA_API_BASE_URL__;
const apiClient = createApiClient({ baseUrl, authMode: 'local' });

createRoot(root).render(
  <StrictMode>
    <ApiProvider client={apiClient}><App /></ApiProvider>
  </StrictMode>,
);
