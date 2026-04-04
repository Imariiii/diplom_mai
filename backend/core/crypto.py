"""
Модуль для шифрования и дешифрования паролей подключений к БД
Использует симметричное шифрование Fernet
"""
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_encryption_key() -> bytes:
    """Получить ключ шифрования из ENV или сгенерировать новый"""
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        print("[CRYPTO] Предупреждение: ENCRYPTION_KEY не установлен, генерируется новый ключ")
        print("[CRYPTO] Добавьте ENCRYPTION_KEY в .env файл для персистентности")
        key = Fernet.generate_key().decode()
        os.environ['ENCRYPTION_KEY'] = key
    else:
        key = key.encode()
    return key


_fernet_instance = None


def _get_fernet() -> Fernet:
    """Получить или создать экземпляр Fernet (ленивая инициализация)"""
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_encryption_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_password(plaintext: str) -> str:
    """
    Зашифровать пароль

    Args:
        plaintext: Пароль в открытом виде

    Returns:
        Зашифрованный пароль в base64
    """
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_password(encrypted: str) -> str:
    """
    Расшифровать пароль

    Args:
        encrypted: Зашифрованный пароль в base64

    Returns:
        Пароль в открытом виде

    Raises:
        ValueError: Если не удалось расшифровать
    """
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted.encode())
        return decrypted.decode()
    except InvalidToken as e:
        raise ValueError(f"Не удалось расшифровать пароль: возможно, изменился ENCRYPTION_KEY") from e
