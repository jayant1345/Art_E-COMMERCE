from flask import Flask, url_for
from extensions import db, login_manager
import os, cloudinary

def create_app():
    app = Flask(__name__)

    # Secret key — always set SECRET_KEY env var in production
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gallery-secret-key-change-in-production')

    # Database — Railway sets DATABASE_URL automatically when you add a Postgres plugin
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///canvasculture.db')
    if database_url.startswith('postgres://'):          # Railway uses postgres://, SQLAlchemy needs postgresql://
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # ── PayU Keys (set via environment variables in Railway dashboard) ───────────
    app.config['PAYU_KEY']    = os.environ.get('PAYU_KEY',  'gtKFFx')
    app.config['PAYU_SALT']   = os.environ.get('PAYU_SALT', 'eCwWELxi')
    app.config['PAYU_MODE']   = os.environ.get('PAYU_MODE', 'test')

    app.config['PAYU_URL_TEST'] = 'https://test.payu.in/_payment'
    app.config['PAYU_URL_LIVE'] = 'https://secure.payu.in/_payment'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Cloudinary (images stored in cloud, survives redeploys) ─────────────────
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
        api_key    = os.environ.get('CLOUDINARY_API_KEY',    ''),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET', ''),
        secure     = True,
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Please log in to access the admin panel.'

    # ── Jinja2 filter: handles both Cloudinary URLs and local static paths ───────
    @app.template_filter('img_url')
    def img_url_filter(path):
        if not path:
            return ''
        if path.startswith('http'):
            return path
        return url_for('static', filename=path)

    from routes import main, admin_bp, shop, artist_bp
    app.register_blueprint(main)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(shop, url_prefix='/shop')
    app.register_blueprint(artist_bp, url_prefix='/artist')

    with app.app_context():
        db.create_all()
        _migrate_schema()
        _seed_data()

    return app

def _migrate_schema():
    """Add columns to existing tables without dropping data."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('artist')]
    if 'user_id' not in cols:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE artist ADD COLUMN user_id INTEGER REFERENCES "user"(id)'))
            conn.commit()

def _seed_data():
    from models import User, Artwork, Artist, Category
    if User.query.first():
        return

    from werkzeug.security import generate_password_hash
    admin = User(username='admin', email='admin@gallery.com',
                 password=generate_password_hash('admin123'), is_admin=True)
    db.session.add(admin)

    cats = ['Painting', 'Photography', 'Sculpture', 'Digital Art', 'Drawing']
    cat_objs = []
    for c in cats:
        cat = Category(name=c)
        db.session.add(cat)
        cat_objs.append(cat)

    artists_data = [
        ('Elena Vasquez', 'Contemporary abstract painter from Barcelona.'),
        ('Marcus Chen', 'Award-winning photographer specializing in urban landscapes.'),
        ('Aria Novak', 'Digital artist exploring AI and human emotion.'),
    ]
    artist_objs = []
    for name, bio in artists_data:
        a = Artist(name=name, bio=bio)
        db.session.add(a)
        artist_objs.append(a)

    db.session.flush()

    artworks = [
        ('Crimson Dreams', 'Abstract expressionist painting in deep reds and gold.', 2400.00, cat_objs[0].id, artist_objs[0].id),
        ('Urban Silence', 'Black and white cityscape at dawn.', 1200.00, cat_objs[1].id, artist_objs[1].id),
        ('Neural Garden', 'Digital artwork exploring organic AI patterns.', 800.00, cat_objs[3].id, artist_objs[2].id),
        ('Golden Hour', 'Oil on canvas, warm tones at sunset.', 3500.00, cat_objs[0].id, artist_objs[0].id),
        ('Concrete Jungle', 'Street photography series from New York.', 950.00, cat_objs[1].id, artist_objs[1].id),
        ('Binary Bloom', 'Generative digital art, limited edition print.', 600.00, cat_objs[3].id, artist_objs[2].id),
    ]
    for title, desc, price, cat_id, artist_id in artworks:
        art = Artwork(title=title, description=desc, price=price,
                      category_id=cat_id, artist_id=artist_id,
                      image_url='', is_available=True)
        db.session.add(art)

    db.session.commit()

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5002))
    app.run(debug=False, host='0.0.0.0', port=port)
