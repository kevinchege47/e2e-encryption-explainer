# E2EEncrypto — Multi-Device End-to-End Encryption Demo

An interactive, step-by-step simulation of how WhatsApp-style end-to-end encryption works across multiple devices. Built for learning — every cryptographic operation is visible, logged, and explained in real time.

---

## 🎯 What This Demonstrates

Most explanations of E2E encryption stop at "the server can't read your messages." This demo shows exactly **why** that is true, and **how** it holds up even when a new device joins an existing account.

You will see:

- **RSA-2048 key pairs** generated live in the browser
- **Messages encrypted separately** for each device before leaving the client
- **The server receiving and storing only ciphertext** — never plaintext
- **A new device (Laptop) joining** and receiving old messages through client-side re-encryption, without the server ever seeing the content
- **A simulated server breach** proving the stolen data is unreadable
- **Forward secrecy and the Double Ratchet** explained visually

---

## 🏗️ Architecture

The server is **structurally blind**. It stores encrypted blobs indexed by device ID and serves them back on request. It has:

- ❌ No private keys
- ❌ No plaintext
- ❌ No session keys
- ✅ Only public keys and ciphertext

### High-Level Flow

```
Sender's Browser
  ↓ (encrypt locally with RSA-OAEP + AES-GCM)
Server (blind storage)
  ↓ (store ciphertext only)
Recipient's Browser
  ↓ (decrypt locally with private key)
Readable Plaintext
```

---

## 🔐 Cryptography Used

| Primitive     | Purpose                                      |
|---------------|----------------------------------------------|
| RSA-2048-OAEP | Encrypting the AES key per recipient device  |
| AES-256-GCM   | Encrypting the message body                  |
| Web Crypto API| All crypto runs in the browser               |

### Hybrid Encryption Explained

RSA can only encrypt ~245 bytes at 2048-bit key size. The solution:

1. **Encrypt message** with AES-256-GCM (fast, any size)
2. **Encrypt AES key** with RSA-2048-OAEP (safe key exchange)
3. **Recipient** uses their RSA private key to unwrap the AES key
4. **Recipient** uses AES key to decrypt the message body

Result: One RSA operation per device + one AES operation for all.

---

## 📋 The Six-Step Demo Flow

### ① Setup Phone
Phone generates an RSA key pair **locally in the browser**. Public key is uploaded to server. **Private key never leaves the device.**

- ✓ Private key generated and stored in browser only
- ✓ Public key sent to server
- ✓ Server blindly stores the public key

### ② Send Old Message
Alice encrypts "Hello Kevin" for Phone only. Message is encrypted **in the browser** before transmission.

- ✓ Message encrypted with AES-256-GCM
- ✓ AES key encrypted with Phone's RSA public key
- ✓ Server receives only ciphertext
- ✓ Phone decrypts locally using its private key

### ③ Setup Laptop
Phone scans a QR code from Laptop and approves it as trusted. Laptop generates its own key pair locally.

- ✓ Laptop generates RSA key pair locally
- ✓ Laptop's public key uploaded to server
- ✓ Phone approves Laptop via QR ceremony (simulated)
- ✓ Server stores Laptop's public key

### ④ Sync Old Messages ⭐ Most Interesting!
Laptop needs access to the old message. **Phone re-encrypts it for Laptop** without the server ever seeing plaintext.

1. Laptop asks server: "Which messages don't I have?"
2. Phone fetches its encrypted blob from server
3. **Phone decrypts** it locally (server never had the key)
4. **Phone re-encrypts** the plaintext for Laptop
5. **Phone sends** new ciphertext to server
6. Laptop fetches and **decrypts** its copy

**Server never sees the plaintext at any point in this chain.**

### ⑤ Send New Message
Alice sends "Hey Kevin" to both devices. **Two different ciphertexts** are produced from the same plaintext.

- ✓ Message encrypted separately for Phone
- ✓ Message encrypted separately for Laptop
- ✓ Both devices receive ciphertext only
- ✓ Each device decrypts independently with its private key

### ⑥ Simulate Server Breach
Attacker downloads the entire server database via `GET /api/attack/snapshot`:

**Attacker has:**
- ✓ Phone public key
- ✓ Laptop public key
- ✓ Encrypted AES keys
- ✓ Encrypted message bodies

**Attacker is missing:**
- ✗ Phone private key (never left device)
- ✗ Laptop private key (never left device)

**Result:** Without private keys, all ciphertext is **cryptographic noise**. Decryption fails. Messages remain unreadable.

---

## ⚠️ Forward Secrecy Note

This demo uses **static RSA identity keys** — one key pair per device for the lifetime of the session.

Real systems like WhatsApp and Signal add the **Double Ratchet Algorithm**, which:

- **Signed prekeys** — medium-term keys uploaded to server in advance
- **One-time prekeys** — single-use keys for session establishment
- **Ephemeral session keys** — new key pair generated per message
- **Forward secrecy** — old keys deleted after use (compromise doesn't expose past messages)
- **Break-in recovery** — ratchet advances, limiting exposure window

**The core guarantee is identical:** Server never sees plaintext. Private keys never leave devices.

---

## 🚀 Running Locally

### Requirements

- Python 3.11+
- A modern browser (Web Crypto API support)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourname/whatsapp-e2e-flow
cd whatsapp-e2e-flow

# Install dependencies
pip install -r requirements.txt
```

### Start the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Open in Browser

```
http://localhost:8000
```

---

## 📂 Project Structure

```
whatsapp-e2e-flow/
├── main.py                 # FastAPI backend, database, API endpoints
├── static/
│   └── index.html          # Interactive demo UI (vanilla JS + Web Crypto)
├── e2e_demo.db             # SQLite database (auto-created)
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── test_main.http          # HTTP request examples
```

---

## 🛠️ Tech Stack

- **FastAPI** — async Python web framework
- **aiosqlite** — async SQLite bindings
- **Uvicorn** — ASGI server
- **Web Crypto API** — RSA-OAEP + AES-GCM (browser native)
- **Vanilla JS** — no framework, keeping crypto logic readable
- **SQLite** — lightweight persistent storage

---

## 📚 API Endpoints

### Device Management

- `POST /api/devices/register` — Register a new device with public key
- `POST /api/devices/approve` — Approve a device as trusted
- `GET /api/devices` — List all registered devices
- `GET /api/devices/{device_id}/public_key` — Get a device's public key

### Messages

- `POST /api/messages/send` — Send encrypted message
- `GET /api/messages/{device_id}` — Retrieve messages for a device
- `GET /api/messages/old/{device_id}` — List messages missing for a device
- `POST /api/messages/sync` — Re-encrypt and sync old message to new device

### Security Simulation

- `GET /api/attack/snapshot` — Simulate server breach (returns database contents)

### Administration

- `POST /api/reset` — Clear all data and restart demo

### WebSocket

- `WS /ws` — Real-time broadcast of events and logs

---

## 🔄 Database Schema

### devices
```sql
CREATE TABLE devices (
    device_id     TEXT PRIMARY KEY,
    device_name   TEXT NOT NULL,
    public_key    TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    approved      INTEGER DEFAULT 0
);
```

### messages
```sql
CREATE TABLE messages (
    msg_id     TEXT PRIMARY KEY,
    sender     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### message_recipients
```sql
CREATE TABLE message_recipients (
    msg_id            TEXT NOT NULL,
    device_id         TEXT NOT NULL,
    encrypted_aes_key TEXT NOT NULL,
    encrypted_body    TEXT NOT NULL,
    iv                TEXT NOT NULL,
    PRIMARY KEY (msg_id, device_id)
);
```

**Key insight:** The server **never stores plaintext**. Every message in `message_recipients` is fully encrypted.

---

## 🎓 Educational Use

This project is intended as a **learning tool**. It simplifies some aspects of production E2E systems to keep the core concept visible:

- ✗ No Double Ratchet (forward secrecy)
- ✗ No prekey bundles
- ✗ No sealed sender
- ✗ No out-of-order message handling
- ✓ Core principle: server-side encryption blindness

**⚠️ Do not use this code as the basis for a production encryption system.**

---

## ❓ FAQ

### Why does the browser do all the crypto?

Because that's what E2E encryption means. If the server encrypted messages, it would have access to plaintext and keys — defeating the purpose entirely. The Web Crypto API gives browsers access to native, non-exportable cryptographic primitives running in a sandboxed environment.

### Why store public keys on the server?

Public keys are public by design. Anyone can have your public key — it can only *encrypt* data *to* you. Only your private key (which stays on your device) can decrypt it. Storing public keys on the server is safe.

### Why can't the server sync old messages itself?

Because the server cannot decrypt them — it has no private keys. The only entity that can read encrypted messages is the device they were encrypted for. That device must perform the re-encryption step. This is exactly how WhatsApp handles linked devices.

### What if a device's private key is stolen?

In this simplified demo: all messages encrypted to that device become readable. In production (with Double Ratchet): only the compromised session keys are exposed. Past messages remain protected via forward secrecy, and future messages are protected via key ratcheting.

### Why RSA-2048-OAEP + AES-256-GCM?

**RSA-2048-OAEP:** Asymmetric encryption for secure key exchange. OAEP is the recommended padding scheme.

**AES-256-GCM:** Symmetric encryption for message bodies. AES is fast and authenticated (GCM provides integrity).

**Together:** Hybrid encryption gives us the best of both worlds — asymmetric authentication + symmetric speed.

---

## 🚦 Demo Walkthrough

1. **Click "Setup Phone"** → Phone generates RSA key pair, uploads public key
2. **Click "Send Old Message"** → Alice sends "Hello Kevin" encrypted to Phone only
3. **Click "Setup Laptop"** → Laptop generates RSA key pair, Phone approves via QR
4. **Click "Sync Old Messages"** → Phone re-encrypts the old message for Laptop
5. **Click "Send New Message"** → Alice sends "Hey Kevin" encrypted separately for both
6. **Click "Simulate Breach"** → Download all server data and attempt decryption (fails)

**Watch the logs to see every cryptographic operation!**

---

## 📖 Learn More

- [Signal Protocol](https://signal.org/docs/) — Production E2E system
- [Double Ratchet Algorithm](https://arxiv.org/pdf/1313.0714.pdf) — Forward secrecy via key ratcheting
- [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API) — Browser cryptography
- [OWASP: Cryptographic Storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

## 📝 License

Educational. Use freely for learning purposes.

---

## 🎉 Demo Complete!

You've seen the full E2E encryption lifecycle.

**Public keys live on the server. Private keys never leave the device. Without private keys, encrypted data is meaningless to an attacker.**

Built with ❤️ for understanding end-to-end encryption.

