import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { ApiProvider } from './api/ApiProvider';
import { createApiClient } from './api/client';
import './styles.css';

const root = document.getElementById('root');
if (!root) throw new Error('EVORA root element is missing.');
const apiClient = createApiClient({ baseUrl: __EVORA_API_BASE_URL__ });

createRoot(root).render(
  <StrictMode>
    <ApiProvider client={apiClient}><App /></ApiProvider>
  </StrictMode>,
);
