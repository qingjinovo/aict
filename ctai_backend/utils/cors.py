"""
Flask CORS 扩展
处理跨域资源共享策略
"""

from flask import request, make_response, jsonify
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CORSManager:
    """CORS 管理器"""

    def __init__(self, app=None, origins='*', methods=None, allow_headers=None):
        self.origins = origins
        self.methods = methods or ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH']
        self.allow_headers = allow_headers or ['Content-Type', 'Authorization', 'X-Requested-With', 'Accept']

        if app:
            self.init_app(app)

    def init_app(self, app):
        """初始化 CORS"""
        app.before_request(self.handle_preflight)
        app.after_request(self.handle_response)

    def handle_preflight(self):
        """处理 OPTIONS 预检请求"""
        if request.method == 'OPTIONS':
            response = make_response()
            self._add_cors_headers(response)
            return response

    def handle_response(self, response):
        """处理响应，添加 CORS 头"""
        if request.method != 'OPTIONS':
            self._add_cors_headers(response)
        return response

    def _add_cors_headers(self, response):
        """添加 CORS 头"""
        origin = request.headers.get('Origin', '*')

        if self.origins == '*':
            response.headers['Access-Control-Allow-Origin'] = '*'
        elif isinstance(self.origins, (list, tuple)):
            if origin in self.origins:
                response.headers['Access-Control-Allow-Origin'] = origin
            else:
                response.headers['Access-Control-Allow-Origin'] = self.origins[0] if self.origins else '*'
        else:
            response.headers['Access-Control-Allow-Origin'] = self.origins

        response.headers['Access-Control-Allow-Methods'] = ', '.join(self.methods)
        response.headers['Access-Control-Allow-Headers'] = ', '.join(self.allow_headers)
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '3600'

    def cors(self, origins=None, methods=None, allow_headers=None):
        """CORS 装饰器"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                response = f(*args, **kwargs)
                if isinstance(response, tuple):
                    resp = response[0]
                else:
                    resp = response

                if hasattr(resp, 'headers'):
                    if origins or self.origins:
                        resp.headers['Access-Control-Allow-Origin'] = origins or self.origins
                    if methods:
                        resp.headers['Access-Control-Allow-Methods'] = ', '.join(methods)
                    if allow_headers:
                        resp.headers['Access-Control-Allow-Headers'] = ', '.join(allow_headers)

                return response
            return decorated_function
        return decorator


cors_manager = CORSManager()


def init_cors(app, config):
    """初始化 CORS"""
    origins = config.get('CORS_ORIGINS', '*')
    methods = config.get('CORS_METHODS', None)
    allow_headers = config.get('CORS_ALLOW_HEADERS', None)

    global cors_manager
    cors_manager = CORSManager(app, origins=origins, methods=methods, allow_headers=allow_headers)

    logger.info(f"CORS 已初始化，允许来源: {origins}")

    return cors_manager
