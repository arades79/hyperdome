"""
Ed25519 to X25519 conversions

Modified from https://github.com/pyca/cryptography/issues/5557#issuecomment-1202986332
"""

from cryptography.exceptions import UnsupportedAlgorithm, _Reasons
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fe25519 import fe25519
from ge25519 import ge25519, ge25519_p3


def x25519_from_ed25519_private_key(
    private_key: Ed25519PrivateKey,
) -> X25519PrivateKey:
    if not backend.x25519_supported():
        raise UnsupportedAlgorithm(
            "X25519 is not supported by this version of OpenSSL.",
            _Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM,
        )

    private_bytes = private_key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )

    hasher = hashes.Hash(hashes.SHA512())
    hasher.update(private_bytes)
    h = bytearray(hasher.finalize())
    # curve25519 clamping
    h[0] &= 248
    h[31] &= 127
    h[31] |= 64

    return X25519PrivateKey.from_private_bytes(h[0:32])


def x25519_from_ed25519_public_key(public_key: Ed25519PublicKey) -> X25519PublicKey:
    if not backend.x25519_supported():
        raise UnsupportedAlgorithm(
            "X25519 is not supported by this version of OpenSSL.",
            _Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM,
        )

    public_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    # This is libsodium's crypto_sign_ed25519_pk_to_curve25519 translated into
    # the Pyton module ge25519.
    if ge25519.has_small_order(public_bytes) != 0:
        raise ValueError("Doesn't have small order")

    # frombytes in libsodium appears to be the same as
    # frombytes_negate_vartime; as ge25519 only implements the from_bytes
    # version, we have to do the root check manually.
    A = ge25519_p3.from_bytes(public_bytes)
    if A.root_check:
        raise ValueError("Root check failed")

    if not A.is_on_main_subgroup():
        raise ValueError("It's on the main subgroup")

    one_minus_y = fe25519.one() - A.Y
    x = A.Y + fe25519.one()
    x = x * one_minus_y.invert()

    return X25519PublicKey.from_public_bytes(x.to_bytes())
