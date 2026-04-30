import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from extensions import db
from models.progress import Message
from models.ct_image import CTImage
from models.user import User

def diagnose():
    app = create_app('development')
    with app.app_context():
        print("="*60)
        print("消息系统诊断")
        print("="*60)
        
        messages = Message.query.all()
        
        if not messages:
            print("数据库中没有消息记录")
            
            print("\n检查CTImage的doctor_id分配:")
            images = CTImage.query.all()
            for img in images:
                doctor = User.query.get(img.doctor_id) if img.doctor_id else None
                print(f"  CTImage ID={img.id}: doctor_id={img.doctor_id}, 医生={doctor.full_name if doctor else '未分配'}")
            return
        
        print(f"\n共找到 {len(messages)} 条消息记录:\n")
        
        for msg in messages:
            sender = User.query.get(msg.sender_id)
            receiver = User.query.get(msg.receiver_id)
            ct_image = CTImage.query.get(msg.ct_image_id)
            
            print(f"消息ID: {msg.id}")
            print(f"  CT影像ID: {msg.ct_image_id}")
            print(f"  发送者: {sender.full_name if sender else '未知'} (ID={msg.sender_id}, 角色={sender.role if sender else '未知'})")
            print(f"  接收者: {receiver.full_name if receiver else '未知'} (ID={msg.receiver_id}, 角色={receiver.role if receiver else '未知'})")
            print(f"  内容: {msg.content[:50]}...")
            print(f"  已读: {msg.is_read}")
            print(f"  创建时间: {msg.created_at}")
            print()
        
        print("\n" + "="*60)
        print("医生收到的消息统计:")
        print("="*60)
        
        doctors = User.query.filter_by(role='doctor').all()
        for doctor in doctors:
            received = Message.query.filter_by(receiver_id=doctor.id).all()
            unread = Message.query.filter_by(receiver_id=doctor.id, is_read=False).count()
            print(f"医生 {doctor.full_name} (ID={doctor.id}):")
            print(f"  收到消息总数: {len(received)}")
            print(f"  未读消息数: {unread}")
            if received:
                for msg in received[-3:]:
                    print(f"    最近消息: {msg.content[:30]}... (来自用户ID={msg.sender_id})")
            print()
        
        print("\n" + "="*60)
        print("CTImage的doctor_id检查:")
        print("="*60)
        
        images = CTImage.query.all()
        for img in images:
            has_doctor = img.doctor_id is not None
            doctor = User.query.get(img.doctor_id) if img.doctor_id else None
            patient = User.query.get(img.patient_id)
            
            status_icon = "✓" if has_doctor else "✗"
            print(f"{status_icon} CTImage ID={img.id}: 患者={patient.full_name if patient else '未知'}, doctor_id={img.doctor_id}, 医生={doctor.full_name if doctor else '未分配'}")
        
        print("\n" + "="*60)
        print("诊断完成")
        print("="*60)

if __name__ == '__main__':
    diagnose()
