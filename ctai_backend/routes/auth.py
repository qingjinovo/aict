from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User
from extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def role_selection():
    if current_user.is_authenticated:
        if current_user.is_doctor():
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))
    return render_template('role_selection.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.role_selection'))

    role = request.args.get('role', 'doctor')

    if request.method == 'POST':
        login_type = request.form.get('login_type', 'doctor')

        if login_type == 'doctor':
            employee_id = request.form.get('employee_id', '')
            password = request.form.get('password', '')

            user = User.query.filter_by(employee_id=employee_id, role='doctor').first()

            if user and user.check_password(password):
                login_user(user)
                session['role'] = 'doctor'
                flash('医生登录成功', 'success')
                return redirect(url_for('doctor.dashboard'))
            else:
                flash('工号或密码错误', 'error')

        else:
            phone = request.form.get('phone', '')
            verify_code = request.form.get('verify_code', '')

            user = User.query.filter_by(phone=phone, role='patient').first()

            if user:
                login_user(user)
                session['role'] = 'patient'
                flash('患者登录成功', 'success')
                return redirect(url_for('patient.dashboard'))
            else:
                session['verify_code'] = '123456'
                session['verify_phone'] = phone
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
                session['role'] = 'patient'
                flash('患者登录成功', 'success')
                return redirect(url_for('patient.dashboard'))

    return render_template('login.html', role=role)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('auth.role_selection'))
