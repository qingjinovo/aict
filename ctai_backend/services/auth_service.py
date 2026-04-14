"""
认证服务
提供 JWT Token 生成和验证功能
"""

import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app, g
from models.user import User

SECRET_KEY = 'ctai-jwt-secret-key'
ALGORITHM = 'HS256'


def generate_token(user_id, role, expires_in=24):
    """生成 JWT Token"""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expires_in),
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token):
    """解码 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """API 认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header:
            return jsonify({'success': False, 'error': '缺少认证信息'}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'success': False, 'error': '无效的认证格式'}), 401

        token = parts[1]
        payload = decode_token(token)

        if not payload:
            return jsonify({'success': False, 'error': '无效或已过期的 Token'}), 401

        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 401

        g.current_user = user
        g.user_role = payload['role']

        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """角色权限装饰器"""
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            if g.user_role not in roles:
                return jsonify({'success': False, 'error': '权限不足'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def get_current_user():
    """获取当前登录用户"""
    return getattr(g, 'current_user', None)


def get_current_role():
    """获取当前用户角色"""
    return getattr(g, 'user_role', None)
