import hashlib


def game_sign(params: dict, private_key: str) -> str:
    """
    游戏点卡签名算法
    规则: key1=value1&key2=value2&...privatekey (ASCII升序排列key，末尾追加私钥，无&)
    """
    sorted_items = sorted(params.items())
    parts = [f"{k}={v}" for k, v in sorted_items]
    plain = "&".join(parts) + private_key
    return hashlib.md5(plain.encode('utf-8')).hexdigest()


def general_sign(params: dict, private_key: str) -> str:
    """
    通用交易签名算法
    规则: key1value1key2value2...PRIVATEKEY (ASCII升序，直接拼接无=无&，末尾加私钥)
    排除 sign 和 signType 字段
    """
    exclude = {'sign', 'signType'}
    sorted_items = sorted((k, v) for k, v in params.items() if k not in exclude)
    plain = "".join(f"{k}{v}" for k, v in sorted_items) + private_key
    return hashlib.md5(plain.encode('utf-8')).hexdigest()


def agiso_sign(params: dict, app_secret: str) -> str:
    """
    阿奇索签名算法
    规则: MD5(AppSecret + key1value1key2value2... + AppSecret) (ASCII升序，排除sign)
    """
    exclude = {'sign'}
    sorted_items = sorted((k, v) for k, v in params.items() if k not in exclude)
    plain = app_secret + "".join(f"{k}{v}" for k, v in sorted_items) + app_secret
    return hashlib.md5(plain.encode('utf-8')).hexdigest()


def verify_game_sign(params: dict, private_key: str) -> bool:
    """验证游戏点卡签名"""
    received_sign = params.get('sign', '')
    params_without_sign = {k: v for k, v in params.items() if k != 'sign'}
    expected_sign = game_sign(params_without_sign, private_key)
    return received_sign == expected_sign


def verify_general_sign(params: dict, private_key: str) -> bool:
    """验证通用交易签名"""
    received_sign = params.get('sign', '')
    expected_sign = general_sign(params, private_key)
    return received_sign == expected_sign
