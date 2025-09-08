// server/ws-server.cjs
const { WebSocketServer } = require('ws');

const PORT = process.env.WS_PORT ? Number(process.env.WS_PORT) : 8080;
const wss = new WebSocketServer({ port: PORT });

function isAction(msg) {
  return msg && typeof msg === 'object' && typeof msg.type === 'string';
}

wss.on('connection', (ws) => {
  console.log('WS client connected');

  ws.on('message', (raw) => {
    // Ignora líneas vacías o espacios (evita "Unexpected end of JSON input")
    const text = String(raw).trim();
    if (!text) return;

    try {
      const msg = JSON.parse(text);

      // broadcast: {kind:"broadcast", payload:{type:"..."}}
      if (msg && msg.kind === 'broadcast' && isAction(msg.payload)) {
        const payload = msg.payload;
        wss.clients.forEach((client) => {
          if (client.readyState === 1) {
            client.send(JSON.stringify({ kind: 'action', payload }));
          }
        });
        return;
      }

      // acción directa al mismo cliente (no broadcast)
      if (isAction(msg)) {
        ws.send(JSON.stringify({ kind: 'action', payload: msg }));
        return;
      }

      // payload inválido
      ws.send(JSON.stringify({ kind: 'error', error: 'Invalid payload: expected {type: string} or {kind:\"broadcast\", payload:{type:...}}' }));
    } catch (e) {
      ws.send(JSON.stringify({ kind: 'error', error: e?.message || String(e) }));
    }
  });

  ws.on('close', () => console.log('WS client disconnected'));
});

console.log(`WS server on ws://localhost:${PORT}`);
