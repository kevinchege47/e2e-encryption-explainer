# E2EEncrypto — Multi-Device End-to-End Encryption Demo

An interactive, step-by-step simulation of how WhatsApp-style end-to-end
encryption works across multiple devices. Built for learning — every
cryptographic operation is visible, logged, and explained in real time.

---

## What this demonstrates

Most explanations of E2E encryption stop at "the server can't read your
messages." This demo shows exactly *why* that is true, and *how* it holds
up even when a new device joins an existing account.

You will see:

- RSA-2048 key pairs generated live in the browser
- Messages encrypted separately for each device before leaving the client
- The server receiving and storing only ciphertext — never plaintext
- A new device (Laptop) joining and receiving old messages through
  client-side re-encryption, without the server ever seeing the content
- A simulated server breach proving the stolen data is unreadable
- A visual explanation of forward secrecy and the Double Ratchet

---

## Architecture
The server is structurally blind. It stores encrypted blobs indexed
by device ID and serves them back on request. It has no private keys,
no plaintext, no session keys — nothing that would allow decryption.

---

## Cryptography used

| Primitive     | Purpose                                      |
|---------------|----------------------------------------------|
| RSA-2048-OAEP | Encrypting the AES key per recipient device  |
| AES-256-GCM   | Encrypting the message body                  |
| Web Crypto API| All crypto runs in the browser               |

**Hybrid encryption** is used because RSA can only encrypt ~245 bytes
at 2048-bit key size. The solution: encrypt the message with AES (fast,
any size), then encrypt the AES key with RSA (safe key exchange). The
recipient uses their RSA private key to unwrap the AES key, then uses
AES to decrypt the body.

---

## The five-step demo flow

### ① Setup devices
Both Phone and Laptop generate RSA key pairs locally in the browser.
Public keys are sent to the server. Private keys never leave the page.

### ② Phone approves Laptop
Simulates the QR code trust ceremony. Laptop is marked as a trusted
device on the account. Until this step, Laptop cannot receive messages.

### ③ Send old message (Phone only)
A message is encrypted *in the browser* for Phone only and sent to the
server as ciphertext. The server stores it. Laptop has no copy yet.

### ④ Laptop joins — sync
This is the most technically interesting step:

1. Laptop asks the server which messages it is missing
2. Phone fetches its own encrypted blob from the server
3. Phone decrypts it locally using its private key
4. Phone re-encrypts the plaintext using Laptop's public key
5. Phone sends the new ciphertext to the server
6. Laptop fetches and decrypts its copy

The server handles steps 1 and 5-6 as blind storage. It never sees the
plaintext at any point in this chain.

### ⑤ Send new message
The sender encrypts separately for both devices using their public keys,
producing two different ciphertexts from the same plaintext. Both devices
decrypt independently.

---

## Server breach simulation

Clicking **☠ Simulate Server Breach** calls `GET /api/attack/snapshot`,
which returns everything the server database contains:

- Device public keys
- Encrypted AES keys
- Encrypted message bodies

The overlay then shows a failed decryption attempt and explains why:
without device private keys, the encrypted AES keys cannot be unwrapped,
and the message bodies remain computationally infeasible to decrypt.

---

## Forward secrecy note

This demo uses static RSA identity keys — one key pair per device for
the lifetime of the session. Real systems like WhatsApp and Signal layer
the **Double Ratchet Algorithm** on top, which adds:

- **Signed prekeys** — medium-term keys uploaded to the server in advance
- **One-time prekeys** — single-use keys for session establishment
- **Ephemeral session keys** — new key pair generated per message
- **Forward secrecy** — old session keys are deleted after use, so
  compromising today's key does not expose yesterday's messages
- **Break-in recovery** — the ratchet advances forward, limiting the
  window of exposure if a key is ever stolen

The core guarantee demonstrated here — server never sees plaintext,
private keys never leave devices — is identical in both approaches.

---

## Running locally

**Requirements:** Python 3.11+, a modern browser (Web Crypto API)

```bash
# Clone and install
git clone https://github.com/yourname/e2ecrypto-demo
cd e2ecrypto-demo
pip install -r requirements.txt

# Run
uvicorn main:app --reload

# Open
http://localhost:8000
```

**requirements.txt**
fastapi
uvicorn[standard]
aiosqlite
cryptography
pydantic
---

## Key design decisions

**Why does the browser do all the crypto?**
Because that is what E2E means. If the server encrypted messages, it
would have access to the plaintext and the keys — defeating the purpose.
The Web Crypto API gives browsers access to native cryptographic
primitives that run in a sandboxed, non-exportable key store.

**Why store public keys on the server?**
Public keys are public by design. Anyone can have your public key — it
can only be used to *encrypt* data *to* you. Only your private key can
decrypt it, and that never leaves your device.

**Why are old messages re-encrypted by Phone and not the server?**
Because the server cannot decrypt them to re-encrypt them — it has no
private keys. The only entity that can read the old messages is the
device they were encrypted for. That device (Phone) must perform the
re-encryption step. This is exactly how WhatsApp handles linked devices.

---

## Educational use

This project is intended as a learning tool. It simplifies some aspects
of production E2E systems (no Double Ratchet, no prekey bundles, no
sealed sender) to keep the core concept visible and followable.

Do not use this code as the basis for a production encryption system.

---

## Tech stack

- **FastAPI** — async Python backend, WebSocket broadcast
- **aiosqlite** — async SQLite
- **Web Crypto API** — RSA-OAEP + AES-GCM, runs natively in the browser
- **Vanilla JS** — no frontend framework, keeping the crypto logic readable