-- Database initialization script for dianshang order management system
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS dianshang DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE dianshang;

-- 1. shops table
CREATE TABLE IF NOT EXISTS shops (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_name VARCHAR(100) NOT NULL COMMENT '店铺名称',
    shop_code VARCHAR(50) UNIQUE NOT NULL COMMENT '店铺代码',
    shop_type TINYINT NOT NULL COMMENT '店铺类型：1=游戏点卡 2=通用交易',

    game_customer_id VARCHAR(50) COMMENT '游戏点卡客户ID',
    game_md5_secret VARCHAR(500) COMMENT '游戏点卡MD5密钥',
    game_direct_callback_url VARCHAR(500) COMMENT '游戏直充回调地址',
    game_card_callback_url VARCHAR(500) COMMENT '游戏卡密回调地址',
    game_api_url VARCHAR(500) COMMENT '游戏点卡接口地址',

    general_vendor_id VARCHAR(50) COMMENT '通用交易商家ID',
    general_md5_secret VARCHAR(500) COMMENT '通用交易MD5密钥',
    general_aes_secret VARCHAR(500) COMMENT '通用交易AES密钥',
    general_callback_url VARCHAR(500) COMMENT '通用交易回调地址',
    general_api_url VARCHAR(500) COMMENT '通用交易接口地址',

    agiso_enabled TINYINT DEFAULT 0 COMMENT '是否启用阿奇索：0=否 1=是',
    agiso_host VARCHAR(100) COMMENT '阿奇索主机地址',
    agiso_port INT COMMENT '阿奇索端口',
    agiso_app_id VARCHAR(100) COMMENT '阿奇索应用ID',
    agiso_app_secret VARCHAR(500) COMMENT '阿奇索应用密钥',
    agiso_access_token VARCHAR(500) COMMENT '阿奇索访问令牌',

    notify_enabled TINYINT DEFAULT 0 COMMENT '是否启用订单通知：0=否 1=是',
    dingtalk_webhook VARCHAR(500) COMMENT '钉钉机器人Webhook地址',
    dingtalk_secret VARCHAR(500) COMMENT '钉钉机器人加签密钥',
    wecom_webhook VARCHAR(500) COMMENT '企业微信机器人Webhook地址',

    auto_deliver TINYINT DEFAULT 0 COMMENT '发货方式：0=手动发货 1=自动发货',

    is_enabled TINYINT DEFAULT 1 COMMENT '是否启用：0=禁用 1=启用',
    expire_time DATETIME COMMENT '到期时间',
    remark VARCHAR(500) COMMENT '备注',

    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_shop_type (shop_type),
    INDEX idx_enabled (is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='店铺表';

-- 2. orders table
CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no VARCHAR(64) UNIQUE NOT NULL COMMENT '我方订单号',
    jd_order_no VARCHAR(64) NOT NULL COMMENT '京东订单号',

    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    shop_type TINYINT NOT NULL COMMENT '店铺类型：1=游戏点卡 2=通用交易',
    order_type TINYINT NOT NULL COMMENT '订单类型：1=直充 2=卡密',

    order_status TINYINT DEFAULT 0 COMMENT '订单状态：0=待支付 1=处理中 2=已完成 3=已取消',

    sku_id VARCHAR(64) COMMENT '商品SKU',
    product_info TEXT COMMENT '商品信息',
    amount BIGINT NOT NULL COMMENT '金额（分）',
    quantity INT DEFAULT 1 COMMENT '数量',

    produce_account VARCHAR(255) COMMENT '充值账号',

    card_info TEXT COMMENT '卡密信息JSON',

    notify_url VARCHAR(500) COMMENT '回调地址',
    notify_status TINYINT DEFAULT 0 COMMENT '回调状态：0=未回调 1=成功 2=失败',
    notify_time DATETIME COMMENT '回调时间',

    notified TINYINT DEFAULT 0 COMMENT '是否已发送通知：0=否 1=是',
    notify_send_time DATETIME COMMENT '通知发送时间',

    pay_time DATETIME COMMENT '支付时间',
    deliver_time DATETIME COMMENT '发货时间',

    remark VARCHAR(500) COMMENT '备注',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_jd_order (jd_order_no, shop_type),
    INDEX idx_shop (shop_id, order_status),
    INDEX idx_create_time (create_time),
    INDEX idx_notified (notified, create_time),

    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 3. users table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    name VARCHAR(100) COMMENT '姓名',

    role VARCHAR(20) NOT NULL DEFAULT 'operator' COMMENT '角色：admin=管理员 operator=操作员',

    can_view_order TINYINT DEFAULT 1 COMMENT '查看订单权限',
    can_deliver TINYINT DEFAULT 0 COMMENT '发货权限',
    can_refund TINYINT DEFAULT 0 COMMENT '退款权限',

    is_active TINYINT DEFAULT 1 COMMENT '是否激活',
    last_login DATETIME COMMENT '最后登录时间',

    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 4. user_shop_permissions table
CREATE TABLE IF NOT EXISTS user_shop_permissions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',

    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_user_shop (user_id, shop_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户店铺权限表';

-- 5. notification_logs table
CREATE TABLE IF NOT EXISTS notification_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL COMMENT '订单ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',

    notify_type VARCHAR(20) NOT NULL COMMENT '通知类型：dingtalk/wecom',
    notify_status TINYINT DEFAULT 0 COMMENT '通知状态：0=失败 1=成功',

    request_data TEXT COMMENT '请求数据',
    response_data TEXT COMMENT '响应数据',
    error_message TEXT COMMENT '错误信息',

    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_order (order_id),
    INDEX idx_shop (shop_id),
    INDEX idx_create_time (create_time),

    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通知日志表';

-- 6. api_logs table
CREATE TABLE IF NOT EXISTS api_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id BIGINT COMMENT '店铺ID',
    api_type VARCHAR(50) COMMENT '接口类型',
    request_method VARCHAR(10) COMMENT '请求方法',
    request_url VARCHAR(500) COMMENT '请求URL',
    request_headers TEXT COMMENT '请求头',
    request_body TEXT COMMENT '请求体',
    response_status INT COMMENT '响应状态码',
    response_body TEXT COMMENT '响应体',
    ip_address VARCHAR(50) COMMENT '请求IP',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_shop (shop_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API日志表';

-- 7. operation_logs table
CREATE TABLE IF NOT EXISTS operation_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL COMMENT '操作人用户名',
    action VARCHAR(50) NOT NULL COMMENT '操作类型',
    target_type VARCHAR(50) COMMENT '操作对象类型',
    target_id INT COMMENT '操作对象ID',
    detail TEXT COMMENT '操作详情',
    ip_address VARCHAR(50) COMMENT '操作IP',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_user (user_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志表';

-- Insert default admin user (password: admin123)
INSERT INTO users (username, password_hash, name, role, can_view_order, can_deliver, can_refund, is_active)
VALUES ('admin', 'scrypt:32768:8:1$placeholder$placeholder', '超级管理员', 'admin', 1, 1, 1, 1)
ON DUPLICATE KEY UPDATE username=username;
