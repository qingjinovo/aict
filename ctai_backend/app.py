import os
from flask import Flask
from config import config
from extensions import db, login_manager
from routes import auth_bp, doctor_bp, patient_bp, api_bp
from routes.auth_api import auth_api_bp
from routes.sam3d_api import sam3d_bp
from utils.cors import init_cors

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['BASE_DIR'], 'data'), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    init_cors(app, config[config_name].__dict__)

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import redirect, url_for, flash
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))

    app.register_blueprint(auth_bp)
    app.register_blueprint(auth_api_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(sam3d_bp)

    @app.template_filter('format_datetime')
    def format_datetime(dt):
        if dt:
            if isinstance(dt, str):
                return dt
            return dt.strftime('%Y-%m-%d %H:%M')
        return ''

    @app.template_filter('format_file_size')
    def format_file_size(size):
        if size:
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return '0 B'

    @app.template_filter('to_web_path')
    def to_web_path(file_path):
        if not file_path:
            return ''
        path = file_path.replace('\\', '/')
        static_prefixes = [
            'D:/Study/Project/JSJDS/demo/ctai_backend/static',
            '/root/file/aict/ctai_backend/static',
            '/root/file/aict/ctai_web/static'
        ]
        for prefix in static_prefixes:
            if prefix in path:
                path = path.replace(prefix, '')
        if not path.startswith('/'):
            path = '/' + path
        if not path.startswith('/static/'):
            if path.startswith('/uploads/'):
                path = '/static' + path
            else:
                path = '/static/' + path.lstrip('/')
        return path

    @app.context_processor
    def inject_utilities():
        return {
            'enumerate': enumerate,
            'len': len
        }

    return app

def init_database(app):
    with app.app_context():
        db.create_all()

        from models.user import User
        existing_doctor = User.query.filter_by(employee_id='D001').first()
        if not existing_doctor:
            doctor = User(
                username='doctor_li',
                email='doctor@hospital.local',
                role='doctor',
                phone='13800000001',
                full_name='李医生',
                department='影像科',
                employee_id='D001'
            )
            doctor.set_password('doctor123')
            db.session.add(doctor)

        existing_patient = User.query.filter_by(phone='13900000001').first()
        if not existing_patient:
            patient = User(
                username='patient_test',
                email='patient@test.local',
                role='patient',
                phone='13900000001',
                full_name='测试患者'
            )
            patient.set_password('patient123')
            db.session.add(patient)

        db.session.commit()

if __name__ == '__main__':
    app = create_app('development')
    init_database(app)
    print("\n" + "="*50)
    print("SAM-Med3D 医学影像诊断平台")
    print("="*50)
    print("访问地址: http://localhost:5000")
    print("\n测试账号:")
    print("  医生: 工号 D001, 密码 doctor123")
    print("  患者: 手机号 13900000001, 验证码任意")
    print("\nSAM3D 模型服务:")
    print("  推理API: POST /api/sam3d/infer")
    print("  简化推理: POST /api/sam3d/infer-simple")
    print("  模型信息: GET /api/sam3d/model-info")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
