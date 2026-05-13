# CanvasCulture Studio

A full-featured art e-commerce web application built with Flask. Artists can list and sell their artworks, admins manage the entire platform, and customers can browse, cart, and checkout securely.

**Live Demo:** [canvassculture.up.railway.app](https://canvassculture.up.railway.app)

---

## Features

### For Customers
- Browse artworks in a filterable, sortable gallery
- Filter by category, artist, and price
- View detailed artwork pages with related works
- Add to cart (no login required)
- Secure checkout via PayU payment gateway
- Order confirmation with receipt

### For Artists
- Dedicated Artist Portal (`/artist/login`)
- Add, edit, and delete their own artworks
- Upload artwork images (stored on Cloudinary)
- Toggle artwork visibility (listed / hidden)
- View their public profile page
- Dashboard with stats — total artworks, listed, in orders

### For Admin
- Full dashboard with revenue, orders, and inventory stats
- Manage artworks (add, edit, delete, feature on homepage)
- Manage artists and create their portal login accounts
- Manage categories (add, rename, delete)
- Manage orders and update status (Pending → Confirmed → Shipped → Delivered)
- Hero carousel management — upload multiple slides, auto-advance every 7 seconds
- Edit homepage hero text (headline and badge label)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Flask 3.1 |
| Database | SQLite (local dev) / PostgreSQL (production) |
| ORM | Flask-SQLAlchemy |
| Auth | Flask-Login |
| Image Storage | Cloudinary (CDN, 25GB free) |
| Payment | PayU India payment gateway |
| Server | Gunicorn (production) |
| Hosting | Railway.app |
| Frontend | Jinja2 templates, vanilla CSS, Font Awesome |

---

## Project Structure

```
Art_E-commerce/
├── app.py               # App factory, Cloudinary config, Jinja2 filters
├── extensions.py        # SQLAlchemy + LoginManager singletons
├── models.py            # Database models
├── routes.py            # All route blueprints (main, admin, shop, artist)
├── wsgi.py              # Gunicorn entry point
├── Procfile             # Railway/Heroku process definition
├── requirements.txt     # Python dependencies
├── runtime.txt          # Python version pin
├── templates/
│   ├── base.html        # Base layout (navbar, footer, CSS variables)
│   ├── index.html       # Homepage with hero carousel
│   ├── gallery.html     # Artwork gallery with filters
│   ├── artists.html     # Artist listing
│   ├── admin/           # Admin panel templates
│   ├── artist/          # Artist portal templates
│   └── shop/            # Cart, checkout, payment templates
└── static/
    └── images/uploads/  # Local image storage (dev only)
```

---

## Architecture

### Blueprints

| Blueprint | Prefix | Purpose |
|---|---|---|
| `main` | `/` | Public pages — homepage, gallery, artists, contact |
| `admin_bp` | `/admin` | Admin panel — full platform management |
| `shop` | `/shop` | Cart, checkout, PayU integration |
| `artist_bp` | `/artist` | Artist portal — manage own artworks |

### Database Models

| Model | Purpose |
|---|---|
| `User` | Admin and artist login accounts |
| `Artist` | Artist profiles; linked to `User` via `user_id` for portal access |
| `Category` | Artwork categories |
| `Artwork` | Core catalogue; `is_featured` shows on homepage |
| `Order` | Customer purchase records |
| `OrderItem` | Individual items within an order |
| `HeroSlide` | Homepage carousel images |
| `SiteSettings` | Key-value CMS settings (hero text) |

### Image Storage Flow

```
Upload (admin/artist) → Cloudinary API → Permanent CDN URL → Saved in PostgreSQL
```

All images are stored on Cloudinary and served via their global CDN. Images survive redeploys and server restarts.

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/jayant1345/Art_E-COMMERCE.git
cd Art_E-COMMERCE
```

### 2. Create and activate virtual environment

```powershell
# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install dependencies

```powershell
.\venv\Scripts\pip install -r requirements.txt
```

### 4. Run the development server

```powershell
python app.py
```

App runs at **http://localhost:5002**

> On first run, the database is created automatically and seeded with sample data including an admin account, artists, categories, and artworks.

---

## Environment Variables

Set these in Railway dashboard (Variables tab) or in a local `.env` file:

| Variable | Description | Required |
|---|---|---|
| `SECRET_KEY` | Flask session secret key | Yes (production) |
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Railway) | Yes (production) |
| `CLOUDINARY_CLOUD_NAME` | Your Cloudinary cloud name | Yes |
| `CLOUDINARY_API_KEY` | Cloudinary API key | Yes |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | Yes |
| `PAYU_KEY` | PayU merchant key | Yes (live payments) |
| `PAYU_SALT` | PayU merchant salt | Yes (live payments) |
| `PAYU_MODE` | `test` or `live` | Yes |

---

## Default Admin Credentials

> **Change these immediately after first login in production.**

| Field | Value |
|---|---|
| URL | `/admin/login` |
| Email | `admin@gallery.com` |
| Password | `admin123` |

---

## Artist Portal

Artists do not self-register. Admin creates their portal account:

1. Go to `/admin` → **Artists** → **Edit** an artist
2. Fill in **Portal Email** and **Portal Password**
3. Artist can now log in at `/artist/login`

---

## Payment Integration (PayU India)

- Test mode is enabled by default (`PAYU_MODE=test`)
- Hash algorithm: SHA-512 (pipe-delimited fields)
- Payment flow: Checkout → PayU hosted page → Success/Failure callback
- Order is created in the database **only after** verified successful payment
- Switch to live: set `PAYU_MODE=live` and update `PAYU_KEY` / `PAYU_SALT`

---

## Deployment (Railway)

1. Push code to GitHub
2. Create a new Railway project → **Deploy from GitHub**
3. Add **PostgreSQL** plugin (auto-injects `DATABASE_URL`)
4. Add environment variables in Railway → Variables
5. Generate a public domain in Settings → Networking

Railway auto-deploys on every `git push` to `main`.

---

## Key URLs

| Page | URL |
|---|---|
| Homepage | `/` |
| Gallery | `/gallery` |
| Artists | `/artists` |
| Cart | `/shop/cart` |
| Admin Login | `/admin/login` |
| Admin Dashboard | `/admin` |
| Artist Login | `/artist/login` |
| Artist Dashboard | `/artist/dashboard` |
