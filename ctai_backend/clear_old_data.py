import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from extensions import db
from app import create_app
from models.ct_image import CTImage
from models.progress import ProgressRecord, Message, Notification

app = create_app()

with app.app_context():
    print("开始清除老数据...")

    ct_images_count = CTImage.query.count()
    print(f"CT图像记录数: {ct_images_count}")

    messages_count = Message.query.count()
    print(f"消息记录数: {messages_count}")

    notifications_count = Notification.query.count()
    print(f"通知记录数: {notifications_count}")

    progress_count = ProgressRecord.query.count()
    print(f"进度记录数: {progress_count}")

    if ct_images_count == 0:
        print("没有需要清除的数据")
    else:
        confirm = input("\n确认清除所有CT图像相关数据？(y/n): ")
        if confirm.lower() == 'y':
            print("正在清除数据...")

            Message.query.delete()
            print(f"已删除 {messages_count} 条消息")

            Notification.query.delete()
            print(f"已删除 {notifications_count} 条通知")

            ProgressRecord.query.delete()
            print(f"已删除 {progress_count} 条进度记录")

            CTImage.query.delete()
            print(f"已删除 {ct_images_count} 条CT图像记录")

            db.session.commit()
            print("\n数据清除完成！")
        else:
            print("已取消")

    user_count = User.query.count()
    print(f"用户记录数: {user_count} (已保留)")
