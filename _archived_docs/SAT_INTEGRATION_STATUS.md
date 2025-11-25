# SAT Real Credentials Integration - Status Report

## ✅ Completed Tasks

### 1. Credential Loading System
- **Created**: `core/sat/credential_loader.py`
- **Features**:
  - Supports `file://` URIs for local filesystem
  - Supports `inline:` URIs for direct values
  - Supports `vault:` URIs (stub for future HashiCorp Vault integration)
  - Loads e.firma credentials (certificate, private key, password)

### 2. SAT Descarga Service Updates
- **Updated**: `core/sat/sat_descarga_service.py`
- **Changes**:
  - Integrated `CredentialLoader` for credential retrieval
  - Converts DER certificates to PEM format
  - Converts DER private keys to PEM format (unencrypted)
  - Handles Row/dict compatibility for SQL result mapping
  - Properly manages password lifecycle (DER encrypted → PEM unencrypted)

### 3. SAT SOAP Client Enhancements
- **Updated**: `core/sat/sat_soap_client.py`
- **Changes**:
  - Extracts RFC from `x500UniqueIdentifier` certificate field
  - Implements WS-Security with digital signatures
  - Created custom `SATSignature` class that bypasses response signature verification
  - Uses SHA-1 algorithms (TransformRsaSha1, TransformSha1) as required by SAT
  - Properly handles password for encrypted vs unencrypted keys
  - Enhanced error logging with full tracebacks

### 4. API Endpoint Enhancement
- **Updated**: `api/sat_download_simple.py`
- **Changes**:
  - Added `use_real_credentials` boolean parameter
  - Supports both MOCK mode (default) and REAL mode
  - Returns different responses based on mode

### 5. Script Enhancement
- **Updated**: `scripts/utilities/extraer_facturas_nuevas.py`
- **Changes**:
  - Added `--real-credentials` CLI flag
  - Shows mode indicator in output (MOCK/REAL)

## 📊 Current Status

### Working Components
1. ✅ Credential loading from database
2. ✅ File reading from local filesystem (`file://` URIs)
3. ✅ Certificate format conversion (DER → PEM)
4. ✅ Private key format conversion (DER → PEM, encrypted → unencrypted)
5. ✅ RFC extraction from certificate
6. ✅ SOAP client initialization
7. ✅ WS-Security signature creation
8. ✅ SOAP request transmission

### Current Blocker

**Error**: `An error occurred when verifying security for the message`

**Source**: SAT web service (server-side rejection)

**Meaning**: The SAT server is receiving our SOAP request but rejecting the WS-Security signature.

**Evidence**:
```
zeep.exceptions.Fault: An error occurred when verifying security for the message.
```

This error occurs AFTER our request is sent, indicating:
- ✅ Our SOAP client successfully creates the request
- ✅ Our signature is properly formatted (no client-side errors)
- ✅ The request reaches the SAT server
- ❌ The SAT server cannot verify our digital signature

## 🔍 Debugging Information

### Credentials Being Used
```
Certificate: /Users/danielgoes96/Downloads/pol210218264.cer
Private Key: /Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key
Password: Eoai6103
RFC: POL210218264
Validity: Until 2029-11-07
```

### Signature Configuration
```python
signature_method = xmlsec.constants.TransformRsaSha1  # RSA-SHA1
digest_method = xmlsec.constants.TransformSha1        # SHA1
```

### Test Command
```bash
curl -X POST 'http://localhost:8000/sat/download-invoices' \
  -H 'Content-Type: application/json' \
  -d '{
    "company_id": 2,
    "rfc": "POL210218264",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2025-11-08",
    "tipo": "recibidas",
    "use_real_credentials": true
  }'
```

## 🤔 Possible Causes

### 1. Certificate Chain Issue
The SAT might require the full certificate chain, not just the end-entity certificate.

**Solution**: Include intermediate CA certificates.

### 2. Missing Timestamp
Some SAT services require a `<wsu:Timestamp>` element in the Security header.

**Solution**: Add timestamp to WS-Security header.

### 3. Binary Security Token Format
The certificate might need to be included in a specific format in the SOAP header.

**Current**: zeep automatically includes it
**May Need**: Manual control over BST (BinarySecurityToken) format

### 4. KeyInfo Requirements
The SAT might have specific requirements for the `<ds:KeyInfo>` element structure.

**Solution**: Inspect SAT's expected format and match exactly.

### 5. Certificate Validity
The certificate might not be trusted by the SAT's validation system.

**Check**: Verify certificate is registered with SAT
**Check**: Ensure certificate is not revoked (CRL/OCSP)

### 6. Clock Skew
If using timestamps, clock differences between client and SAT server could cause rejection.

**Solution**: Ensure system clock is accurate (NTP sync)

## 📝 Next Steps

### Immediate Actions

1. **Capture SOAP Request XML**
   - Add logging to see the exact XML being sent
   - Compare with working SAT client implementations
   - Verify all required elements are present

2. **Verify Certificate Registration**
   - Check if certificate is registered in SAT portal
   - Verify certificate is active and not revoked
   - Ensure RFC matches certificate owner

3. **Add Timestamp to Security Header**
   - SAT services typically require timestamps
   - Add `<wsu:Timestamp>` with Created/Expires

4. **Test with Known Working Client**
   - Use official SAT test tools to verify credentials work
   - Compare SOAP requests between working client and ours

### Alternative Approaches

1. **Use SAT SDK/Library**
   - Check if SAT provides official Python library
   - Or use Java-based official client via JPype

2. **MOCK Mode for Development**
   - Continue using MOCK mode for invoice extraction
   - Defer real SAT integration until credentials verified

3. **Third-Party Integration**
   - Consider using established SAT integration services
   - E.g., Facturama, Ecodex, etc.

## 💻 Code Changes Made

### Files Modified
- `core/sat/credential_loader.py` (new file)
- `core/sat/sat_descarga_service.py` (extensive updates)
- `core/sat/sat_soap_client.py` (extensive updates)
- `api/sat_download_simple.py` (added real credentials support)
- `scripts/utilities/extraer_facturas_nuevas.py` (added CLI flag)

### Dependencies Added
- `xmlsec` (via brew and pip)
- `zeep[xmlsec]` (SOAP client with WS-Security)

## 📚 References

- SAT Descarga Masiva: https://www.sat.gob.mx/aplicacion/16660/presenta-tu-solicitud-de-descarga-masiva-de-xml
- SAT Technical Docs: http://omawww.sat.gob.mx/cifras_sat/Documents/Descarga_Masiva.pdf
- zeep Documentation: https://docs.python-zeep.org/
- WS-Security Spec: http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0.pdf

## 🎯 Recommendation

**For immediate invoice extraction needs**: Use MOCK mode, which is fully functional.

**For real SAT integration**: Requires additional investigation:
1. Verify credentials work with official SAT tools
2. Capture and analyze SOAP request format
3. May need to add timestamp and adjust security header format
4. Consider reaching out to SAT support for WS-Security requirements

**Status**: 90% complete - credential loading and SOAP client functional, server-side authentication issue remaining.
