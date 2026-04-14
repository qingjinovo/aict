from datetime import datetime
from extensions import db
from models.progress import ProgressRecord, Message, Notification

class NotificationService:
    @staticmethod
    def create_notification(user_id, title, content, notification_type, related_ct_image_id=None, related_message_id=None):
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            related_ct_image_id=related_ct_image_id,
            related_message_id=related_message_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @staticmethod
    def get_user_notifications(user_id, unread_only=False, limit=50):
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_as_read(notification_id):
        notification = Notification.query.get(notification_id)
        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(user_id):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        db.session.commit()

    @staticmethod
    def get_unread_count(user_id):
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()


class MessageService:
    @staticmethod
    def create_message(ct_image_id, sender_id, receiver_id, content, message_type='text'):
        message = Message(
            ct_image_id=ct_image_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type
        )
        db.session.add(message)
        db.session.commit()

        NotificationService.create_notification(
            user_id=receiver_id,
            title='新消息',
            content=content[:100],
            notification_type='message',
            related_ct_image_id=ct_image_id,
            related_message_id=message.id
        )
        return message

    @staticmethod
    def get_ct_messages(ct_image_id):
        return Message.query.filter_by(ct_image_id=ct_image_id).order_by(Message.created_at.asc()).all()

    @staticmethod
    def mark_message_read(message_id):
        message = Message.query.get(message_id)
        if message and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()
        return message

    @staticmethod
    def get_conversation(user1_id, user2_id, ct_image_id=None):
        query = Message.query.filter(
            ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
            ((Message.sender_id == user2_id) & (Message.receiver_id == user_id))
        )
        if ct_image_id:
            query = query.filter_by(ct_image_id=ct_image_id)
        return query.order_by(Message.created_at.asc()).all()


class ProgressService:
    STAGES = {
        'uploaded': {'name': '已上传', 'progress': 10, 'next': 'notifying'},
        'notifying': {'name': '通知医生中', 'progress': 20, 'next': 'doctor_reviewing'},
        'doctor_reviewing': {'name': '医生审阅中', 'progress': 30, 'next': 'ai_processing'},
        'ai_processing': {'name': 'AI处理中', 'progress': 50, 'next': 'ai_completed'},
        'ai_completed': {'name': 'AI处理完成', 'progress': 70, 'next': 'doctor_annotating'},
        'doctor_annotating': {'name': '医生标注中', 'progress': 80, 'next': 'pending_confirmation'},
        'pending_confirmation': {'name': '待确认', 'progress': 90, 'next': 'completed'},
        'completed': {'name': '已完成', 'progress': 100, 'next': None}
    }

    @staticmethod
    def create_progress_record(ct_image_id, stage, message=None):
        record = ProgressRecord(
            ct_image_id=ct_image_id,
            stage=stage,
            status='in_progress',
            progress_percentage=ProgressService.STAGES.get(stage, {}).get('progress', 0),
            message=message,
            started_at=datetime.utcnow()
        )
        db.session.add(record)
        db.session.commit()
        return record

    @staticmethod
    def update_progress(record_id, status='completed', message=None, error_message=None):
        record = ProgressRecord.query.get(record_id)
        if record:
            record.status = status
            if message:
                record.message = message
            if error_message:
                record.error_message = error_message
            if status == 'completed':
                record.completed_at = datetime.utcnow()
            db.session.commit()
        return record

    @staticmethod
    def get_ct_progress(ct_image_id):
        records = ProgressRecord.query.filter_by(ct_image_id=ct_image_id).order_by(ProgressRecord.created_at.asc()).all()
        current_stage = None
        current_progress = 0

        for record in reversed(records):
            if record.status == 'in_progress':
                current_stage = record.stage
                current_progress = record.progress_percentage
                break
            elif record.status == 'completed' and not current_stage:
                current_stage = record.stage
                current_progress = record.progress_percentage

        return {
            'records': [r.to_dict() for r in records],
            'current_stage': current_stage,
            'current_progress': current_progress,
            'stage_name': ProgressService.STAGES.get(current_stage, {}).get('name', '未知阶段') if current_stage else '未知'
        }

    @staticmethod
    def advance_stage(ct_image_id):
        records = ProgressRecord.query.filter_by(ct_image_id=ct_image_id).order_by(ProgressRecord.created_at.desc()).all()

        current_stage = 'uploaded'
        if records:
            latest = records[0]
            if latest.status == 'in_progress':
                latest.status = 'completed'
                latest.completed_at = datetime.utcnow()
                current_stage = latest.stage

        next_stage = ProgressService.STAGES.get(current_stage, {}).get('next', None)
        if next_stage:
            new_record = ProgressService.create_progress_record(
                ct_image_id=ct_image_id,
                stage=next_stage,
                message=f"进入{ProgressService.STAGES[next_stage]['name']}阶段"
            )
            db.session.commit()
            return new_record
        return None

    @staticmethod
    def complete_processing(ct_image_id):
        current = ProgressRecord.query.filter_by(
            ct_image_id=ct_image_id,
            status='in_progress'
        ).order_by(ProgressRecord.created_at.desc()).first()

        if current:
            current.status = 'completed'
            current.completed_at = datetime.utcnow()
            db.session.commit()

        final_record = ProgressRecord(
            ct_image_id=ct_image_id,
            stage='completed',
            status='completed',
            progress_percentage=100,
            message='处理完成',
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(final_record)
        db.session.commit()
        return final_record
