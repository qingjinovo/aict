from datetime import datetime
from extensions import db

class CTImage(db.Model):
    __tablename__ = 'ct_images'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    file_name = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(20))

    body_part = db.Column(db.String(50))
    description = db.Column(db.Text)

    status = db.Column(db.String(30), default='uploaded')

    ai_model_version = db.Column(db.String(50))
    processing_started_at = db.Column(db.DateTime)
    processing_completed_at = db.Column(db.DateTime)

    final_report = db.Column(db.Text)
    final_diagnosis = db.Column(db.Text)
    confirmed_by_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    annotations = db.relationship('Annotation', backref='ct_image', lazy='dynamic')
    progress_records = db.relationship('ProgressRecord', backref='ct_image', lazy='dynamic')
    messages = db.relationship('Message', backref='ct_image', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'file_name': self.file_name,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'body_part': self.body_part,
            'description': self.description,
            'status': self.status,
            'ai_model_version': self.ai_model_version,
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            'final_report': self.final_report,
            'final_diagnosis': self.final_diagnosis,
            'confirmed_by_doctor_id': self.confirmed_by_doctor_id,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Annotation(db.Model):
    __tablename__ = 'annotations'

    id = db.Column(db.Integer, primary_key=True)
    ct_image_id = db.Column(db.Integer, db.ForeignKey('ct_images.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    annotation_type = db.Column(db.String(30))
    slice_number = db.Column(db.Integer)
    coordinates_x = db.Column(db.Float)
    coordinates_y = db.Column(db.Float)
    coordinates_z = db.Column(db.Float)
    radius = db.Column(db.Float)
    label = db.Column(db.String(100))
    severity = db.Column(db.String(20))
    notes = db.Column(db.Text)

    is_abnormal = db.Column(db.Boolean, default=False)
    ai_generated = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'ct_image_id': self.ct_image_id,
            'doctor_id': self.doctor_id,
            'annotation_type': self.annotation_type,
            'slice_number': self.slice_number,
            'coordinates': {
                'x': self.coordinates_x,
                'y': self.coordinates_y,
                'z': self.coordinates_z
            },
            'radius': self.radius,
            'label': self.label,
            'severity': self.severity,
            'notes': self.notes,
            'is_abnormal': self.is_abnormal,
            'ai_generated': self.ai_generated,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
