"""Servidor MCP (stdio) que expone los agentes locales de llama-server a ZCode.

Herramientas:
  local_ask(agent, prompt, system?, max_tokens?, timeout_s?) -> POST /v1/chat/completions
  local_status() -> salud de cada endpoint (nunca arranca ni detiene modelos:
  el hub (CATTS.cmd) es el dueno de la exclusion de GPU).

Solo stdlib. Los puertos vienen de scripts/local_models.py (fuente de verdad);
si no se puede importar, se usan los fallbacks de abajo.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVER_NAME = "local-agents"
SERVER_VERSION = "0.1.0"
DEFAULT_TIMEOUT_S = 300.0
HEALTH_TIMEOUT_S = 2.0

# (puerto, alias de modelo esperado, descripcion corta)
FALLBACK_ENDPOINTS = {
    "smol": (9104, "", "Slot Smol: el modelo que el hub tenga cargado (mini, qwen35, coder7...)"),
    "taller": (9102, "qwen35-local", "Qwen3.5 9B editor de Taller"),
    "qwen27": (9101, "qwen27-local", "Qwen3.8 27B Q3 consultor (lento, RAM)"),
    "spark": (9105, "spark25", "Spark-X2.5 4B rapido"),
    "neohorse": (9107, "neohorse", "NeoHorse-1 4B router rapido"),
    "bonsai2": (9106, "bonsai2", "Proxy auto-compresor frente a Bonsai-2 27B (:9103)"),
}
ALIASES = {"minicpm": "smol", "qwen35": "taller", "neo": "neohorse", "bonsai": "bonsai2"}
# Si el proxy de bonsai2 no esta arriba, probamos el llama-server directo.
DIRECT_FALLBACK = {"bonsai2": 9103}


def load_endpoints():
    ports = {}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import local_models
        ports["smol"] = local_models.SMOL_PORT
        for key, (alias_map, spec_key) in {
            "taller": ("qwen35-local", "qwen35"),
            "qwen27": ("qwen27-local", "qwen27"),
            "spark": ("spark25", "spark"),
            "neohorse": ("neohorse", "neohorse"),
        }.items():
            ports[key] = local_models.STANDALONE[spec_key]["port"]
    except Exception as exc:  # sin local_models seguimos con los fallbacks
        print(f"[{SERVER_NAME}] local_models no importable ({exc}); uso puertos fallback", file=sys.stderr)
        return {k: v[0] for k, v in FALLBACK_ENDPOINTS.items()}
    ports["bonsai2"] = 9106  # proxy; fallback directo abajo
    merged = {k: ports.get(k, FALLBACK_ENDPOINTS[k][0]) for k in FALLBACK_ENDPOINTS}
    return merged


PORTS = load_endpoints()

TOOLS = [
    {
        "name": "local_ask",
        "description": (
            "Ask a local llama-server model (free tokens, no plan usage). Best for bulk/mechanical "
            "work: summarizing text, extraction, formatting, batch classification. Not for "
            "judgment-heavy review. Choose agent: 'smol' (whatever model the hub loaded), "
            "'taller' (Qwen3.5 9B editor), 'qwen27' (27B consultor, slow), 'spark' (4B fast), "
            "'neohorse' (4B router), 'bonsai2' (27B ternary via auto-compress proxy)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "enum": sorted(PORTS), "description": "Local endpoint to use"},
                "prompt": {"type": "string", "description": "User prompt/task"},
                "system": {"type": "string", "description": "Optional system prompt"},
                "max_tokens": {"type": "integer", "description": "Max new tokens (default 1024)"},
                "timeout_s": {"type": "number", "description": "HTTP timeout seconds (default 300)"},
            },
            "required": ["agent", "prompt"],
        },
    },
    {
        "name": "local_status",
        "description": "Health-check the local llama-server endpoints. Read-only: reports which ports are up and which model each serves; never starts or stops models.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _http_json(url, payload=None, timeout=DEFAULT_TIMEOUT_S):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _served_model(port):
    try:
        data = _http_json(f"http://127.0.0.1:{port}/v1/models", timeout=HEALTH_TIMEOUT_S)
        ids = [m.get("id", "") for m in data.get("data", [])]
        return ids[0] if ids else ""
    except Exception:
        return None


def tool_status(_args):
    lines = []
    for name in sorted(PORTS):
        port = PORTS[name]
        model = _served_model(port)
        state = "UP" if model is not None else "down"
        extra = f" modelo={model}" if model else ""
        lines.append(f"{name} :{port} -> {state}{extra}")
    lines.append("(para arrancar: CATTS.cmd / MODELS.cmd; el hub adopta servers ya corriendo)")
    return "\n".join(lines), False


def tool_ask(args):
    name = ALIASES.get(args["agent"], args["agent"])
    if name not in PORTS:
        return f"agente desconocido: {args['agent']}. Validos: {', '.join(sorted(PORTS))}", True
    port = PORTS[name]
    candidates = [port] + ([DIRECT_FALLBACK[name]] if name in DIRECT_FALLBACK else [])
    messages = ([{"role": "system", "content": args["system"]}] if args.get("system") else [])
    messages.append({"role": "user", "content": args["prompt"]})
    timeout = float(args.get("timeout_s", DEFAULT_TIMEOUT_S))
    last_err = None
    for cand in candidates:
        model = _served_model(cand)
        if model is None:
            last_err = f":{cand} sin respuesta"
            continue
        payload = {"model": model, "messages": messages, "stream": False,
                   "max_tokens": int(args.get("max_tokens", 1024))}
        try:
            data = _http_json(f"http://127.0.0.1:{cand}/v1/chat/completions", payload=payload, timeout=timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            return f"HTTP {exc.code} de :{cand}: {body}", True
        except Exception as exc:
            last_err = f":{cand} fallo ({exc})"
            continue
        msg = (data.get("choices") or [{}])[0].get("message", {})
        text = msg.get("content") or msg.get("reasoning_content") or ""
        if not text.strip():
            return f"[{name}:{model}] respuesta vacia", True
        return text, False
    return (f"{name} no disponible ({last_err}). Arrancalo con CATTS.cmd / MODELS.cmd.", True)


TOOL_HANDLERS = {"local_ask": tool_ask, "local_status": tool_status}


def handle(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion") or "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}}}
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method in ("tools/list", "resources/list", "prompts/list"):
        key = method.split("/")[0]
        return {"jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": TOOLS} if key == "tools" else {key: []}}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name", "")
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"tool desconocido: {name}"}}
        try:
            text, is_error = handler(params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": text}], "isError": is_error}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"error interno: {exc}"}], "isError": True}}
    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"metodo desconocido: {method}"}}
    return None


def main():
    print(f"[{SERVER_NAME}] v{SERVER_VERSION} endpoints: " +
          ", ".join(f"{k}:{v}" for k, v in sorted(PORTS.items())), file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"JSON invalido: {exc}"}}
        else:
            resp = handle(msg)
        if resp is not None:
            sys.stdout.buffer.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
