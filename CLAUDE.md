# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```powershell
# Activate venv (Windows)
.\venv\Scripts\activate

# Run dev server (port 5002)
python app.py
# or
python run.py
```

The app runs on **http://localhost:5002**. Port 5000 is reserved by another process.

## Installing Dependencies

```powershell
.\venv\Scripts\pip install -r requirements.txt
```

## Architecture

### Module Split (critical to understand)

`db` and `login_manager` live in **`extensions.py`** — not in `app.py`. This prevents the dual-import bug where running `python app.py` as `__main__` causes `models.py`'s `from app import db` to re-import `app.py` as a second module, creating two SQLAlchemy instances. Always import from `extensions`, never from `app`.

### Request Flow

```
app.py  →  create_app() factory
             ├── extensions.py  (db, login_manager singletons)
             ├── models.py      (imports from extensions)
             └── routes.py      (imports from extensions + models)
                  ├── Blueprint: main      (public pages, url prefix: /)
                  ├── Blueprint: admin_bp  (admin panel, url prefix: /admin)
                  └── Blueprint: shop      (cart/checkout/PayU, url prefix: /shop)
```

### Database

- SQLite, stored at `instance/canvasculture.db`
- `db.create_all()` + seed data runs automatically on first startup via `_seed_data()` in `app.py`
- **No migration tool** — schema changes require deleting `instance/canvasculture.db` and restarting to reseed
- Default admin: `admin@gallery.com` / `admin123`

### Models (`models.py`)

| Model | Purpose |
|---|---|
| `User` | Admin accounts only; `is_admin=True` required for admin access |
| `Artist` | Gallery artists with optional `photo_url` |
| `Category` | Artwork categories; cannot delete if artworks assigned |
| `Artwork` | Core catalogue; `is_featured` controls homepage display |
| `Order` / `OrderItem` | Purchase records; status flow: Pending → Confirmed → Shipped → Delivered |
| `HeroSlide` | Homepage carousel images, ordered by `order` column then `id` |
| `SiteSettings` | Key-value store for CMS settings (`hero_title`, `hero_sub`); use `SiteSettings.get(key)` / `SiteSettings.set(key, value)` static helpers |

### PayU Payment Integration

- Hash generation: `payu_generate_hash()` in `routes.py` — SHA-512 of pipe-delimited fields
- Response verification: `payu_verify_hash()` — reverse field order, compare against PayU's returned hash
- Flow: checkout POST → build params + hash → render `shop/payment.html` (auto-submits form to PayU after 2s) → PayU POSTs back to `/shop/payment/success` or `/shop/payment/failure`
- Pending order stored in `session['pending_order']` during PayU redirect; DB record created only after verified success callback
- Switch to live: set `PAYU_MODE = 'live'` and replace `PAYU_KEY` / `PAYU_SALT` in `app.py`

### Template Hierarchy

```
base.html                  ← all public pages extend this
admin/base_admin.html      ← extends base.html; adds sidebar, hides footer, defines {% block admin_content %}
  └── all admin/*.html     ← extend base_admin.html using {% block admin_content %}
```

The admin layout uses `position: sticky` sidebar (`top: 68px; height: calc(100vh - 68px)`) and hides the public footer via `footer { display: none !important }`. Do not add `height` or `overflow: hidden` to `.admin-layout` — this causes content to render off-screen.

### Static Files & Image Uploads

- Uploaded files saved to `static/images/uploads/` with a `{timestamp}_{original_name}` filename
- `image_url` fields store the path relative to `static/` (e.g. `images/uploads/1234_foo.jpg`)
- Render in templates: `url_for('static', filename=artwork.image_url)`
- Allowed types: `png`, `jpg`, `jpeg`, `gif`, `webp`; max 16MB

### CSS Design Tokens (`base.html` `:root`)

All pages share CSS variables. Key ones:
- `--navy: #1e3050` — primary text/button colour
- `--amber: #c07c2e` — accent, prices, labels
- `--bg: #e8dfd4` — warm clay page background
- `--bg-2: #f2e9de` — card/form background
- `--bg-3: #ddd3c6` — section/alternate background
- `--font-serif: 'Playfair Display'` — headings and prices
- `--font-sans: 'DM Sans'` — body text

### Cart

Cart is stored entirely in Flask `session` as `{artwork_id: quantity}`. No login required to add to cart. Cart is cleared after successful payment.
