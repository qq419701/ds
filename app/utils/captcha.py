"""图形验证码生成工具"""
import random
import string
import base64
from io import BytesIO
from captcha.image import ImageCaptcha


def generate_captcha():
    """生成验证码，返回 (验证码文本, base64编码的图片)"""
    chars = random.choices(string.ascii_uppercase + string.digits, k=4)
    code = ''.join(chars)
    image = ImageCaptcha(width=160, height=60)
    data = image.generate(code)
    b64 = base64.b64encode(data.read()).decode('utf-8')
    return code, f'data:image/png;base64,{b64}'
