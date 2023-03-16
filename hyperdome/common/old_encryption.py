import base64
import functools
import logging


from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.asymmetric.x448 import X448PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import cryptography.hazmat.primitives.serialization as serial


class LockBox:
    """
    handle key storage, generation, exchange,
    encryption and decryption
    """

    __log = logging.getLogger(__name__)

    _HASH = hashes.SHA3_512()
    _ENCODING = serial.Encoding.PEM
    _BACKEND = default_backend()
    _PUBLIC_FORMAT = serial.PublicFormat.SubjectPublicKeyInfo
    _PRIVATE_FORMAT = serial.PrivateFormat.PKCS8
    _RATCHET_KDF = functools.partial(
        HKDF, _HASH, 64, salt=None, info=b"ratchet increment", backend=_BACKEND
    )

    def __init__(self):
        self._chat_key = None
        self._signing_key = None
        self._send_ratchet_key = None
        self._recieve_ratchet_key = None

    def encrypt_outgoing_message(self, message: bytes) -> str:

        new_base_key = self._RATCHET_KDF().derive(self._send_ratchet_key)
        self._send_ratchet_key = new_base_key[:32]
        fernet_key = base64.urlsafe_b64encode(new_base_key[32:])
        ciphertext = Fernet(fernet_key).encrypt(message)
        return ciphertext.decode("utf-8")

    def decrypt_incoming_message(self, message: bytes) -> str:

        new_base_key = self._RATCHET_KDF().derive(self._recieve_ratchet_key)
        self._recieve_ratchet_key = new_base_key[:32]
        fernet_key = base64.urlsafe_b64encode(new_base_key[32:])
        plaintext = Fernet(fernet_key).decrypt(message)
        return plaintext.decode("utf-8")

    @property
    def public_chat_key(self) -> str:
        """
        return a PEM encoded serialized public key digest
        of a new ephemeral X448 key
        """
        self.__log.info("generating new public key")
        self._send_ratchet_key = None
        self._recieve_ratchet_key = None

        self._chat_key = X448PrivateKey.generate()
        pub_key_bytes = self._chat_key.public_key().public_bytes(
            self._ENCODING, self._PUBLIC_FORMAT
        )
        return pub_key_bytes.decode("utf-8")

    @property
    def public_signing_key(self) -> str:
        """
        return a PEM encoded serialized public key digest
        of the ed448 signing key
        """
        key = self._signing_key.public_key()
        key_bytes = key.public_bytes(self._ENCODING, self._PUBLIC_FORMAT)
        return key_bytes.decode("utf-8")

    def perform_key_exchange(self, public_key_bytes: bytes, chirality: bool):
        """
        ingest a PEM encoded public key and generate a symmetric key
        created by a Diffie-Helman key exchange result being passed into
        a key-derivation and used to create a fernet instance
        """
        public_key = serial.load_pem_public_key(public_key_bytes, self._BACKEND)
        shared = self._chat_key.exchange(public_key)
        # TODO consider customizing symmetric encryption for larger key or authentication
        new_chat_key = self._RATCHET_KDF().derive(shared)
        if chirality:
            send_slice = slice(None, 32)
            recieve_slice = slice(32, None)
        else:
            send_slice = slice(32, None)
            recieve_slice = slice(None, 32)
        self._send_ratchet_key = new_chat_key[send_slice]
        self._recieve_ratchet_key = new_chat_key[recieve_slice]

    def make_signing_key(self):
        self._signing_key = Ed448PrivateKey.generate()

    def sign_message(self, message: bytes) -> str:
        sig = self._signing_key.sign(message)
        return base64.urlsafe_b64encode(sig).decode("utf-8")

    def export_key(self, passphrase: bytes):
        key_bytes = self._signing_key.private_bytes(
            self._ENCODING,
            self._PRIVATE_FORMAT,
            serial.BestAvailableEncryption(passphrase),
        )
        return base64.urlsafe_b64encode(key_bytes).decode("utf-8")

    def import_key(self, key_bytes: bytes, passphrase: bytes):
        key_bytes = base64.urlsafe_b64decode(key_bytes)
        self._signing_key = serial.load_pem_private_key(
            key_bytes, passphrase, self._BACKEND
        )
