## What This Demonstrates

Most explanations of end-to-end encryption stop at:

> "The server cannot read your messages."

This demo shows exactly why that is true and what happens when a new device joins an existing account.

You'll see:

- RSA-2048 key pairs generated locally in the browser
- Messages encrypted on the client before transmission
- The server receiving and storing only ciphertext
- A new device joining later and receiving old messages without the server seeing plaintext
- A simulated server breach showing why stolen encrypted data remains unreadable
- Simplified explanations of concepts used by real systems such as forward secrecy and the Double Ratchet algorithm

---

## Architecture

The server is structurally blind. It stores encrypted blobs indexed by device ID and serves them back on request.

The server has:

- No private keys
- No plaintext
- No session keys
- Only public keys and ciphertext

### High-Level Flow

Sender Browser
→ Encrypt locally with RSA-OAEP + AES-GCM

Server
→ Store ciphertext only

Recipient Browser
→ Decrypt locally using private key

Readable plaintext

---

## The Six-Step Demo Flow

### Step 1: Setup Phone

The phone creates its identity locally.

- Generate RSA key pair in the browser
- Upload public key to server
- Keep private key on device

Server stores:

✓ Public key

Server never stores:

✗ Private key
✗ Plaintext

---

### Step 2: Send Old Message

Alice sends:

"Hello Kevin"

Message flow:

Alice Browser
→ Generate AES key
→ Encrypt message with AES-GCM
→ Encrypt AES key using Phone public key
→ Send encrypted data to server

Phone:

→ Decrypt AES key using private key
→ Decrypt message locally

Laptop:

Does not exist yet

---

### Step 3: Setup Laptop

Laptop joins after messages already exist.

Laptop:

- Generate local RSA key pair
- Generate QR payload containing device identity
- Present QR for approval

Phone:

- Scan QR
- Verify Laptop identity
- Approve Laptop

Server:

- Store Laptop public key

---

### Step 4: Sync Old Messages

This is the core idea of the demo.

Phone already has access to the old message:

1. Phone requests its encrypted copy
2. Phone decrypts locally
3. Phone encrypts the message again using Laptop's public key
4. Phone sends the new encrypted blob to server
5. Laptop downloads and decrypts

Important:

The server never sees plaintext during any part of this process.

---

### Step 5: Send New Message

Alice sends:

"Hey Kevin"

Now both devices exist.

Alice encrypts separately for:

- Phone
- Laptop

Result:

Phone → decrypts locally

Laptop → decrypts locally

Two encrypted blobs.

One original message.

---

### Step 6: Simulate Server Breach

Attacker steals:

✓ Public keys  
✓ Encrypted blobs  
✓ Database contents

Attacker does NOT have:

✗ Phone private key  
✗ Laptop private key

Result:

Encrypted data remains unreadable.
