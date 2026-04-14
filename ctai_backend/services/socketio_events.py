from flask_socketio import emit, join_room, leave_room
from flask import request
from flask_login import current_user
from models.progress import Message, Notification
from extensions import db
import json

def register_socketio_events(socketio):

    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            room = f"user_{current_user.id}"
            join_room(room)
            emit('connected', {'status': 'connected', 'user_id': current_user.id})
        else:
            emit('error', {'message': 'Unauthorized'})

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            room = f"user_{current_user.id}"
            leave_room(room)

    @socketio.on('join_ct_room')
    def handle_join_ct_room(data):
        ct_image_id = data.get('ct_image_id')
        if ct_image_id:
            room = f"ct_{ct_image_id}"
            join_room(room)
            emit('joined_ct_room', {'ct_image_id': ct_image_id})

    @socketio.on('leave_ct_room')
    def handle_leave_ct_room(data):
        ct_image_id = data.get('ct_image_id')
        if ct_image_id:
            room = f"ct_{ct_image_id}"
            leave_room(room)

    @socketio.on('send_message')
    def handle_send_message(data):
        ct_image_id = data.get('ct_image_id')
        content = data.get('content')
        receiver_id = data.get('receiver_id')

        if ct_image_id and content and receiver_id:
            message = Message(
                ct_image_id=ct_image_id,
                sender_id=current_user.id,
                receiver_id=receiver_id,
                content=content
            )
            db.session.add(message)
            db.session.commit()

            notification = Notification(
                user_id=receiver_id,
                title='新消息',
                content=content[:100],
                notification_type='message',
                related_ct_image_id=ct_image_id,
                related_message_id=message.id
            )
            db.session.add(notification)
            db.session.commit()

            emit('new_message', message.to_dict(), room=f"ct_{ct_image_id}")
            emit('new_message', message.to_dict(), room=f"user_{receiver_id}")

            emit('message_sent', {'status': 'success', 'message': message.to_dict()})

    @socketio.on('progress_update')
    def handle_progress_update(data):
        ct_image_id = data.get('ct_image_id')
        stage = data.get('stage')
        progress = data.get('progress')
        message = data.get('message')

        if ct_image_id:
            room = f"ct_{ct_image_id}"
            emit('progress_changed', {
                'ct_image_id': ct_image_id,
                'stage': stage,
                'progress': progress,
                'message': message
            }, room=room)

            if current_user.is_authenticated:
                emit('progress_changed', {
                    'ct_image_id': ct_image_id,
                    'stage': stage,
                    'progress': progress,
                    'message': message
                }, room=f"user_{current_user.id}")

    @socketio.on('annotation_added')
    def handle_annotation_added(data):
        ct_image_id = data.get('ct_image_id')
        if ct_image_id:
            room = f"ct_{ct_image_id}"
            emit('annotation_update', {
                'action': 'added',
                'annotation': data.get('annotation'),
                'ct_image_id': ct_image_id
            }, room=room)

    @socketio.on('annotation_modified')
    def handle_annotation_modified(data):
        ct_image_id = data.get('ct_image_id')
        if ct_image_id:
            room = f"ct_{ct_image_id}"
            emit('annotation_update', {
                'action': 'modified',
                'annotation': data.get('annotation'),
                'ct_image_id': ct_image_id
            }, room=room)

    @socketio.on('annotation_deleted')
    def handle_annotation_deleted(data):
        ct_image_id = data.get('ct_image_id')
        annotation_id = data.get('annotation_id')
        if ct_image_id:
            room = f"ct_{ct_image_id}"
            emit('annotation_update', {
                'action': 'deleted',
                'annotation_id': annotation_id,
                'ct_image_id': ct_image_id
            }, room=room)

    @socketio.on('call_model')
    def handle_call_model(data):
        ct_image_id = data.get('ct_image_id')
        if ct_image_id:
            emit('model_call_started', {'ct_image_id': ct_image_id}, room=f"ct_{ct_image_id}")

    @socketio.on('model_call_complete')
    def handle_model_call_complete(data):
        ct_image_id = data.get('ct_image_id')
        result = data.get('result')
        if ct_image_id:
            emit('model_call_finished', {
                'ct_image_id': ct_image_id,
                'result': result
            }, room=f"ct_{ct_image_id}")
