"""
后端系统全面测试脚本
测试所有 API 端点、功能、集成、边界情况和安全性
"""

import json
import sys
import os
import tempfile
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, init_database
from models.user import User
from models.annotation import AnnotationSet, Annotation, AnnotationType, AnnotationCategory, SeverityLevel, WorkflowStatus
from extensions import db


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.warnings = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name, reason):
        self.failed += 1
        self.errors.append({
            'test': name,
            'reason': reason,
            'severity': 'HIGH'
        })
        print(f"  [FAIL] {name}: {reason}")

    def add_warning(self, name, reason):
        self.warnings.append({
            'test': name,
            'reason': reason,
            'severity': 'MEDIUM'
        })
        print(f"  [WARN] {name}: {reason}")

    def summary(self):
        print("\n" + "="*60)
        print(f"测试结果: {self.passed} 通过, {self.failed} 失败, {len(self.warnings)} 警告")
        print("="*60)


def test_api_endpoints():
    """测试所有 API 端点是否正确注册"""
    print("\n[1] API 端点注册测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')

    expected_endpoints = [
        ('/api/auth/login', ['POST']),
        ('/api/auth/logout', ['POST']),
        ('/api/auth/me', ['GET']),
        ('/api/auth/verify', ['GET']),
        ('/api/ct-images', ['GET', 'POST']),
        ('/api/sam3d/health', ['GET']),
        ('/api/sam3d/model-info', ['GET']),
        ('/api/sam3d/infer', ['POST']),
        ('/api/annotation/sets', ['GET', 'POST']),
    ]

    with app.app_context():
        for rule in app.url_map.iter_rules():
            if 'api' in rule.rule:
                methods = [m for m in rule.methods if m not in ['OPTIONS', 'HEAD']]
                print(f"  发现端点: {','.join(methods)} {rule.rule}")

    for endpoint, expected_methods in expected_endpoints:
        found = False
        for rule in app.url_map.iter_rules():
            if rule.rule == endpoint:
                methods = [m for m in rule.methods if m not in ['OPTIONS', 'HEAD']]
                if set(methods) >= set(expected_methods):
                    result.add_pass(f"{endpoint}")
                else:
                    result.add_fail(f"{endpoint}", f"方法不匹配，期望 {expected_methods}, 实际 {methods}")
                found = True
                break
        if not found:
            result.add_fail(f"{endpoint}", "端点未注册")

    result.summary()
    return result


def test_authentication_flow():
    """测试认证流程"""
    print("\n[2] 认证流程测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        init_database(app)
        client = app.test_client()

        print("\n  2.1 医生登录测试")
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': 'D001',
            'password': 'doctor123'
        })
        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success') and data.get('token'):
                result.add_pass("医生登录成功")
                doctor_token = data['token']

                print("\n  2.2 Token 验证测试")
                response = client.get('/api/auth/verify', headers={
                    'Authorization': f'Bearer {doctor_token}'
                })
                if response.status_code == 200:
                    result.add_pass("Token 验证成功")
                else:
                    result.add_fail("Token 验证", f"状态码: {response.status_code}")

                print("\n  2.3 获取当前用户测试")
                response = client.get('/api/auth/me', headers={
                    'Authorization': f'Bearer {doctor_token}'
                })
                if response.status_code == 200:
                    data = json.loads(response.data)
                    if data.get('user', {}).get('role') == 'doctor':
                        result.add_pass("获取当前用户成功")
                    else:
                        result.add_fail("获取当前用户", "角色不匹配")
                else:
                    result.add_fail("获取当前用户", f"状态码: {response.status_code}")
            else:
                result.add_fail("医生登录", f"响应: {data}")
        else:
            result.add_fail("医生登录", f"状态码: {response.status_code}")

        print("\n  2.4 患者登录测试")
        response = client.post('/api/auth/login', json={
            'login_type': 'patient',
            'phone': '13900000001',
            'verify_code': '123456'
        })
        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success') and data.get('token'):
                result.add_pass("患者登录成功")
            else:
                result.add_fail("患者登录", f"响应: {data}")
        else:
            result.add_fail("患者登录", f"状态码: {response.status_code}")

        print("\n  2.5 错误登录测试")
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': 'D001',
            'password': 'wrongpassword'
        })
        if response.status_code == 401:
            result.add_pass("错误密码正确拒绝")
        else:
            result.add_fail("错误密码拒绝", f"状态码应为 401, 实际: {response.status_code}")

        print("\n  2.6 缺少字段登录测试")
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor'
        })
        if response.status_code == 400:
            result.add_pass("缺少字段正确拒绝")
        else:
            result.add_warning("缺少字段拒绝", f"状态码: {response.status_code}")

    result.summary()
    return result


def test_annotation_api():
    """测试标注 API"""
    print("\n[3] 标注 API 测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        init_database(app)
        client = app.test_client()

        doctor_response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': 'D001',
            'password': 'doctor123'
        })
        doctor_token = json.loads(doctor_response.data)['token']

        print("\n  3.1 创建标注集")
        response = client.post('/api/annotation/sets',
            headers={'Authorization': f'Bearer {doctor_token}'},
            json={
                'set_id': 'test_set_001',
                'ct_image_id': 'img_001',
                'name': '测试标注集'
            }
        )
        if response.status_code in [200, 201]:
            result.add_pass("创建标注集成功")
            set_id = json.loads(response.data).get('data', {}).get('annotation_set_id') or 'test_set_001'
        else:
            result.add_fail("创建标注集", f"状态码: {response.status_code}")
            set_id = 'test_set_001'

        print("\n  3.2 获取标注集")
        response = client.get(f'/api/annotation/sets/{set_id}',
            headers={'Authorization': f'Bearer {doctor_token}'}
        )
        if response.status_code == 200:
            result.add_pass("获取标注集成功")
        else:
            result.add_fail("获取标注集", f"状态码: {response.status_code}")

        print("\n  3.3 创建标注")
        response = client.post(f'/api/annotation/sets/{set_id}/annotations',
            headers={'Authorization': f'Bearer {doctor_token}'},
            json={
                'type': 'polygon',
                'points': [{'x': 100, 'y': 200}, {'x': 150, 'y': 180}, {'x': 180, 'y': 220}],
                'label': '测试结节',
                'category': 'lesion',
                'severity': 'medium',
                'slice_index': 50
            }
        )
        if response.status_code in [200, 201]:
            result.add_pass("创建标注成功")
        else:
            result.add_fail("创建标注", f"状态码: {response.status_code}, 响应: {response.data}")

        print("\n  3.4 按切片获取标注")
        response = client.get(f'/api/annotation/sets/{set_id}/slices/50',
            headers={'Authorization': f'Bearer {doctor_token}'}
        )
        if response.status_code == 200:
            result.add_pass("按切片获取标注成功")
        else:
            result.add_fail("按切片获取标注", f"状态码: {response.status_code}")

        print("\n  3.5 导出标注集")
        response = client.get(f'/api/annotation/sets/{set_id}/export?format=json',
            headers={'Authorization': f'Bearer {doctor_token}'}
        )
        if response.status_code == 200:
            result.add_pass("导出标注集成功")
        else:
            result.add_fail("导出标注集", f"状态码: {response.status_code}")

    result.summary()
    return result


def test_sam3d_api():
    """测试 SAM3D 模型 API"""
    print("\n[4] SAM3D API 测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        client = app.test_client()

        print("\n  4.1 健康检查")
        response = client.get('/api/sam3d/health')
        if response.status_code == 200:
            result.add_pass("健康检查成功")
        else:
            result.add_fail("健康检查", f"状态码: {response.status_code}")

        print("\n  4.2 获取模型信息")
        response = client.get('/api/sam3d/model-info')
        if response.status_code == 200:
            data = json.loads(response.data)
            if data.get('success'):
                result.add_pass("获取模型信息成功")
            else:
                result.add_warning("获取模型信息", f"模型可能未加载: {data}")
        else:
            result.add_fail("获取模型信息", f"状态码: {response.status_code}")

        print("\n  4.3 简化推理（无文件）")
        response = client.post('/api/sam3d/infer-simple', json={
            'image_path': '/nonexistent/path.nii.gz'
        })
        if response.status_code in [200, 400, 404, 500]:
            data = json.loads(response.data)
            if not data.get('success'):
                result.add_pass("无文件推理正确返回错误")
            else:
                result.add_warning("无文件推理", "返回成功但文件不存在")
        else:
            result.add_fail("无文件推理", f"状态码: {response.status_code}")

    result.summary()
    return result


def test_database_operations():
    """测试数据库操作"""
    print("\n[5] 数据库操作测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        db.create_all()

        print("\n  5.1 用户创建测试")
        user = User(
            username='test_user',
            email='test@test.com',
            phone='13800138000',
            role='patient',
            full_name='测试用户'
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.commit()

        found_user = User.query.filter_by(username='test_user').first()
        if found_user and found_user.check_password('test123'):
            result.add_pass("用户创建和查询成功")
        else:
            result.add_fail("用户创建和查询", "用户未找到或密码验证失败")

        print("\n  5.2 用户更新测试")
        found_user.full_name = '更新后的测试用户'
        db.session.commit()
        updated_user = User.query.filter_by(username='test_user').first()
        if updated_user.full_name == '更新后的测试用户':
            result.add_pass("用户更新成功")
        else:
            result.add_fail("用户更新", "更新未生效")

        print("\n  5.3 标注集创建测试")
        annotation_set = AnnotationSet(
            set_id='db_test_set',
            ct_image_id='db_test_img',
            name='数据库测试标注集'
        )
        db.session.add(annotation_set)
        db.session.commit()

        found_set = AnnotationSet.query.filter_by(set_id='db_test_set').first()
        if found_set:
            result.add_pass("标注集创建成功")
        else:
            result.add_fail("标注集创建", "未找到创建的标注集")

        print("\n  5.4 标注创建测试")
        annotation = Annotation(
            annotation_id='db_test_anno',
            annotation_set_id='db_test_set',
            graphic_type=AnnotationType.POLYGON,
            category=AnnotationCategory.FINDING,
            label='数据库测试标注',
            severity=SeverityLevel.NORMAL,
            workflow_status=WorkflowStatus.PRELIMINARY
        )
        db.session.add(annotation)
        db.session.commit()

        found_anno = Annotation.query.filter_by(annotation_id='db_test_anno').first()
        if found_anno:
            result.add_pass("标注创建成功")
        else:
            result.add_fail("标注创建", "未找到创建的标注")

        print("\n  5.5 数据清理")
        try:
            Annotation.query.filter_by(annotation_id='db_test_anno').delete()
            AnnotationSet.query.filter_by(set_id='db_test_set').delete()
            User.query.filter_by(username='test_user').delete()
            db.session.commit()
            result.add_pass("数据清理成功")
        except Exception as e:
            db.session.rollback()
            result.add_fail("数据清理", str(e))

        print("\n  5.6 事务回滚测试")
        try:
            user1 = User(username='rollback_test', email='rb1@test.com', role='patient')
            user1.set_password('123')
            db.session.add(user1)
            db.session.flush()
            raise Exception("模拟错误")
        except:
            db.session.rollback()
        finally:
            db.session.commit()

        rollback_user = User.query.filter_by(username='rollback_test').first()
        if rollback_user is None:
            result.add_pass("事务回滚成功")
        else:
            result.add_fail("事务回滚", "用户应该被回滚但仍然存在")

    result.summary()
    return result


def test_edge_cases():
    """测试边界情况"""
    print("\n[6] 边界情况测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        init_database(app)
        client = app.test_client()

        print("\n  6.1 空请求体测试")
        response = client.post('/api/auth/login',
            content_type='application/json',
            data=''
        )
        if response.status_code == 400:
            result.add_pass("空请求体正确拒绝")
        else:
            result.add_warning("空请求体", f"状态码: {response.status_code}")

        print("\n  6.2 无效 JSON 测试")
        response = client.post('/api/auth/login',
            content_type='application/json',
            data='not valid json'
        )
        if response.status_code == 400:
            result.add_pass("无效 JSON 正确拒绝")
        else:
            result.add_warning("无效 JSON", f"状态码: {response.status_code}")

        print("\n  6.3 缺失必填字段测试")
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor'
        })
        if response.status_code == 400:
            result.add_pass("缺失必填字段正确拒绝")
        else:
            result.add_warning("缺失必填字段", f"状态码: {response.status_code}")

        print("\n  6.4 无效 Token 测试")
        response = client.get('/api/auth/me', headers={
            'Authorization': 'Bearer invalid_token_here'
        })
        if response.status_code == 401:
            result.add_pass("无效 Token 正确拒绝")
        else:
            result.add_fail("无效 Token 拒绝", f"状态码: {response.status_code}")

        print("\n  6.5 超长输入测试")
        long_input = 'A' * 10000
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': long_input,
            'password': long_input
        })
        if response.status_code in [400, 413, 422]:
            result.add_pass("超长输入正确拒绝")
        else:
            result.add_warning("超长输入", f"状态码: {response.status_code}")

        print("\n  6.6 SQL 注入测试")
        sql_injection = "'; DROP TABLE users; --"
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': sql_injection,
            'password': 'anypassword'
        })
        if response.status_code in [400, 401]:
            result.add_pass("SQL 注入尝试正确拒绝")
        else:
            result.add_fail("SQL 注入", f"未正确拒绝 SQL 注入: 状态码 {response.status_code}")

        print("\n  6.7 XSS 注入测试")
        xss_input = '<script>alert("xss")</script>'
        response = client.post('/api/annotation/sets',
            headers={'Authorization': f'Bearer {client.post("/api/auth/login", json={"login_type": "doctor", "employee_id": "D001", "password": "doctor123"}).headers.get("Authorization", "")}'},
            json={
                'name': xss_input,
                'ct_image_id': 'test'
            }
        )
        if response.status_code in [200, 201, 400]:
            result.add_pass("XSS 输入被处理")
        else:
            result.add_warning("XSS 输入", f"状态码: {response.status_code}")

    result.summary()
    return result


def test_security_mechanisms():
    """测试安全机制"""
    print("\n[7] 安全机制测试")
    print("-"*40)

    result = TestResult()
    app = create_app('development')
    app.config['TESTING'] = True

    with app.app_context():
        init_database(app)
        client = app.test_client()

        print("\n  7.1 CORS 头检查")
        response = client.get('/api/sam3d/health')
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        cors_methods = response.headers.get('Access-Control-Allow-Methods')
        if cors_origin and cors_methods:
            result.add_pass(f"CORS 头存在 (Origin: {cors_origin})")
        else:
            result.add_fail("CORS 头", f"缺少 CORS 头: Allow-Origin={cors_origin}")

        print("\n  7.2 敏感信息暴露检查")
        response = client.post('/api/auth/login', json={
            'login_type': 'doctor',
            'employee_id': 'D001',
            'password': 'doctor123'
        })
        data = json.loads(response.data)
        if 'password' not in str(response.data).lower() and 'hash' not in str(response.data).lower():
            result.add_pass("敏感信息未暴露")
        else:
            result.add_fail("敏感信息暴露", "响应中可能包含密码或哈希")

        print("\n  7.3 Token 过期检查")
        from services.auth_service import generate_token
        import jwt
        expired_token = jwt.encode({
            'user_id': 1,
            'role': 'doctor',
            'exp': datetime.utcnow() - 3600
        }, 'ctai-jwt-secret-key', algorithm='HS256')

        response = client.get('/api/auth/me', headers={
            'Authorization': f'Bearer {expired_token}'
        })
        if response.status_code == 401:
            result.add_pass("过期 Token 正确拒绝")
        else:
            result.add_fail("过期 Token", f"过期 Token 未被拒绝: 状态码 {response.status_code}")

        print("\n  7.4 错误信息泄露检查")
        response = client.get('/api/annotation/sets/nonexistent_set_12345',
            headers={'Authorization': 'Bearer valid'}
        )
        data = json.loads(response.data)
        if 'stack' not in str(response.data).lower() and 'traceback' not in str(response.data).lower():
            result.add_pass("错误信息未泄露")
        else:
            result.add_warning("错误信息", "可能泄露了堆栈跟踪信息")

    result.summary()
    return result


def generate_report(all_results):
    """生成测试报告"""
    print("\n" + "="*70)
    print("                       综 合 测 试 报 告")
    print("="*70)

    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_warnings = sum(len(r.warnings) for r in all_results)

    print(f"\n总体结果:")
    print(f"  通过: {total_passed}")
    print(f"  失败: {total_failed}")
    print(f"  警告: {total_warnings}")

    print(f"\n失败测试详情:")
    for result in all_results:
        for error in result.errors:
            print(f"  [{error['severity']}] {error['test']}")
            print(f"         原因: {error['reason']}")

    print(f"\n警告事项:")
    for result in all_results:
        for warning in result.warnings:
            print(f"  [{warning['severity']}] {warning['test']}")
            print(f"         原因: {warning['reason']}")

    print("\n" + "="*70)

    if total_failed == 0:
        print("✅ 所有核心测试通过！")
    else:
        print(f"⚠️  发现 {total_failed} 个失败项，需要修复")

    print("="*70 + "\n")

    return total_failed == 0


if __name__ == '__main__':
    print("\n" + "="*70)
    print("       SAM-Med3D 后端系统全面测试")
    print("="*70)

    results = []

    results.append(test_api_endpoints())
    results.append(test_authentication_flow())
    results.append(test_annotation_api())
    results.append(test_sam3d_api())
    results.append(test_database_operations())
    results.append(test_edge_cases())
    results.append(test_security_mechanisms())

    success = generate_report(results)

    sys.exit(0 if success else 1)
