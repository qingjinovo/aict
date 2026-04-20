"""
认证 API 路由
提供 JWT Token 认证接口
"""

from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from models.user import User
from extensions import db
from services.auth_service import generate_token, decode_token, require_auth, get_current_user, get_current_role
import logging

logger = logging.getLogger(__name__)

auth_api_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')


@auth_api_bp.route('/login', methods=['POST'])
def api_login():
    """
    API 登录接口

    Request JSON:
    {
        "login_type": "doctor" | "patient",
        "employee_id": "D001",      # 医生登录
        "password": "xxx",           # 医生密码
        "phone": "13900000001",      # 患者登录
        "verify_code": "123456"      # 患者验证码
    }

    Returns:
    {
        "success": true,
        "token": "jwt_token",
        "user": {
            "id": 1,
            "username": "doctor_li",
            "role": "doctor",
            "full_name": "李医生"
        }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    login_type = data.get('login_type', 'doctor')

    if login_type == 'doctor':
        employee_id = data.get('employee_id', '')
        password = data.get('password', '')

        if not employee_id or not password:
            return jsonify({'success': False, 'error': '工号和密码不能为空'}), 400

        user = User.query.filter_by(employee_id=employee_id, role='doctor').first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            token = generate_token(user.id, 'doctor')

            return jsonify({
                'success': True,
                'token': token,
                'user': user.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': '工号或密码错误'}), 401

    else:
        phone = data.get('phone', '')
        verify_code = data.get('verify_code', '')

        if not phone:
            return jsonify({'success': False, 'error': '手机号不能为空'}), 400

        user = User.query.filter_by(phone=phone, role='patient').first()

        if user:
            login_user(user)
            token = generate_token(user.id, 'patient')

            return jsonify({
                'success': True,
                'token': token,
                'user': user.to_dict()
            })
        else:
            session_code = '123456'

            if verify_code != session_code:
                return jsonify({'success': False, 'error': '验证码错误'}), 401

            user = User(
                username=f'patient_{phone[-4:]}',
                email=f'{phone}@patient.local',
                phone=phone,
                role='patient',
                full_name=f'患者{phone[-4:]}'
            )
            user.set_password('patient123')
            db.session.add(user)
            db.session.commit()

            login_user(user)
            token = generate_token(user.id, 'patient')

            return jsonify({
                'success': True,
                'token': token,
                'user': user.to_dict()
            })


@auth_api_bp.route('/logout', methods=['POST'])
@require_auth
def api_logout():
    """API 登出接口"""
    from flask import session
    logout_user()
    session.clear()
    return jsonify({'success': True, 'message': '登出成功'})


@auth_api_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """获取当前用户信息"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': '用户未登录'}), 401

    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@auth_api_bp.route('/refresh', methods=['POST'])
@require_auth
def refresh_token():
    """刷新 Token"""
    user = get_current_user()
    role = get_current_role()

    if not user:
        return jsonify({'success': False, 'error': '用户未登录'}), 401

    new_token = generate_token(user.id, role)

    return jsonify({
        'success': True,
        'token': new_token
    })


@auth_api_bp.route('/verify', methods=['GET'])
def verify_token():
    """验证 Token 是否有效"""
    auth_header = request.headers.get('Authorization', '')

    if not auth_header:
        return jsonify({'success': False, 'valid': False, 'error': '无 Token'})

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return jsonify({'success': False, 'valid': False, 'error': '无效格式'})

    token = parts[1]
    payload = decode_token(token)

    if not payload:
        return jsonify({'success': False, 'valid': False, 'error': '无效或已过期'})

    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({'success': False, 'valid': False, 'error': '用户不存在'})

    return jsonify({
        'success': True,
        'valid': True,
        'user': user.to_dict(),
        'role': payload['role']
    })
