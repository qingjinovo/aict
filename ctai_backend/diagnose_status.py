import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from extensions import db
from models.ct_image import CTImage

def diagnose():
    app = create_app('development')
    with app.app_context():
        print("="*60)
        print("CTImage 状态诊断")
        print("="*60)
        
        images = CTImage.query.all()
        
        if not images:
            print("数据库中没有CTImage记录")
            return
        
        print(f"\n共找到 {len(images)} 条记录:\n")
        
        status_counts = {}
        for img in images:
            status_counts[img.status] = status_counts.get(img.status, 0) + 1
            print(f"ID: {img.id}")
            print(f"  患者ID: {img.patient_id}")
            print(f"  文件名: {img.original_filename}")
            print(f"  状态: '{img.status}'")
            print(f"  创建时间: {img.created_at}")
            print()
        
        print("\n状态统计:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}条")
        
        print("\n" + "="*60)
        print("检查异常状态...")
        print("="*60)
        
        valid_statuses = ['uploaded', 'notifying', 'doctor_reviewing', 
                         'ai_processing', 'ai_completed', 'doctor_annotating',
                         'ai_annotated', 'pending_confirmation', 'completed']
        
        for img in images:
            if img.status not in valid_statuses:
                print(f"[警告] ID {img.id} 状态异常: '{img.status}'")
        
        uploaded_images = CTImage.query.filter_by(status='uploaded').all()
        if uploaded_images:
            print(f"\n找到 {len(uploaded_images)} 条 uploaded 状态的记录:")
            for img in uploaded_images:
                print(f"  ID: {img.id}, 创建时间: {img.created_at}")
        
        ai_processing_images = CTImage.query.filter_by(status='ai_processing').all()
        if ai_processing_images:
            print(f"\n[注意] 找到 {len(ai_processing_images)} 条 ai_processing 状态的记录:")
            for img in ai_processing_images:
                print(f"  ID: {img.id}, 创建时间: {img.created_at}")
        
        print("\n" + "="*60)
        print("诊断完成")
        print("="*60)

if __name__ == '__main__':
    diagnose()
