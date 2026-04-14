import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from config import Config

class FileUploadService:
    ALLOWED_EXTENSIONS = Config.ALLOWED_EXTENSIONS
    UPLOAD_FOLDER = Config.UPLOAD_FOLDER

    COMPRESSED_NIFTI_EXTENSIONS = {'nii.gz'}
    SINGLE_EXTENSIONS = {'nii', 'dcm', 'png', 'jpg', 'jpeg'}

    @staticmethod
    def allowed_file(filename):
        if not filename or '.' not in filename:
            return False
        if filename.startswith('.'):
            return False

        ext = FileUploadService.get_extension(filename)
        if not ext:
            return False

        if ext in FileUploadService.COMPRESSED_NIFTI_EXTENSIONS:
            return True
        if ext in FileUploadService.SINGLE_EXTENSIONS:
            return True
        return False

    @staticmethod
    def get_extension(filename):
        if not filename or '.' not in filename or filename.startswith('.'):
            return ''
        parts = filename.rsplit('.', 1)
        if len(parts) == 2:
            ext = parts[1].lower()
            if ext == 'gz' and '.' in parts[0]:
                inner_parts = parts[0].rsplit('.', 1)
                if len(inner_parts) == 2 and inner_parts[1].lower() == 'nii':
                    return 'nii.gz'
            return ext
        return ''

    @staticmethod
    def generate_filename(original_filename):
        ext = FileUploadService.get_extension(original_filename)
        unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if ext:
            unique_name += f".{ext}"
        return unique_name

    @staticmethod
    def get_file_path(filename):
        return os.path.join(FileUploadService.UPLOAD_FOLDER, filename)

    @staticmethod
    def save_file(file):
        if file and FileUploadService.allowed_file(file.filename):
            filename = FileUploadService.generate_filename(file.filename)
            filepath = FileUploadService.get_file_path(filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            file_size = os.path.getsize(filepath)
            file_type = FileUploadService.get_file_type(filename)
            return {
                'filename': filename,
                'filepath': filepath,
                'file_size': file_size,
                'file_type': file_type
            }
        return None

    @staticmethod
    def get_file_type(filename):
        ext = FileUploadService.get_extension(filename)
        if ext in FileUploadService.COMPRESSED_NIFTI_EXTENSIONS or ext == 'nii.gz':
            return 'nifti_gz'
        if ext == 'nii':
            return 'nifti'
        if ext in {'dcm', 'dicom'}:
            return 'dicom'
        if ext in {'png', 'jpg', 'jpeg'}:
            return 'image'
        return 'unknown'

    @staticmethod
    def delete_file(filename):
        filepath = FileUploadService.get_file_path(filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    @staticmethod
    def get_file_info(filename):
        filepath = FileUploadService.get_file_path(filename)
        if os.path.exists(filepath):
            return {
                'exists': True,
                'size': os.path.getsize(filepath),
                'path': filepath,
                'modified': datetime.fromtimestamp(os.path.getmtime(filepath)),
                'type': FileUploadService.get_file_type(filename)
            }
        return {'exists': False}
