# Continue with ChatGPT

EVORA can use the official Sign in with ChatGPT flow as a model provider. This connection is separate from local workstation accounts: it does not replace the local administrator, case permissions or offline login. The connected plan powers model requests for the workstation, so only a local administrator can connect, change or disconnect it.

## Connect

1. Sign in to EVORA as an administrator and open Settings.
2. Turn off **Local models only** and choose **ChatGPT plan** under Provider.
3. Click **Continue with ChatGPT**. Finish authorization in the browser. Allow pop-ups when using the web app. Grant permission to use your plan if offered.
4. Return to Settings. The connection indicates whether plan usage was authorized.
5. Click **Test connection**, choose an account-provided model, then save Settings. No API key or custom base URL is needed for this provider.

ChatGPT plan eligibility, supported clients and account usage limits are controlled by OpenAI. A successful sign-in or model listing is not a guarantee of inference access. A completed model response verifies access for that request. The user must complete authentication and consent.

## Text, images, video and speech

Case Q&A and executive briefs can use this provider. Images and sampled video frames use the existing image pipeline with the selected model or a separate vision model. ChatGPT plan model discovery currently supplies account model IDs; EVORA does not guess image capability when the catalog does not provide it. Choose a model known to accept images. The shared-model option is enabled when choosing the ChatGPT provider, but image processing still needs a supported model and explicit consent.

Connecting, refreshing status and listing models do not transmit evidence. Image/video actions confirm the official OpenAI destination before sending normalized images or sampled frames. Queued image configuration includes a hash binding the account registration; changing accounts causes that queued request to fail rather than sending it under the new account. The original files remain unchanged, and model-derived outputs retain provenance.

Native audio/video input and transcription are not supported by this plan flow. Video analysis still samples frames locally, and optional speech transcription stays local through the existing Whisper integration. Cloud model requests require internet; local account login and local processing remain available offline. Switching **Local models only** back on cancels a pending sign-in and blocks ChatGPT inference/renewal. An explicitly selected unsaved online draft may connect and fetch the catalog without enabling evidence processing until Settings are saved.

## Storage and disconnect

The backend uses a stable host ID, fresh OAuth state/nonce/PKCE, and a short-lived HTTP callback listener on `127.0.0.1`. The listener is started before authorization and uses the same exact callback URI for code exchange. It validates the issued client ID, the JWT's RSA signature against OpenAI JWKS, issuer, audience, expiry, nonce, and the current local administrator session. Identity-only consent does not authorize model requests.

Credentials are stored beside the configured SQLite database in `<database filename>.chatgpt/credentials.json`, not in the database or browser storage. The directory and file use owner-only permissions on Unix; the file is replaced atomically. Deployments must also protect that directory with the operating system's access controls. It contains sensitive access, refresh and retained ID tokens: exclude it from case exports, support bundles and source control. Git ignores `*.chatgpt/`. The directory remains separate when copying/deleting a case database. Disconnect before removing a workstation installation.

Rotating token refresh is serialized. Access tokens are sent only to the fixed official OpenAI endpoints, never to a configurable OpenAI-compatible endpoint. Request bodies use the plan-specific Responses contract (`store: false`, `stream: true`), and partial/failed/incomplete streams are rejected. Tokens do not enter model provenance or frontend settings.

Use **Disconnect ChatGPT** to clear local tokens. Online disconnect attempts remote revocation; offline or failed revocation is explicitly reported, with a link to [ChatGPT usage and app access](https://chatgpt.com/settings/usage). A registration identifier and account label remain for reconnecting. **Use another ChatGPT account** starts a new registration and only replaces the connection after verified authorization. One active connection is supported; a full multi-profile manager is not implemented. Review older app registrations in ChatGPT Settings when switching accounts.

On Windows, v1.2.1 and later use a protected NTFS ACL granting access to the current Windows user and SYSTEM. Unix mode bits are not used to judge Windows file privacy. Existing credential files are secured in place on access, preserving their host registration and any saved account credentials. This fixes the v1.2.0 Windows sign-in startup error; upgrade and retry without deleting the workstation database.

The connection survives backend restarts. Existing non-secret provider/model preferences are still runtime settings: select online ChatGPT mode again after restarting. You do not need to enter an API key, but expired/revoked sessions may require signing in again. Local EVORA sign-out does not disconnect the workstation model provider; a pending OAuth callback requires the initiating local administrator session to remain valid.

## Verification

Automated tests use explicit OpenAI protocol doubles with real RSA-signed test ID tokens, actual loopback callback handling, real credential-file permissions, scope/offline rejection, session revocation, refresh serialization and completed-stream validation. Image tests check Responses image content, provenance without tokens, and account-change rejection. The browser acceptance test uses labeled OAuth UI doubles and checks provider selection, popup/status, model discovery, settings persistence, disconnect and absence of browser tokens. These checks do not prove live plan entitlement or model accuracy.

Official references: [registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).
