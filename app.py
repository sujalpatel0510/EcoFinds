from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

# -------------------------
# Flask Setup
# -------------------------
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:8511@localhost/ecofindsdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# -------------------------
# File upload configuration
# -------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------
# Database & Migrations
# -------------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# -------------------------
# Context Processor
# -------------------------
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# -------------------------
# Helpers
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    """Save uploaded image file and return filename. If none, return None."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

# -------------------------
# Models
# -------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', back_populates='owner', cascade='all, delete-orphan')
    cart_items = db.relationship('Cart', back_populates='user', cascade='all, delete-orphan')
    purchases = db.relationship('Purchase', back_populates='user', cascade='all, delete-orphan')


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(200), default='default.png')  # filename only
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', back_populates='products')


class Cart(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)

    user = db.relationship('User', back_populates='cart_items')
    product = db.relationship('Product')


class Purchase(db.Model):
    __tablename__ = "purchases"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='purchases')
    product = db.relationship('Product')


# -------------------------
# Create tables at startup
# -------------------------
with app.app_context():
    db.create_all()


# -------------------------
# Routes
# -------------------------
@app.route('/')
def home():
    products = Product.query.all()
    return render_template('home.html', products=products)


# ---------- AUTH ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password1 = request.form['password1']
        password2 = request.form['password2']

        if password1 != password2:
            flash("Passwords do not match", "danger")
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash("Email already exists", "danger")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password1)
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash("Signup successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('dashboard', user_id=user.id))
        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))


# ---------- DASHBOARD ----------
@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('dashboard.html', user=user)


@app.route('/dashboard/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        new_password = request.form.get('password')
        if new_password:
            user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for('dashboard', user_id=user.id))
    return render_template('edit_user.html', user=user)


# ---------- PRODUCTS ----------
@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        image_file = request.files.get('image')
        filename = save_image(image_file) or 'default.png'

        product = Product(
            title=request.form['title'],
            description=request.form['description'],
            category=request.form['category'],
            price=float(request.form['price']),
            image=filename,
            user_id=int(request.form['user_id'])
        )
        db.session.add(product)
        db.session.commit()
        flash("Product added!", "success")
        return redirect(url_for('home'))
    return render_template('add_product.html')


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)


@app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.title = request.form['title']
        product.description = request.form['description']
        product.category = request.form['category']
        product.price = float(request.form['price'])

        image_file = request.files.get('image')
        filename = save_image(image_file)
        if filename:
            product.image = filename

        db.session.commit()
        flash("Product updated!", "success")
        return redirect(url_for('product_detail', product_id=product.id))
    return render_template('edit_product.html', product=product)


@app.route('/product/<int:product_id>/delete')
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted!", "danger")
    return redirect(url_for('home'))


# ---------- CART ----------
@app.route('/cart/<int:user_id>')
def view_cart(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        flash("Please login to view your cart.", "warning")
        return redirect(url_for('login'))

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    total_price = sum(item.product.price for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, user_id=user_id, total_price=total_price)


@app.route('/cart/add/<int:user_id>/<int:product_id>')
def add_to_cart(user_id, product_id):
    item = Cart(user_id=user_id, product_id=product_id)
    db.session.add(item)
    db.session.commit()
    flash("Product added to cart!", "success")
    return redirect(url_for('view_cart', user_id=user_id))


@app.route('/cart/remove/<int:item_id>')
def remove_from_cart(item_id):
    item = Cart.query.get_or_404(item_id)
    user_id = item.user_id
    db.session.delete(item)
    db.session.commit()
    flash("Removed from cart!", "danger")
    return redirect(url_for('view_cart', user_id=user_id))


# ---------- PURCHASES ----------
@app.route('/purchase/<int:user_id>/<int:product_id>')
def purchase(user_id, product_id):
    purchase = Purchase(user_id=user_id, product_id=product_id)
    db.session.add(purchase)
    Cart.query.filter_by(user_id=user_id, product_id=product_id).delete()
    db.session.commit()
    flash("Purchase successful!", "success")
    return redirect(url_for('view_purchases', user_id=user_id))


@app.route('/purchases/<int:user_id>')
def view_purchases(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        flash("Please login to view your purchases.", "warning")
        return redirect(url_for('login'))

    purchases = Purchase.query.filter_by(user_id=user_id).all()
    return render_template('purchases.html', purchases=purchases, user_id=user_id)


# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
