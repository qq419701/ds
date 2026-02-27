import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def base64_encode(data: str) -> str:
    """Base64编码"""
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def base64_decode(data: str) -> str:
    """Base64解码（支持标准和URL安全格式）"""
    # 处理URL安全的Base64（替换字符并补齐填充）
    data = data.replace('-', '+').replace('_', '/')
    padding = (4 - len(data) % 4) % 4
    data += '=' * padding
    return base64.b64decode(data).decode('utf-8')


def aes_encrypt(data: str, key: str) -> str:
    """AES-256-ECB加密（通用交易卡密加密）
    注意：ECB模式为京东通用交易平台规范要求，不可更换为其他模式。
    """
    # 密钥补齐到32字节
    key_bytes = key.encode('utf-8')
    key_bytes = key_bytes[:32].ljust(32, b'\0')
    cipher = AES.new(key_bytes, AES.MODE_ECB)  # nosec - Required by JD platform spec
    encrypted = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(encrypted).decode('utf-8')


def aes_decrypt(data: str, key: str) -> str:
    """AES-256-ECB解密（ECB模式为京东平台规范要求）"""
    key_bytes = key.encode('utf-8')
    key_bytes = key_bytes[:32].ljust(32, b'\0')
    cipher = AES.new(key_bytes, AES.MODE_ECB)  # nosec - Required by JD platform spec
    decrypted = unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size)
    return decrypted.decode('utf-8')
