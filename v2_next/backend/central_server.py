from __future__ import annotations

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Any, Optional
import json
import os

from . import config
from .models.config_model import ConfigUpdate
from .central_store import get_store


class ConfigUpdateRequest(BaseModel):
    device_id: str
    author: Optional[str] = None
    force: bool = False
    requires_restart: bool = False
    config: dict[str, Any]


class ConfigAckRequest(BaseModel):
    device_id: str
    version: str
    status: str
    applied_at: str
    message: Optional[str] = None


class ConfigRequestCreate(BaseModel):
    device_id: str
    author: Optional[str] = None
    reason: Optional[str] = None
    force: bool = False
    requires_restart: bool = False
    approve_now: bool = False
    config: dict[str, Any]


class ConfigRequestApprove(BaseModel):
    request_id: str
    approver: Optional[str] = None
    comment: Optional[str] = None


class ConfigRequestReject(BaseModel):
    request_id: str
    rejector: Optional[str] = None
    comment: Optional[str] = None


class PolicyUpdate(BaseModel):
    approval_required_for_operator: Optional[bool] = None
    auto_approve_admin: Optional[bool] = None


class ConfigRollbackRequest(BaseModel):
    device_id: str
    version: str
    reason: Optional[str] = None
    author: Optional[str] = None
    force: bool = False


def _audit_path() -> Path:
    env_path = os.getenv("SFL_CENTRAL_AUDIT_PATH")
    if env_path:
        return Path(env_path)
    return Path(config.APP_DATA_DIR) / "central_audit.log"


def _ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _get_auth_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return auth_header.strip() or None


def _resolve_role(token: str | None) -> str | None:
    admin_key = os.getenv("SFL_CENTRAL_ADMIN_KEY") or os.getenv("SFL_CENTRAL_API_KEY") or os.getenv(
        "SFL_CONFIG_API_KEY"
    )
    operator_key = os.getenv("SFL_CENTRAL_OPERATOR_KEY")
    viewer_key = os.getenv("SFL_CENTRAL_VIEWER_KEY")
    if not admin_key and not operator_key and not viewer_key:
        return "admin"
    if not token:
        return None
    if admin_key and token == admin_key:
        return "admin"
    if operator_key and token == operator_key:
        return "operator"
    if viewer_key and token == viewer_key:
        return "viewer"
    return None


def _authorize(request: Request, require_admin: bool = False, allow_viewer: bool = True) -> str:
    token = _get_auth_token(request)
    role = _resolve_role(token)
    if role is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    if require_admin and role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    if not allow_viewer and role == "viewer":
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return role


def _authorize_token(token: str | None, require_admin: bool = False, allow_viewer: bool = True) -> str:
    role = _resolve_role(token)
    if role is None:
        raise HTTPException(status_code=401, detail="Authorization required")
    if require_admin and role != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    if not allow_viewer and role == "viewer":
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return role


_CENTRAL_STORE = get_store()


def _audit(event: str, payload: dict[str, Any]) -> None:
    path = _audit_path()
    _ensure_parent(path)
    record = {
        "event": event,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "payload": payload,
    }
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        pass


app = FastAPI(title="SmartFactoryLogger Central Config")


@app.get("/api/config/latest")
def get_latest(device_id: str, request: Request, response: Response):
    _authorize(request, require_admin=False, allow_viewer=True)
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    latest = _CENTRAL_STORE.get_latest(device_id)
    if not latest:
        raise HTTPException(status_code=404, detail="no config for device")
    etag = latest.get("version")
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match and etag and if_none_match == etag:
        response.status_code = 304
        return {}
    if etag:
        response.headers["ETag"] = etag
    return {
        "device_id": device_id,
        "version": latest.get("version"),
        "updated_at": latest.get("updated_at"),
        "requires_restart": latest.get("requires_restart", False),
        "force": latest.get("force", False),
        "config": latest.get("config", {}),
    }


@app.post("/api/config/ack")
def post_ack(payload: ConfigAckRequest, request: Request):
    _authorize(request, require_admin=False, allow_viewer=False)
    ack = {
        "version": payload.version,
        "status": payload.status,
        "applied_at": payload.applied_at,
        "message": payload.message,
        "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _CENTRAL_STORE.add_ack(payload.device_id, ack)
    _audit("ack", {"device_id": payload.device_id, "version": payload.version, "status": payload.status})
    return {"ok": True}


@app.post("/api/config/update")
def update_config(payload: ConfigUpdateRequest, request: Request):
    role = _authorize(request, require_admin=True, allow_viewer=False)
    if not payload.device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    try:
        ConfigUpdate(**payload.config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entry = _CENTRAL_STORE.save_update(
        payload.device_id,
        author=payload.author or role,
        force=payload.force,
        requires_restart=payload.requires_restart,
        config=payload.config,
        source="update",
    )
    _audit(
        "update",
        {"device_id": payload.device_id, "version": entry.get("version"), "author": payload.author or role},
    )
    return {"version": entry.get("version"), "status": "CREATED"}


@app.get("/api/config/policy")
def get_policy_api(request: Request):
    _authorize(request, require_admin=False, allow_viewer=True)
    return _CENTRAL_STORE.get_policy()


@app.post("/api/config/policy")
def update_policy_api(payload: PolicyUpdate, request: Request):
    role = _authorize(request, require_admin=True, allow_viewer=False)
    policy = _CENTRAL_STORE.update_policy(
        {
            "approval_required_for_operator": payload.approval_required_for_operator,
            "auto_approve_admin": payload.auto_approve_admin,
        }
    )
    _audit("policy_update", {"author": role, "policy": policy})
    return policy


@app.post("/api/config/requests")
def create_request(payload: ConfigRequestCreate, request: Request):
    role = _authorize(request, require_admin=False, allow_viewer=False)
    if not payload.device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    try:
        ConfigUpdate(**payload.config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    policy = _CENTRAL_STORE.get_policy()
    entry = _CENTRAL_STORE.create_request(
        payload.device_id,
        author=payload.author or role,
        reason=payload.reason,
        force=payload.force,
        requires_restart=payload.requires_restart,
        config=payload.config,
    )
    request_id = entry.get("id")
    approval_required = role != "admin" and policy.get("approval_required_for_operator", True)
    auto_approve = role == "admin" and (payload.approve_now or policy.get("auto_approve_admin", True))
    if not approval_required and role != "viewer":
        auto_approve = True

    if auto_approve and request_id:
        result = _CENTRAL_STORE.approve_request(
            request_id,
            approver=payload.author or role,
            comment=None,
        )
        _audit(
            "request_approved",
            {"device_id": payload.device_id, "request_id": request_id, "version": result.get("version")},
        )
        return {"status": "APPROVED", "request_id": request_id, "version": result.get("version")}

    _audit("request_created", {"device_id": payload.device_id, "request_id": request_id})
    return {"status": "PENDING", "request_id": request_id}


@app.get("/api/config/requests")
def list_requests(
    request: Request,
    device_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
):
    _authorize(request, require_admin=False, allow_viewer=True)
    items = _CENTRAL_STORE.list_requests(device_id=device_id, status=status, limit=limit)
    return {"items": items}


@app.post("/api/config/requests/approve")
def approve_request(payload: ConfigRequestApprove, request: Request):
    role = _authorize(request, require_admin=True, allow_viewer=False)
    try:
        result = _CENTRAL_STORE.approve_request(
            payload.request_id,
            approver=payload.approver or role,
            comment=payload.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        "request_approved",
        {"device_id": result.get("device_id"), "request_id": payload.request_id, "version": result.get("version")},
    )
    return {"status": "APPROVED", "request_id": payload.request_id, "version": result.get("version")}


@app.post("/api/config/requests/reject")
def reject_request(payload: ConfigRequestReject, request: Request):
    role = _authorize(request, require_admin=True, allow_viewer=False)
    try:
        result = _CENTRAL_STORE.reject_request(
            payload.request_id,
            rejector=payload.rejector or role,
            comment=payload.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit("request_rejected", {"device_id": result.get("device_id"), "request_id": payload.request_id})
    return {"status": "REJECTED", "request_id": payload.request_id}


@app.get("/api/config/history")
def get_history(device_id: str, limit: int = 20, request: Request | None = None):
    if request is not None:
        _authorize(request, require_admin=False, allow_viewer=True)
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    items = _CENTRAL_STORE.list_history(device_id, limit)
    if not items:
        latest = _CENTRAL_STORE.get_latest(device_id)
        if not latest:
            raise HTTPException(status_code=404, detail="device not found")
    return {"device_id": device_id, "items": items}


@app.post("/api/config/rollback")
def rollback_config(payload: ConfigRollbackRequest, request: Request):
    role = _authorize(request, require_admin=True, allow_viewer=False)
    if not payload.device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    target = _CENTRAL_STORE.find_config(payload.device_id, payload.version)
    if not target:
        raise HTTPException(status_code=404, detail="version not found")
    entry = _CENTRAL_STORE.save_update(
        payload.device_id,
        author=payload.author or role,
        force=payload.force,
        requires_restart=bool(target.get("requires_restart", False)),
        config=target.get("config", {}),
        source="rollback",
        rolled_back_from=payload.version,
        reason=payload.reason,
    )
    _audit(
        "rollback",
        {"device_id": payload.device_id, "from": payload.version, "version": entry.get("version")},
    )
    return {"version": entry.get("version"), "status": "ROLLED_BACK"}


@app.get("/ui")
def central_ui(request: Request, token: str | None = None):
    token_value = token or _get_auth_token(request)
    role = _authorize_token(token_value, require_admin=False, allow_viewer=True)
    policy = _CENTRAL_STORE.get_policy()
    devices = _CENTRAL_STORE.list_devices()
    device_rows = ""
    for device_id in devices:
        latest = _CENTRAL_STORE.get_latest(device_id) or {}
        latest_config = json.dumps(latest.get("config", {}), ensure_ascii=True, indent=2)
        device_rows += (
            "<tr>"
            f"<td>{device_id}</td>"
            f"<td>{latest.get('version', '--')}</td>"
            f"<td>{latest.get('updated_at', '--')}</td>"
            f"<td><pre>{latest_config}</pre></td>"
            "</tr>"
        )
    if not device_rows:
        device_rows = "<tr><td colspan='4'>No devices</td></tr>"

    request_rows = ""
    pending = _CENTRAL_STORE.list_requests(device_id=None, status="PENDING", limit=200)
    for entry in pending:
        payload = json.dumps(entry.get("config", {}), ensure_ascii=True, indent=2)
        action_cell = "--"
        if role == "admin":
            token_param = f"&token={token_value}" if token_value else ""
            approve_link = f"/ui/approve?request_id={entry.get('id')}{token_param}"
            reject_link = f"/ui/reject?request_id={entry.get('id')}{token_param}"
            action_cell = f"<a href='{approve_link}'>Approve</a> | <a href='{reject_link}'>Reject</a>"
        request_rows += (
            "<tr>"
            f"<td>{entry.get('id')}</td>"
            f"<td>{entry.get('device_id')}</td>"
            f"<td>{entry.get('author')}</td>"
            f"<td>{entry.get('created_at')}</td>"
            f"<td>{entry.get('reason') or ''}</td>"
            f"<td><pre>{payload}</pre></td>"
            f"<td>{action_cell}</td>"
            "</tr>"
        )
    if not request_rows:
        request_rows = "<tr><td colspan='7'>No pending requests</td></tr>"

    policy_require_attr = "checked" if policy.get("approval_required_for_operator") else ""
    policy_auto_attr = "checked" if policy.get("auto_approve_admin") else ""
    default_payload = json.dumps({"settings": {"logpath": "Z:\\\\logs"}}, ensure_ascii=True, indent=2)

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Central Config Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #0f1115; color: #e6e9ef; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #2c313c; padding: 8px; vertical-align: top; }}
    th {{ background: #1a1f2b; text-align: left; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    .meta {{ color: #9aa4b2; margin-bottom: 16px; }}
    .panel {{ background: #161b25; border: 1px solid #2c313c; padding: 16px; border-radius: 8px; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .card {{ background: #0f141c; border: 1px solid #2c313c; padding: 12px; border-radius: 6px; }}
    label {{ display: block; margin-bottom: 8px; color: #c0c7d4; }}
    input, textarea {{ width: 100%; background: #0b0f15; border: 1px solid #2c313c; color: #e6e9ef; padding: 6px; border-radius: 4px; }}
    textarea {{ min-height: 120px; }}
    button {{ background: #2f6fed; color: #fff; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; }}
    button.secondary {{ background: #30384a; }}
    .result {{ margin-top: 12px; padding: 8px; border-radius: 4px; }}
    .result.ok {{ background: #12321f; color: #9fe6b8; }}
    .result.error {{ background: #3b1b1b; color: #f0b1b1; }}
  </style>
</head>
<body>
  <h1>Central Config Dashboard</h1>
  <div class="meta">Role: {role} | Policy: approval_required_for_operator={policy.get('approval_required_for_operator')} auto_approve_admin={policy.get('auto_approve_admin')}</div>

  <div class="panel">
    <h2>Quick Actions</h2>
    <div class="grid">
      <div class="card">
        <h3>Create Update (Admin)</h3>
        <label>Device ID <input id="update-device" placeholder="LINE-01"></label>
        <label>Author <input id="update-author" placeholder="admin"></label>
        <label><input type="checkbox" id="update-force"> force</label>
        <label><input type="checkbox" id="update-restart"> requires_restart</label>
        <label>Config JSON <textarea id="update-config">{default_payload}</textarea></label>
        <button onclick="submitUpdate()">Send Update</button>
      </div>
      <div class="card">
        <h3>Create Request (Operator)</h3>
        <label>Device ID <input id="request-device" placeholder="LINE-01"></label>
        <label>Author <input id="request-author" placeholder="operator"></label>
        <label>Reason <input id="request-reason" placeholder="Change request"></label>
        <label><input type="checkbox" id="request-force"> force</label>
        <label><input type="checkbox" id="request-restart"> requires_restart</label>
        <label>Config JSON <textarea id="request-config">{default_payload}</textarea></label>
        <button onclick="submitRequest()">Send Request</button>
      </div>
      <div class="card">
        <h3>Policy</h3>
        <label><input type="checkbox" id="policy-approval" {policy_require_attr}> approval_required_for_operator</label>
        <label><input type="checkbox" id="policy-auto" {policy_auto_attr}> auto_approve_admin</label>
        <button class="secondary" onclick="updatePolicy()">Update Policy</button>
      </div>
    </div>
    <div id="action-result" class="result" style="display:none;"></div>
  </div>

  <h2>Latest Configs</h2>
  <table>
    <thead>
      <tr>
        <th>Device</th>
        <th>Version</th>
        <th>Updated</th>
        <th>Config</th>
      </tr>
    </thead>
    <tbody>
      {device_rows}
    </tbody>
  </table>
  <h2>Pending Requests</h2>
  <table>
    <thead>
      <tr>
        <th>Request ID</th>
        <th>Device</th>
        <th>Author</th>
        <th>Created</th>
        <th>Reason</th>
        <th>Config</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {request_rows}
    </tbody>
  </table>
  <p class="meta">Use /ui?token=... for admin actions.</p>

  <script>
    const token = new URLSearchParams(window.location.search).get('token');
    const resultEl = document.getElementById('action-result');

    function showResult(message, ok) {{
      resultEl.textContent = message;
      resultEl.className = ok ? 'result ok' : 'result error';
      resultEl.style.display = 'block';
    }}

    function buildHeaders() {{
      const headers = {{ 'Content-Type': 'application/json' }};
      if (token) {{
        headers['Authorization'] = `Bearer ${{token}}`;
      }}
      return headers;
    }}

    function parseJson(raw) {{
      if (!raw) {{
        return {{}};
      }}
      return JSON.parse(raw);
    }}

    async function postJson(path, payload) {{
      const res = await fetch(path, {{
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify(payload),
      }});
      let data = {{}};
      try {{
        data = await res.json();
      }} catch (err) {{
        data = {{}};
      }}
      if (!res.ok) {{
        throw new Error(data.detail || `HTTP ${{res.status}}`);
      }}
      return data;
    }}

    async function submitUpdate() {{
      try {{
        const payload = {{
          device_id: document.getElementById('update-device').value.trim(),
          author: document.getElementById('update-author').value.trim(),
          force: document.getElementById('update-force').checked,
          requires_restart: document.getElementById('update-restart').checked,
          config: parseJson(document.getElementById('update-config').value),
        }};
        const res = await postJson('/api/config/update', payload);
        showResult(`Update created: ${{res.version}}`, true);
        window.location.reload();
      }} catch (err) {{
        showResult(err.message || 'Update failed', false);
      }}
    }}

    async function submitRequest() {{
      try {{
        const payload = {{
          device_id: document.getElementById('request-device').value.trim(),
          author: document.getElementById('request-author').value.trim(),
          reason: document.getElementById('request-reason').value.trim(),
          force: document.getElementById('request-force').checked,
          requires_restart: document.getElementById('request-restart').checked,
          config: parseJson(document.getElementById('request-config').value),
        }};
        const res = await postJson('/api/config/requests', payload);
        showResult(`Request submitted: ${{res.request_id}}`, true);
        window.location.reload();
      }} catch (err) {{
        showResult(err.message || 'Request failed', false);
      }}
    }}

    async function updatePolicy() {{
      try {{
        const payload = {{
          approval_required_for_operator: document.getElementById('policy-approval').checked,
          auto_approve_admin: document.getElementById('policy-auto').checked,
        }};
        await postJson('/api/config/policy', payload);
        showResult('Policy updated', true);
        window.location.reload();
      }} catch (err) {{
        showResult(err.message || 'Policy update failed', false);
      }}
    }}
  </script>
</body>
</html>
"""
    return Response(content=html, media_type="text/html")


@app.get("/ui/approve")
def ui_approve(request_id: str, request: Request, token: str | None = None):
    token_value = token or _get_auth_token(request)
    role = _authorize_token(token_value, require_admin=True, allow_viewer=False)
    try:
        result = _CENTRAL_STORE.approve_request(request_id, approver=role, comment="ui")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        "request_approved",
        {"device_id": result.get("device_id"), "request_id": request_id, "version": result.get("version")},
    )
    redirect_target = f"/ui?token={token_value}" if token_value else "/ui"
    return RedirectResponse(url=redirect_target, status_code=303)


@app.get("/ui/reject")
def ui_reject(request_id: str, request: Request, token: str | None = None):
    token_value = token or _get_auth_token(request)
    role = _authorize_token(token_value, require_admin=True, allow_viewer=False)
    try:
        result = _CENTRAL_STORE.reject_request(request_id, rejector=role, comment="ui")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit("request_rejected", {"device_id": result.get("device_id"), "request_id": request_id})
    redirect_target = f"/ui?token={token_value}" if token_value else "/ui"
    return RedirectResponse(url=redirect_target, status_code=303)


@app.get("/ui/policy")
def ui_policy(
    request: Request,
    token: str | None = None,
    approval_required_for_operator: int | None = None,
    auto_approve_admin: int | None = None,
):
    token_value = token or _get_auth_token(request)
    role = _authorize_token(token_value, require_admin=True, allow_viewer=False)
    updates: dict[str, Any] = {}
    if approval_required_for_operator is not None:
        updates["approval_required_for_operator"] = bool(approval_required_for_operator)
    if auto_approve_admin is not None:
        updates["auto_approve_admin"] = bool(auto_approve_admin)
    if updates:
        policy = _CENTRAL_STORE.update_policy(updates)
        _audit("policy_update", {"author": role, "policy": policy})
    redirect_target = f"/ui?token={token_value}" if token_value else "/ui"
    return RedirectResponse(url=redirect_target, status_code=303)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.central_server:app", host="127.0.0.1", port=config.CENTRAL_PORT, reload=False)
