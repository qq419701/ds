from flask import current_app


ALLOWED_IPS = ['59.110.9.236']  # 京东服务器IP白名单


def check_ip(request) -> bool:
    """验证请求IP是否在白名单中"""
    # 如果配置了跳过IP验证，直接通过
    if current_app.config.get('SKIP_IP_VERIFY', False):
        return True

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()

    allowed = current_app.config.get('ALLOWED_IPS', ALLOWED_IPS)
    return client_ip in allowed
