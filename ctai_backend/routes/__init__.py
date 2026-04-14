from routes.auth import auth_bp
from routes.doctor import doctor_bp
from routes.patient import patient_bp
from routes.api import api_bp

__all__ = ['auth_bp', 'doctor_bp', 'patient_bp', 'api_bp']
