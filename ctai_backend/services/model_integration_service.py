import requests
import json
from datetime import datetime
from config import Config

class ModelIntegrationService:
    MODEL_SERVICE_URL = Config.MODEL_SERVICE_URL

    @staticmethod
    def is_model_available():
        try:
            response = requests.get(f"{ModelIntegrationService.MODEL_SERVICE_URL}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    @staticmethod
    def call_model_inference(ct_image_path, annotations=None):
        payload = {
            'image_path': ct_image_path,
            'annotations': annotations or [],
            'timestamp': datetime.now().isoformat()
        }

        try:
            response = requests.post(
                f"{ModelIntegrationService.MODEL_SERVICE_URL}/predict",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                return {
                    'success': True,
                    'result': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f"Model service returned status {response.status_code}",
                    'result': None
                }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Cannot connect to model service. Please ensure the model service is running.',
                'result': None
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Model inference timed out',
                'result': None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'result': None
            }

    @staticmethod
    def get_model_info():
        try:
            response = requests.get(f"{ModelIntegrationService.MODEL_SERVICE_URL}/model_info", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {
            'available': False,
            'message': 'Model service is not available. Please start the model service.'
        }

    @staticmethod
    def generate_mock_result(ct_image_id):
        return {
            'success': True,
            'result': {
                'model_version': 'SAM-Med3D-v1.0',
                'predictions': [
                    {
                        'slice_number': 45,
                        'coordinates': {'x': 125.5, 'y': 98.3, 'z': 72.1},
                        'radius': 15.2,
                        'label': 'nodule',
                        'confidence': 0.92,
                        'severity': 'medium'
                    },
                    {
                        'slice_number': 67,
                        'coordinates': {'x': 200.1, 'y': 150.8, 'z': 95.3},
                        'radius': 8.7,
                        'label': 'lesion',
                        'confidence': 0.87,
                        'severity': 'low'
                    }
                ],
                'processing_time': 12.5,
                'ct_image_id': ct_image_id
            }
        }
