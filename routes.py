from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, jsonify, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from extensions import db
from models import User, Artwork, Artist, Category, Order, OrderItem, SiteSettings, HeroSlide
import os, hashlib, time, uuid
from functools import wraps

main      = Blueprint('main', __name__)
admin_bp  = Blueprint('admin', __name__)
shop      = Blueprint('shop', __name__)
artist_bp = Blueprint('artist', __name__)


def artist_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.artist_profile:
            flash('Artist portal access required.', 'danger')
            return redirect(url_for('artist.login'))
        return f(*args, **kwargs)
    return decorated

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(f):
    return '.' in f.filename and f.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, app):
    if not file or not allowed_file(file):
        return ''
    import cloudinary, cloudinary.uploader
    if cloudinary.config().cloud_name:
        result = cloudinary.uploader.upload(file, folder='canvasculture', resource_type='image')
        return result['secure_url']
    # Local fallback (dev without Cloudinary configured)
    filename = f"{int(time.time())}_{secure_filename(file.filename)}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return f'images/uploads/{filename}'

def cart_items_and_total():
    cart  = session.get('cart', {})
    items, total = [], 0.0
    for art_id, qty in cart.items():
        artwork = Artwork.query.get(int(art_id))
        if artwork:
            subtotal = artwork.price * qty
            items.append({'artwork': artwork, 'qty': qty, 'subtotal': subtotal})
            total += subtotal
    return items, total

# ── PayU helpers ──────────────────────────────────────────────────────────────

def payu_generate_hash(params: dict, salt: str) -> str:
    """
    PayU hash formula (SHA-512):
    key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||salt
    """
    hash_str = (
        f"{params['key']}|{params['txnid']}|{params['amount']}|"
        f"{params['productinfo']}|{params['firstname']}|{params['email']}|"
        f"{params.get('udf1','')}|{params.get('udf2','')}|{params.get('udf3','')}|"
        f"{params.get('udf4','')}|{params.get('udf5','')}||||||{salt}"
    )
    return hashlib.sha512(hash_str.encode('utf-8')).hexdigest()

def payu_verify_hash(response: dict, salt: str) -> bool:
    """
    PayU reverse hash (SHA-512) for response verification:
    salt|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    """
    reverse_str = (
        f"{salt}|{response.get('status','')}|"
        f"|||||"
        f"|{response.get('udf5','')}|{response.get('udf4','')}|"
        f"{response.get('udf3','')}|{response.get('udf2','')}|"
        f"{response.get('udf1','')}|{response.get('email','')}|"
        f"{response.get('firstname','')}|{response.get('productinfo','')}|"
        f"{response.get('amount','')}|{response.get('txnid','')}|"
        f"{response.get('key','')}"
    )
    expected = hashlib.sha512(reverse_str.encode('utf-8')).hexdigest()
    return expected.lower() == response.get('hash', '').lower()

def payu_url():
    if current_app.config.get('PAYU_MODE') == 'live':
        return current_app.config['PAYU_URL_LIVE']
    return current_app.config['PAYU_URL_TEST']

# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@main.route('/')
def index():
    featured = Artwork.query.filter_by(is_featured=True, is_available=True).limit(6).all()
    if not featured:
        featured = Artwork.query.filter_by(is_available=True).limit(6).all()
    categories = Category.query.all()
    artists    = Artist.query.limit(3).all()
    hero_slides    = HeroSlide.query.order_by(HeroSlide.order, HeroSlide.id).all()
    hero_title     = SiteSettings.get('hero_title', 'Where Art Finds Its Collector')
    hero_sub       = SiteSettings.get('hero_sub', 'Curated Fine Art')
    count_artworks = Artwork.query.filter_by(is_available=True).count()
    count_artists  = Artist.query.count()
    count_orders   = Order.query.filter_by(payment_status='Paid').count()
    return render_template('index.html', featured=featured, categories=categories,
                           artists=artists, hero_slides=hero_slides,
                           hero_title=hero_title, hero_sub=hero_sub,
                           count_artworks=count_artworks,
                           count_artists=count_artists,
                           count_orders=count_orders)

@main.route('/gallery')
def gallery():
    cat_id    = request.args.get('category', type=int)
    artist_id = request.args.get('artist', type=int)
    sort      = request.args.get('sort', 'newest')
    query     = Artwork.query.filter_by(is_available=True)
    if cat_id:      query = query.filter_by(category_id=cat_id)
    if artist_id:   query = query.filter_by(artist_id=artist_id)
    if sort == 'price_asc':   query = query.order_by(Artwork.price.asc())
    elif sort == 'price_desc': query = query.order_by(Artwork.price.desc())
    else:                      query = query.order_by(Artwork.created_at.desc())
    categories = Category.query.all()
    artists    = Artist.query.all()
    return render_template('gallery.html', artworks=query.all(), categories=categories,
                           artists=artists, selected_cat=cat_id,
                           selected_artist=artist_id, sort=sort)

@main.route('/artwork/<int:id>')
def artwork_detail(id):
    artwork = Artwork.query.get_or_404(id)
    related = Artwork.query.filter_by(category_id=artwork.category_id, is_available=True)\
                           .filter(Artwork.id != id).limit(3).all()
    return render_template('artwork_detail.html', artwork=artwork, related=related)

@main.route('/artists')
def artists():
    return render_template('artists.html', artists=Artist.query.all())

@main.route('/artist/<int:id>')
def artist_detail(id):
    artist   = Artist.query.get_or_404(id)
    artworks = Artwork.query.filter_by(artist_id=id, is_available=True).all()
    return render_template('artist_detail.html', artist=artist, artworks=artworks)

@main.route('/contact')
def contact():
    return render_template('contact.html')

# ── CART ──────────────────────────────────────────────────────────────────────

@shop.route('/cart')
def cart():
    items, total = cart_items_and_total()
    return render_template('shop/cart.html', items=items, total=total)

@shop.route('/add/<int:art_id>', methods=['POST'])
def add_to_cart(art_id):
    cart      = session.get('cart', {})
    cart[str(art_id)] = cart.get(str(art_id), 0) + 1
    session['cart'] = cart
    flash('Artwork added to cart!', 'success')
    return redirect(request.referrer or url_for('main.gallery'))

@shop.route('/remove/<int:art_id>', methods=['POST'])
def remove_from_cart(art_id):
    cart = session.get('cart', {})
    cart.pop(str(art_id), None)
    session['cart'] = cart
    return redirect(url_for('shop.cart'))

@shop.route('/cart-count')
def cart_count():
    return jsonify({'count': sum(session.get('cart', {}).values())})

# ── CHECKOUT → build PayU form and POST to PayU ───────────────────────────────

@shop.route('/checkout', methods=['GET', 'POST'])
def checkout():
    items, total = cart_items_and_total()
    if not items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('shop.cart'))

    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, email, phone, address]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('shop/checkout.html', items=items, total=total)

        # Generate unique transaction ID
        txnid = f"LUM{int(time.time())}{uuid.uuid4().hex[:6].upper()}"

        # Save pending order info in session (we create DB record after PayU confirms)
        session['pending_order'] = {
            'txnid': txnid, 'name': name, 'email': email,
            'phone': phone, 'address': address, 'total': total
        }

        key  = current_app.config['PAYU_KEY']
        salt = current_app.config['PAYU_SALT']

        # Build PayU params
        payu_params = {
            'key':         key,
            'txnid':       txnid,
            'amount':      f"{total:.2f}",
            'productinfo': 'CanvasCulture Studio Purchase',
            'firstname':   name.split()[0],
            'email':       email,
            'phone':       phone,
            'surl':        url_for('shop.payment_success', _external=True),
            'furl':        url_for('shop.payment_failure', _external=True),
            'udf1':        '',
            'udf2':        '',
            'udf3':        '',
            'udf4':        '',
            'udf5':        '',
        }
        payu_params['hash'] = payu_generate_hash(payu_params, salt)

        return render_template('shop/payment.html',
                               payu_url=payu_url(),
                               payu_params=payu_params,
                               items=items, total=total,
                               customer_name=name, customer_email=email)

    return render_template('shop/checkout.html', items=items, total=total)

# ── PAYU SUCCESS CALLBACK ─────────────────────────────────────────────────────

@shop.route('/payment/success', methods=['POST'])
def payment_success():
    data = request.form.to_dict()
    salt = current_app.config['PAYU_SALT']

    # Verify hash from PayU
    if not payu_verify_hash(data, salt):
        flash('Payment verification failed. Please contact support.', 'danger')
        return redirect(url_for('shop.cart'))

    if data.get('status') != 'success':
        flash(f"Payment was not successful: {data.get('error_Message', 'Unknown error')}", 'danger')
        return redirect(url_for('shop.cart'))

    # Check if this transaction already saved (prevent duplicate)
    existing = Order.query.filter_by(payu_txnid=data.get('txnid')).first()
    if existing:
        return redirect(url_for('shop.order_success', order_id=existing.id))

    pending = session.get('pending_order', {})
    items, _ = cart_items_and_total()

    order = Order(
        customer_name    = pending.get('name', data.get('firstname', '')),
        customer_email   = pending.get('email', data.get('email', '')),
        customer_phone   = pending.get('phone', data.get('phone', '')),
        customer_address = pending.get('address', ''),
        total            = float(data.get('amount', pending.get('total', 0))),
        status           = 'Confirmed',
        payment_status   = 'Paid',
        payu_txnid       = data.get('txnid'),
        payu_mihpayid    = data.get('mihpayid'),
        payu_mode        = data.get('mode'),
        payu_status      = data.get('status'),
    )
    db.session.add(order)
    db.session.flush()

    for item in items:
        db.session.add(OrderItem(
            order_id   = order.id,
            artwork_id = item['artwork'].id,
            quantity   = item['qty'],
            price      = item['artwork'].price
        ))

    db.session.commit()
    session['cart']          = {}
    session['pending_order'] = None

    flash(f'Payment successful! Order #{order.id} confirmed.', 'success')
    return redirect(url_for('shop.order_success', order_id=order.id))

# ── PAYU FAILURE CALLBACK ─────────────────────────────────────────────────────

@shop.route('/payment/failure', methods=['POST'])
def payment_failure():
    data    = request.form.to_dict()
    reason  = data.get('error_Message') or data.get('field9') or 'Payment was declined'
    txnid   = data.get('txnid', '')
    flash(f'Payment failed: {reason}', 'danger')
    return render_template('shop/payment_failed.html', reason=reason, txnid=txnid)

# ── ORDER SUCCESS PAGE ────────────────────────────────────────────────────────

@shop.route('/order-success/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('shop/order_success.html', order=order)

# ── ADMIN ─────────────────────────────────────────────────────────────────────

@admin_bp.before_request
def require_admin():
    if request.endpoint in ('admin.login',):
        return
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for('admin.login'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password')) and user.is_admin:
            login_user(user)
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@login_required
def dashboard():
    if not current_user.is_admin:
        return redirect(url_for('main.index'))
    revenue = db.session.query(db.func.sum(Order.total)).filter_by(payment_status='Paid').scalar() or 0
    return render_template('admin/dashboard.html',
        total_artworks = Artwork.query.count(),
        total_orders   = Order.query.count(),
        total_artists  = Artist.query.count(),
        pending_orders = Order.query.filter_by(status='Pending').count(),
        recent_orders  = Order.query.order_by(Order.created_at.desc()).limit(5).all(),
        revenue        = revenue)

@admin_bp.route('/artworks')
@login_required
def artworks():
    return render_template('admin/artworks.html',
                           artworks=Artwork.query.order_by(Artwork.created_at.desc()).all())

@admin_bp.route('/artworks/add', methods=['GET', 'POST'])
@login_required
def add_artwork():
    categories = Category.query.all(); artists = Artist.query.all()
    if request.method == 'POST':
        image_url = save_image(request.files.get('image'), current_app) if 'image' in request.files else ''
        db.session.add(Artwork(
            title=request.form['title'], description=request.form['description'],
            price=float(request.form['price']), medium=request.form.get('medium'),
            dimensions=request.form.get('dimensions'), year=request.form.get('year', type=int),
            stock=int(request.form.get('stock', 1)),
            is_featured='is_featured' in request.form, is_available='is_available' in request.form,
            category_id=request.form.get('category_id', type=int),
            artist_id=request.form.get('artist_id', type=int), image_url=image_url))
        db.session.commit()
        flash('Artwork added!', 'success')
        return redirect(url_for('admin.artworks'))
    return render_template('admin/artwork_form.html', categories=categories, artists=artists, artwork=None)

@admin_bp.route('/artworks/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_artwork(id):
    artwork = Artwork.query.get_or_404(id)
    categories = Category.query.all(); artists = Artist.query.all()
    if request.method == 'POST':
        artwork.title=request.form['title']; artwork.description=request.form['description']
        artwork.price=float(request.form['price']); artwork.medium=request.form.get('medium')
        artwork.dimensions=request.form.get('dimensions'); artwork.year=request.form.get('year',type=int)
        artwork.stock=int(request.form.get('stock',1))
        artwork.is_featured='is_featured' in request.form; artwork.is_available='is_available' in request.form
        artwork.category_id=request.form.get('category_id',type=int); artwork.artist_id=request.form.get('artist_id',type=int)
        if 'image' in request.files and request.files['image'].filename:
            artwork.image_url = save_image(request.files['image'], current_app)
        db.session.commit(); flash('Artwork updated!', 'success')
        return redirect(url_for('admin.artworks'))
    return render_template('admin/artwork_form.html', categories=categories, artists=artists, artwork=artwork)

@admin_bp.route('/artworks/delete/<int:id>', methods=['POST'])
@login_required
def delete_artwork(id):
    artwork = Artwork.query.get_or_404(id)
    db.session.delete(artwork); db.session.commit()
    flash('Artwork deleted.', 'success')
    return redirect(url_for('admin.artworks'))

@admin_bp.route('/artists')
@login_required
def artists():
    return render_template('admin/artists.html', artists=Artist.query.all())

@admin_bp.route('/artists/add', methods=['GET', 'POST'])
def add_artist():
    if request.method == 'POST':
        photo_url = save_image(request.files.get('photo'), current_app) if 'photo' in request.files else ''
        artist = Artist(name=request.form['name'], bio=request.form['bio'], photo_url=photo_url)
        db.session.add(artist)

        portal_email    = request.form.get('portal_email', '').strip()
        portal_password = request.form.get('portal_password', '').strip()
        if portal_email and portal_password:
            if User.query.filter_by(email=portal_email).first():
                flash('Portal email already in use by another account.', 'danger')
                return render_template('admin/artist_form.html', artist=None)
            username = f"artist_{int(time.time())}"
            user = User(username=username, email=portal_email,
                        password=generate_password_hash(portal_password), is_admin=False)
            db.session.add(user)
            db.session.flush()
            artist.user_id = user.id

        db.session.commit()
        flash('Artist added!', 'success')
        return redirect(url_for('admin.artists'))
    return render_template('admin/artist_form.html', artist=None)

@admin_bp.route('/artists/edit/<int:id>', methods=['GET', 'POST'])
def edit_artist(id):
    artist = Artist.query.get_or_404(id)
    if request.method == 'POST':
        artist.name = request.form['name']
        artist.bio  = request.form['bio']
        if 'photo' in request.files and request.files['photo'].filename:
            artist.photo_url = save_image(request.files['photo'], current_app)

        portal_email    = request.form.get('portal_email', '').strip()
        portal_password = request.form.get('portal_password', '').strip()

        if artist.account:
            if portal_email:
                artist.account.email = portal_email
            if portal_password:
                artist.account.password = generate_password_hash(portal_password)
        elif portal_email and portal_password:
            if User.query.filter_by(email=portal_email).first():
                flash('Portal email already in use by another account.', 'danger')
                return render_template('admin/artist_form.html', artist=artist)
            username = f"artist_{int(time.time())}"
            user = User(username=username, email=portal_email,
                        password=generate_password_hash(portal_password), is_admin=False)
            db.session.add(user)
            db.session.flush()
            artist.user_id = user.id

        db.session.commit()
        flash('Artist updated!', 'success')
        return redirect(url_for('admin.artists'))
    return render_template('admin/artist_form.html', artist=artist)

@admin_bp.route('/artists/delete/<int:id>', methods=['POST'])
def delete_artist(id):
    artist = Artist.query.get_or_404(id)
    portal_user = artist.account
    db.session.delete(artist)
    if portal_user:
        db.session.delete(portal_user)
    db.session.commit()
    flash('Artist deleted.', 'success')
    return redirect(url_for('admin.artists'))

@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if request.method == 'POST':
        db.session.add(Category(name=request.form['name']))
        db.session.commit(); flash('Category added!', 'success')
    return render_template('admin/categories.html', categories=Category.query.all())

@admin_bp.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
def edit_category(id):
    cat = Category.query.get_or_404(id)
    new_name = request.form.get('name', '').strip()
    if new_name:
        cat.name = new_name
        db.session.commit()
        flash(f'Category renamed to "{new_name}".', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    cat = Category.query.get_or_404(id)
    if cat.artworks:
        flash(f'Cannot delete "{cat.name}" — it has {len(cat.artworks)} artwork(s) assigned.', 'danger')
        return redirect(url_for('admin.categories'))
    db.session.delete(cat)
    db.session.commit()
    flash(f'Category "{cat.name}" deleted.', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/orders')
@login_required
def orders():
    return render_template('admin/orders.html',
                           orders=Order.query.order_by(Order.created_at.desc()).all())

@admin_bp.route('/orders/<int:id>')
@login_required
def order_detail(id):
    return render_template('admin/order_detail.html', order=Order.query.get_or_404(id))

@admin_bp.route('/orders/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    order = Order.query.get_or_404(id)
    order.status = request.form['status']
    db.session.commit(); flash('Order status updated!', 'success')
    return redirect(url_for('admin.order_detail', id=id))

# ── SITE SETTINGS ─────────────────────────────────────────────────────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')

        # Upload one or multiple slides
        if action == 'add_slides':
            files = request.files.getlist('slides')
            added = 0
            next_order = (db.session.query(db.func.max(HeroSlide.order)).scalar() or 0) + 1
            for f in files:
                if f and f.filename:
                    url = save_image(f, current_app)
                    if url:
                        db.session.add(HeroSlide(image_url=url, order=next_order))
                        next_order += 1
                        added += 1
            db.session.commit()
            flash(f'{added} slide{"s" if added != 1 else ""} added!', 'success')

        # Delete a slide
        elif action == 'delete_slide':
            slide = HeroSlide.query.get_or_404(request.form.get('slide_id', type=int))
            db.session.delete(slide)
            db.session.commit()
            flash('Slide removed.', 'success')

        # Save hero text
        elif action == 'save_text':
            title = request.form.get('hero_title', '').strip()
            sub   = request.form.get('hero_sub', '').strip()
            if title: SiteSettings.set('hero_title', title)
            if sub:   SiteSettings.set('hero_sub', sub)
            flash('Hero text saved!', 'success')

        return redirect(url_for('admin.settings'))

    slides = HeroSlide.query.order_by(HeroSlide.order, HeroSlide.id).all()
    return render_template('admin/settings.html',
        slides     = slides,
        hero_title = SiteSettings.get('hero_title', 'Where Art Finds Its Collector'),
        hero_sub   = SiteSettings.get('hero_sub',   'Curated Fine Art'),
    )

# ── ARTIST PORTAL ─────────────────────────────────────────────────────────────

@artist_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and current_user.artist_profile:
        return redirect(url_for('artist.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password', '')) and user.artist_profile:
            login_user(user)
            return redirect(url_for('artist.dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('artist/login.html')

@artist_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('artist.login'))

@artist_bp.route('/dashboard')
@artist_required
def dashboard():
    artist   = current_user.artist_profile
    artworks = Artwork.query.filter_by(artist_id=artist.id).order_by(Artwork.created_at.desc()).all()
    sold_ids = {oi.artwork_id for oi in OrderItem.query.all()}
    return render_template('artist/dashboard.html', artist=artist, artworks=artworks, sold_ids=sold_ids)

@artist_bp.route('/artwork/add', methods=['GET', 'POST'])
@artist_required
def add_artwork():
    categories = Category.query.all()
    if request.method == 'POST':
        image_url = save_image(request.files.get('image'), current_app) if 'image' in request.files else ''
        db.session.add(Artwork(
            title       = request.form['title'],
            description = request.form.get('description', ''),
            price       = float(request.form['price']),
            medium      = request.form.get('medium', ''),
            dimensions  = request.form.get('dimensions', ''),
            year        = request.form.get('year', type=int),
            stock       = int(request.form.get('stock', 1)),
            is_available= 'is_available' in request.form,
            is_featured = False,
            category_id = request.form.get('category_id', type=int),
            artist_id   = current_user.artist_profile.id,
            image_url   = image_url,
        ))
        db.session.commit()
        flash('Artwork submitted and listed!', 'success')
        return redirect(url_for('artist.dashboard'))
    return render_template('artist/artwork_form.html', categories=categories, artwork=None)

@artist_bp.route('/artwork/<int:id>/edit', methods=['GET', 'POST'])
@artist_required
def edit_artwork(id):
    artwork = Artwork.query.get_or_404(id)
    if artwork.artist_id != current_user.artist_profile.id:
        flash('You can only edit your own artworks.', 'danger')
        return redirect(url_for('artist.dashboard'))
    categories = Category.query.all()
    if request.method == 'POST':
        artwork.title       = request.form['title']
        artwork.description = request.form.get('description', '')
        artwork.price       = float(request.form['price'])
        artwork.medium      = request.form.get('medium', '')
        artwork.dimensions  = request.form.get('dimensions', '')
        artwork.year        = request.form.get('year', type=int)
        artwork.stock       = int(request.form.get('stock', 1))
        artwork.is_available= 'is_available' in request.form
        artwork.category_id = request.form.get('category_id', type=int)
        if 'image' in request.files and request.files['image'].filename:
            artwork.image_url = save_image(request.files['image'], current_app)
        db.session.commit()
        flash('Artwork updated!', 'success')
        return redirect(url_for('artist.dashboard'))
    return render_template('artist/artwork_form.html', categories=categories, artwork=artwork)

@artist_bp.route('/artwork/<int:id>/delete', methods=['POST'])
@artist_required
def delete_artwork(id):
    artwork = Artwork.query.get_or_404(id)
    if artwork.artist_id != current_user.artist_profile.id:
        flash('You can only delete your own artworks.', 'danger')
        return redirect(url_for('artist.dashboard'))
    db.session.delete(artwork)
    db.session.commit()
    flash('Artwork removed.', 'success')
    return redirect(url_for('artist.dashboard'))

