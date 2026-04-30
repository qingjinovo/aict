import os
from app import create_app, init_database

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)
init_database(app)

if __name__ == '__main__':
    app.run()
