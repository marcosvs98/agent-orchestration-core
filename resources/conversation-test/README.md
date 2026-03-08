# Conversation SSE Test (Frontend)

Simple static frontend to test `POST /core/v1/conversations` SSE stream.

## How to run

1. Start the API (in one terminal):
   ```bash
   uv run uvicorn src.app:create_app --factory --host 0.0.0.0 --port 8000
   ```
2. Serve the frontend and open in browser:
   ```bash
   make serve-conversation-test
   ```
   Then open http://localhost:9000 (frontend runs on port 9000; API stays on 8000).

## How to use

1. Paste your **JWT token** (Bearer value only; use `make gen-token` to generate one).
2. Set **API base URL** if not `http://localhost:8000`.
3. Type a **message** and click **Send** (or Enter).
4. Chat area shows user/assistant messages; **Stream events** shows raw SSE.

## Fixed IDs

- `flow_id`: 00000000-0000-0000-0000-000000000700  
- `flow_version_id`: 00000000-0000-0000-0000-000000000701  
- `session_id`: 4a77dbf0-af03-4bee-9382-17aac00da302  
- `user_id`: marcosteste  

Edit `API_IDS` in `index.html` to change them.
