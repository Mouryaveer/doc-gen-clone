from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from datetime import datetime, timedelta, timezone

NAME     = "Akshay Kumar"       # change to your name
PASSWORD = "123456"         # change to your password
OUTPUT   = "docgen/my_cert.pfx"  # where to save

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME,          NAME),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,    "Turn2Law"),
    x509.NameAttribute(NameOID.COUNTRY_NAME,         "IN"),
])
now = datetime.now(timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(subject).issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + timedelta(days=365))
    .add_extension(x509.KeyUsage(
        digital_signature=True, content_commitment=True,
        key_encipherment=False, data_encipherment=False,
        key_agreement=False, key_cert_sign=False,
        crl_sign=False, encipher_only=False, decipher_only=False,
    ), critical=True)
    .sign(key, hashes.SHA256())
)
p12 = pkcs12.serialize_key_and_certificates(
    name=NAME.encode(), key=key, cert=cert, cas=None,
    encryption_algorithm=serialization.BestAvailableEncryption(PASSWORD.encode()),
)
with open(OUTPUT, "wb") as f:
    f.write(p12)
print(f"Certificate saved: {OUTPUT}")
print(f"Password        : {PASSWORD}")
