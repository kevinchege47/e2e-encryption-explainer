"""
WhatsApp-Style Multi-Device End-to-End Encryption Demo
======================================================
Architecture:
  - Server NEVER performs encryption or decryption
  - Server NEVER stores plaintext, private keys, or session keys
  - All crypto happens in the browser (Web Crypto API)
  - Server stores ONLY ciphertext blobs

Flow:
  Sender browser → encrypt locally → FastAPI (store ciphertext only) → devices decrypt locally
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = "e2e_demo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id     TEXT PRIMARY KEY,
    device_name   TEXT NOT NULL,
    public_key    TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    approved      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    msg_id     TEXT PRIMARY KEY,
    sender     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_recipients (
    msg_id            TEXT NOT NULL,
    device_id         TEXT NOT NULL,
    encrypted_aes_key TEXT NOT NULL,
    encrypted_body    TEXT NOT NULL,
    iv                TEXT NOT NULL,
    PRIMARY KEY (msg_id, device_id)
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


async def log(actor: str, message: str, level: str = "info", data: dict = None):
    await manager.broadcast({
        "type": "log",
        "actor": actor,
        "message": message,
        "level": level,
        "data": data or {},
        "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
    })
    await asyncio.sleep(0.25)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="E2E Encryption Demo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Models ──

class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_name: str
    public_key: str


class ApproveDeviceRequest(BaseModel):
    device_id: str


class SetApprovalRequest(BaseModel):
    device_id: str
    approved: bool


class SendMessageRequest(BaseModel):
    sender: str
    recipients: list[dict]


class SyncMessageRequest(BaseModel):
    msg_id: str
    device_id: str
    encrypted_aes_key: str
    encrypted_body: str
    iv: str


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        return f.read()


@app.post("/api/reset")
async def reset_demo():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM message_recipients")
        await db.execute("DELETE FROM messages")
        await db.execute("DELETE FROM devices")
        await db.commit()
    await manager.broadcast({"type": "reset"})
    return {"status": "ok"}


@app.post("/api/devices/register")
async def register_device(req: DeviceRegisterRequest):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT device_id FROM devices WHERE device_id=?", (req.device_id,)
        ) as cur:
            existing = await cur.fetchone()

        if existing:
            await db.execute(
                "UPDATE devices SET public_key=?, registered_at=? WHERE device_id=?",
                (req.public_key, datetime.now().isoformat(), req.device_id),
            )
        else:
            await db.execute(
                """INSERT INTO devices
                   (device_id, device_name, public_key, registered_at, approved)
                   VALUES (?,?,?,?,?)""",
                (
                    req.device_id, req.device_name, req.public_key,
                    datetime.now().isoformat(),
                    1 if req.device_name == "Phone" else 0,
                ),
            )
        await db.commit()

    await log(
        req.device_name,
        "Registered. Public key stored on server. Private key stays on device — server never sees it.",
        "success",
        {"public_key_preview": req.public_key[:60] + "..."},
    )
    await manager.broadcast({
        "type": "device_registered",
        "device_id": req.device_id,
        "device_name": req.device_name,
        "approved": req.device_name == "Phone",
    })
    return {"status": "registered"}


@app.post("/api/devices/approve")
async def approve_device(req: ApproveDeviceRequest):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET approved=1 WHERE device_id=?", (req.device_id,)
        )
        await db.commit()
    await log("Phone", f"Approved device {req.device_id} as trusted", "success")
    await manager.broadcast({"type": "device_approved", "device_id": req.device_id})
    return {"status": "approved"}


@app.post("/api/devices/set-approval")
async def set_approval(req: SetApprovalRequest):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET approved=? WHERE device_id=?",
            (1 if req.approved else 0, req.device_id),
        )
        await db.commit()
    return {"status": "ok"}


@app.get("/api/devices")
async def list_devices():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT device_id, device_name, public_key, approved FROM devices"
        ) as cur:
            rows = await cur.fetchall()
    return [
        {"device_id": r[0], "device_name": r[1], "public_key": r[2], "approved": bool(r[3])}
        for r in rows
    ]


@app.get("/api/devices/{device_id}/public_key")
async def get_device_public_key(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT public_key, device_name FROM devices WHERE device_id=?", (device_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": "Device not found"}
    return {"public_key": row[0], "device_name": row[1]}


@app.post("/api/messages/send")
async def send_message(req: SendMessageRequest):
    msg_id = str(uuid.uuid4())[:8]

    await log(
        "Server",
        "Receiving encrypted blobs from Sender. "
        "Server cannot read these — no private keys here.",
        "warning",
    )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (msg_id, sender, created_at) VALUES (?,?,?)",
            (msg_id, req.sender, datetime.now().isoformat()),
        )
        for recipient in req.recipients:
            await db.execute(
                """INSERT INTO message_recipients
                   (msg_id, device_id, encrypted_aes_key, encrypted_body, iv)
                   VALUES (?,?,?,?,?)""",
                (
                    msg_id,
                    recipient["device_id"],
                    recipient["encrypted_aes_key"],
                    recipient["encrypted_body"],
                    recipient["iv"],
                ),
            )
        await db.commit()

    await log(
        "Server",
        f"Stored {len(req.recipients)} encrypted blob(s) for message {msg_id}. "
        "Attempting decryption... FAILED — no private keys available.",
        "warning",
        {"wiretap_attempt": "FAILED", "reason": "No private key on server"},
    )

    await manager.broadcast({
        "type": "new_message",
        "msg_id": msg_id,
        "sender": req.sender,
        "recipient_count": len(req.recipients),
        "wiretap": {
            "encrypted_aes_key": req.recipients[0]["encrypted_aes_key"][:40] + "...",
            "encrypted_body": req.recipients[0]["encrypted_body"][:40] + "...",
            "attempt": "FAILED",
            "reason": "No private key",
        },
    })

    return {"status": "sent", "msg_id": msg_id}


@app.get("/api/messages/{device_id}")
async def get_messages_for_device(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT m.msg_id, m.sender, m.created_at,
                      mr.encrypted_aes_key, mr.encrypted_body, mr.iv
               FROM messages m
               JOIN message_recipients mr ON m.msg_id = mr.msg_id
               WHERE mr.device_id = ?
               ORDER BY m.created_at""",
            (device_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "msg_id": r[0], "sender": r[1], "created_at": r[2],
            "encrypted_aes_key": r[3], "encrypted_body": r[4], "iv": r[5],
        }
        for r in rows
    ]


@app.get("/api/messages/old/{device_id}")
async def get_old_messages_no_recipient(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT m.msg_id, m.sender, m.created_at
               FROM messages m
               WHERE m.msg_id NOT IN (
                   SELECT msg_id FROM message_recipients WHERE device_id = ?
               )""",
            (device_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"msg_id": r[0], "sender": r[1], "created_at": r[2]} for r in rows]


@app.post("/api/messages/sync")
async def sync_message(req: SyncMessageRequest):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM message_recipients WHERE msg_id=? AND device_id=?",
            (req.msg_id, req.device_id),
        ) as cur:
            exists = await cur.fetchone()

        if not exists:
            await db.execute(
                """INSERT INTO message_recipients
                   (msg_id, device_id, encrypted_aes_key, encrypted_body, iv)
                   VALUES (?,?,?,?,?)""",
                (req.msg_id, req.device_id, req.encrypted_aes_key, req.encrypted_body, req.iv),
            )
            await db.commit()

    await log(
        "Server",
        f"Stored re-encrypted blob for {req.device_id}. "
        "Phone performed the re-encryption — server never saw plaintext.",
        "success",
    )
    await manager.broadcast({
        "type": "message_synced",
        "msg_id": req.msg_id,
        "device_id": req.device_id,
    })
    return {"status": "synced"}


@app.get("/api/attack/snapshot")
async def attack_snapshot():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT device_id, device_name, public_key FROM devices"
        ) as cur:
            devices = await cur.fetchall()
        async with db.execute(
            "SELECT msg_id, device_id, encrypted_aes_key, encrypted_body FROM message_recipients"
        ) as cur:
            blobs = await cur.fetchall()
    return {
        "stolen_devices": [
            {"device_id": r[0], "device_name": r[1], "public_key": r[2][:60] + "..."}
            for r in devices
        ],
        "stolen_blobs": [
            {
                "msg_id": r[0], "device_id": r[1],
                "encrypted_aes_key": r[2][:40] + "...",
                "encrypted_body": r[3][:40] + "...",
            }
            for r in blobs
        ],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)