# Turn2Law — System Workflow

## Complete End-to-End Pipeline

```
User Input (fields / reference document)
            │
            ▼
  Text Extraction          ← PyMuPDF · python-docx · Tesseract OCR
            │
            ▼
  AI Classification        ← Google Gemini 2.5 Flash  (or skipped via generate_direct)
            │
            ▼
  Schema Validation        ← schema.py
            │
            ▼
  Template Rendering       ← {{placeholder}} substitution + LaTeX escaping
            │
            ▼
  XeLaTeX × 2 passes       ← TikZ overlays require two passes
            │
            ▼
  ┌─────────────────┐
  │   Unsigned PDF  │
  └────────┬────────┘
           │
           ▼
  ┌────────────────────────────────────┐
  │   Digital Signature Engine         │
  │                                    │
  │   1. Load Certificate              │
  │      SimpleSigner.load_pkcs12()    │
  │      .pfx / .p12  +  password      │
  │                                    │
  │   2. Validate Certificate          │
  │      Expiry check                  │
  │      Key-usage check               │
  │      Algorithm check               │
  │                                    │
  │   3. Build Metadata                │
  │      signer_name, reason,          │
  │      location, contact,            │
  │      signing_time (UTC)            │
  │                                    │
  │   4. Hash PDF                      │
  │      SHA-256                       │
  │                                    │
  │   5. Sign Hash                     │
  │      Private key (RSA / ECDSA)     │
  │      PKCS#7 / CMS signature        │
  │                                    │
  │   6. Embed Signature               │
  │      Incremental PDF update        │
  │      PAdES-compliant               │
  │      Visible annotation (optional) │
  │                                    │
  │   7. Timestamp (optional)          │
  │      RFC 3161 TSA                  │
  │                                    │
  │   8. Dispose key material          │
  └────────┬───────────────────────────┘
           │
           ▼
  ┌─────────────────┐
  │   Signed PDF    │──────► Download / Email / Archive
  └─────────────────┘
           │
           ▼
  Verification (on demand)
     ├─ Signature intact?
     ├─ Certificate valid?
     ├─ Timestamp valid?
     └─ Result: VALID / MODIFIED / CERT_EXPIRED / ...
```

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `app.py` | Orchestration — calls generation then optionally signing |
| `digital_signature/signer.py` | Public API facade — `sign_document()`, `sign_pdf_file()` |
| `digital_signature/certificate_loader.py` | Load PKCS#12 into `CertificateBundle` |
| `digital_signature/certificate_validator.py` | Expiry, key-usage, algorithm checks |
| `digital_signature/metadata.py` | `SignatureMetadata` data model |
| `digital_signature/pdf_signer.py` | pyHanko integration — actual signing |
| `digital_signature/timestamp.py` | RFC 3161 TSA client builder |
| `digital_signature/verification.py` | Verify embedded signatures |
| `digital_signature/signature_config.py` | All tunable defaults |
| `digital_signature/exceptions.py` | Domain exception hierarchy |
| `digital_signature/utils.py` | File helpers, hashing, sanitisation |

## Certificate Lifecycle

```
Certificate File (.pfx/.p12)
          │
          ▼
   load_certificate()        ← reads bytes, decrypts with password
          │
          ▼
   CertificateBundle         ← private_key + certificate + chain
          │
          ▼
   validate_certificate()    ← expiry / key-usage / algorithm checks
          │
          ▼
   sign_pdf()                ← private key used here only
          │
          ▼
   bundle.dispose()          ← private_key reference cleared
```

**Private key rule**: The key never leaves memory.  It is never serialised,
never logged, and the reference is cleared immediately after signing.

## Visible Signature Appearance

```
┌────────────────────────────────────────────────────────────┐
│  Digitally signed by JAGJYOT SINGH                         │
│  Date: 2026.07.10 11:05:03 +00'00'                         │
│  Reason: Approved                                          │
│  Location: Chennai, India                                  │
└────────────────────────────────────────────────────────────┘
```

- Clean text box — no cursive/handwritten watermark
- Coordinates configurable via `VisibleSignatureConfig`
- Default placement: bottom-left of last page

## Future Roadmap

| Phase | Feature |
|-------|---------|
| Phase 2 | USB DSC tokens (ePass2003, ProxKey) via PKCS#11 |
| Phase 2 | HSM-backed signing |
| Phase 3 | Multi-signer sequential workflows |
| Phase 3 | Role-based approval chains |
| Phase 4 | CRL / OCSP certificate revocation checking |
| Phase 4 | Long-Term Validation (LTV) |
| Phase 4 | Government eSign providers (eMudhra, CDAC) |
| Phase 5 | Verification portal (web UI) |
| Phase 5 | Audit log integration |
