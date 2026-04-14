from datetime import datetime
from extensions import db

class ProgressRecord(db.Model):
    __tablename__ = 'progress_records'

    id = db.Column(db.Integer, primary_key=True)
    ct_image_id = db.Column(db.Integer, db.ForeignKey('ct_images.id'), nullable=False)

    stage = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    progress_percentage = db.Column(db.Integer, default=0)
    message = db.Column(db.String(255))
    error_message = db.Column(db.Text)

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    STAGES = [
        ('uploaded', '已上传'),
        ('notifying', '通知医生中'),
        ('doctor_reviewing', '医生审阅中'),
        ('ai_processing', 'AI处理中'),
        ('ai_completed', 'AI处理完成'),
        ('doctor_annotating', '医生标注中'),
        ('pending_confirmation', '待确认'),
        ('completed', '已完成')
    ]

    def to_dict(self):
        return {
            'id': self.id,
            'ct_image_id': self.ct_image_id,
            'stage': self.stage,
            'stage_name': dict(self.STAGES).get(self.stage, self.stage),
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'message': self.message,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    ct_image_id = db.Column(db.Integer, db.ForeignKey('ct_images.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')

    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

    def to_dict(self):
        return {
            'id': self.id,
            'ct_image_id': self.ct_image_id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'content': self.content,
            'message_type': self.message_type,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sender_name': self.sender.full_name if self.sender else None,
            'receiver_name': self.receiver.full_name if self.receiver else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30))

    related_ct_image_id = db.Column(db.Integer, db.ForeignKey('ct_images.id'))
    related_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'))

    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'content': self.content,
            'notification_type': self.notification_type,
            'related_ct_image_id': self.related_ct_image_id,
            'related_message_id': self.related_message_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
