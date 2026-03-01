from datetime import datetime
from app.extensions import db


class ApiLog(db.Model):
    __tablename__ = 'api_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id', ondelete='SET NULL'), nullable=True)
    api_type = db.Column(db.String(50), comment='接口类型')
    request_method = db.Column(db.String(10), comment='请求方法')
    request_url = db.Column(db.String(500), comment='请求URL')
    request_headers = db.Column(db.Text, comment='请求头')
    request_body = db.Column(db.Text, comment='请求体')
    response_status = db.Column(db.Integer, comment='响应状态码')
    response_body = db.Column(db.Text, comment='响应体')
    ip_address = db.Column(db.String(50), comment='请求IP')
    create_time = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'shop_id': self.shop_id,
            'api_type': self.api_type,
            'request_method': self.request_method,
            'request_url': self.request_url,
            'request_headers': self.request_headers,
            'request_body': self.request_body,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'ip_address': self.ip_address,
        }
