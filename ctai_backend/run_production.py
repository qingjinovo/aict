import os
import sys
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app, init_database

app = create_app('production')
init_database(app)

if __name__ == '__main__':
    from waitress import serve
    print("\n" + "=" * 50)
    print("SAM-Med3D 医学影像诊断平台 (生产模式)")
    print("=" * 50)
    print("访问地址: http://0.0.0.0:8080")
    print("=" * 50 + "\n")
    serve(app, host='0.0.0.0', port=8080, threads=8)
