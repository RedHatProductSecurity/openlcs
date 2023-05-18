import hashlib
import json

from cryptography.fernet import Fernet


def encrypt_with_secret_key(message: str, secret_key: str) -> str:
    """
    encrypt string with django secret key
    """
    fernet = Fernet(secret_key)
    enc_message = fernet.encrypt(message.encode())

    return enc_message.decode()


def decrypt_with_secret_key(enc_message: str, secret_key: str) -> str:
    """
    decrypt string with django secret key
    """
    fernet = Fernet(secret_key)
    dec_message = fernet.decrypt(enc_message).decode()

    return dec_message
