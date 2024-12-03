from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
import os
import json
import random
from models import db, User, ChatMessage
from chat_routes import chat_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop_v2.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'PATCH', 'DELETE']

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

# Register blueprints
app.register_blueprint(chat_bp)

# Configure CSRF protection
csrf.exempt('/api/cart/add')  # Exempt the cart API from CSRF protection

# Configure login manager
login_manager.login_view = 'login'

# Template filters
@app.template_filter('truncate_description')
def truncate_description(text):
    if len(text) > 100:
        return text[:97] + '...'
    return text

# Models
class Seller(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    instagram_link = db.Column(db.String(200), nullable=True)
    products = db.relationship('Product', backref='seller', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'shop_name': self.shop_name,
            'user_id': self.user_id,
            'description': self.description,
            'status': self.status,
            'instagram_link': self.instagram_link,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class ShippingAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'phone': self.phone,
            'is_default': self.is_default
        }

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    products = db.relationship('Product', backref=db.backref('category', lazy=True))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(200), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # New field for soft delete
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    @property
    def display_image(self):
        if not self.image_url:
            return url_for('static', filename='images/default-product.jpg')
        
        # Check if it's already a full URL
        if self.image_url.startswith(('http://', 'https://')):
            return self.image_url
            
        # Otherwise treat it as a local file
        return url_for('static', filename=f'images/{self.image_url}')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_ordered = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending')
    total_amount = db.Column(db.Float, nullable=False)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Template context processors
@app.context_processor
def utility_processor():
    def get_categories():
        return Category.query.order_by(Category.name).all()
    return dict(get_categories=get_categories)

# Routes
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Get category filter
    category_id = request.args.get('category', type=int)
    
    # Base query
    query = Product.query.filter(Product.is_active == True)
    
    # Apply category filter if specified
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Get paginated products
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all categories for the filter dropdown
    categories = Category.query.all()
    selected_category = Category.query.get(category_id) if category_id else None
    
    return render_template('index.html', 
                         products=products,
                         categories=categories,
                         selected_category=selected_category)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index', login_success=True))
        else:
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Basic validation for required user fields
        if not all([username, email, password, confirm_password]):
            flash('Please fill in all required account fields')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Create user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        
        # Validate shipping information if provided
        shipping_fields = ['full_name', 'address', 'city', 'state', 'zip_code', 'phone']
        shipping_data = {field: request.form.get(field) for field in shipping_fields}
        
        if any(shipping_data.values()):  # If any shipping field is filled
            if not all(shipping_data.values()):  # Check if all shipping fields are filled
                flash('Please fill in all shipping information fields or leave them all empty')
                return redirect(url_for('register'))
            
            # Create shipping address
            address = ShippingAddress(
                user=user,
                full_name=shipping_data['full_name'],
                address=shipping_data['address'],
                city=shipping_data['city'],
                state=shipping_data['state'],
                zip_code=shipping_data['zip_code'],
                phone=shipping_data['phone'],
                is_default=True
            )
            db.session.add(address)
        
        try:
            db.session.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/cart')
@login_required
def cart():
    # Get cart items with product information
    cart_items = db.session.query(CartItem, Product).join(
        Product, CartItem.product_id == Product.id
    ).filter(CartItem.user_id == current_user.id).all()
    
    # Calculate total
    total = sum(item.quantity * product.price for item, product in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/api/cart/items', methods=['GET'])
@login_required
def get_cart_items():
    cart_items = db.session.query(CartItem, Product).join(
        Product, CartItem.product_id == Product.id
    ).filter(CartItem.user_id == current_user.id).all()
    
    items = []
    total = 0
    for cart_item, product in cart_items:
        item_total = cart_item.quantity * product.price
        total += item_total
        items.append({
            'id': cart_item.id,
            'product_id': product.id,
            'name': product.name,
            'price': product.price,
            'quantity': cart_item.quantity,
            'image_url': product.image_url or url_for('static', filename='images/default-product.jpg'),
            'total': item_total
        })
    
    return jsonify({
        'items': items,
        'total': total
    })

@app.route('/api/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    
    # Verify ownership
    if cart_item.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data or 'quantity' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    
    try:
        quantity = int(data['quantity'])
        if quantity <= 0:
            db.session.delete(cart_item)
        else:
            # Check stock
            if quantity > cart_item.product.stock:
                return jsonify({'error': f'Only {cart_item.product.stock} items available'}), 400
            cart_item.quantity = quantity
            
        db.session.commit()
        return jsonify({'message': 'Cart updated successfully'})
    except ValueError:
        return jsonify({'error': 'Invalid quantity'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update cart'}), 500

@app.route('/api/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_cart_item(item_id):
    cart_item = CartItem.query.get_or_404(item_id)
    
    # Verify ownership
    if cart_item.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({'message': 'Item removed from cart'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to remove item'}), 500

@app.route('/shipping-addresses', methods=['GET', 'POST'])
@login_required
def shipping_addresses():
    if request.method == 'POST':
        # Get form data
        address_data = {
            'full_name': current_user.username,  # Use current user's name
            'address': request.form.get('address'),
            'city': request.form.get('city'),
            'state': request.form.get('state'),
            'zip_code': request.form.get('zip_code'),
            'phone': current_user.phone or request.form.get('phone', ''),  # Use user's phone or form data
            'is_default': bool(request.form.get('is_default'))
        }
        
        # If this is set as default, remove default from other addresses
        if address_data['is_default']:
            ShippingAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
        
        # Create new address
        new_address = ShippingAddress(user_id=current_user.id, **address_data)
        db.session.add(new_address)
        
        # Update user's phone if not set
        if not current_user.phone and address_data['phone']:
            current_user.phone = address_data['phone']
        
        db.session.commit()
        
        flash('Shipping address added successfully!', 'success')
        return redirect(url_for('shipping_addresses'))
    
    addresses = ShippingAddress.query.filter_by(user_id=current_user.id).order_by(ShippingAddress.is_default.desc()).all()
    return render_template('shipping_addresses.html', addresses=addresses)

@app.route('/shipping-addresses/delete/<int:address_id>', methods=['POST'])
@login_required
def delete_shipping_address(address_id):
    address = ShippingAddress.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()
    db.session.delete(address)
    db.session.commit()
    flash('Address deleted successfully!', 'success')
    return redirect(url_for('shipping_addresses'))

@app.route('/shipping-addresses/set-default/<int:address_id>', methods=['POST'])
@login_required
def set_default_address(address_id):
    # Remove default from all addresses
    ShippingAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
    
    # Set new default
    address = ShippingAddress.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()
    address.is_default = True
    db.session.commit()
    
    flash('Default address updated successfully!', 'success')
    return redirect(url_for('shipping_addresses'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    # Get cart items with product information
    cart_items = db.session.query(CartItem, Product).join(
        Product, CartItem.product_id == Product.id
    ).filter(CartItem.user_id == current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('cart'))
    
    # Calculate total
    total = sum(item.quantity * product.price for item, product in cart_items)
    
    if request.method == 'POST':
        # Get shipping address
        address_id = request.form.get('shipping_address')
        if not address_id:
            flash('Please select a shipping address.', 'error')
            return redirect(url_for('checkout'))
        
        shipping_address = ShippingAddress.query.get_or_404(address_id)
        if shipping_address.user_id != current_user.id:
            flash('Invalid shipping address.', 'error')
            return redirect(url_for('checkout'))
        
        try:
            # First, verify stock for all items
            for cart_item, product in cart_items:
                if cart_item.quantity > product.stock:
                    flash(f'Sorry, {product.name} only has {product.stock} items in stock.', 'error')
                    return redirect(url_for('cart'))
            
            # Create order
            order = Order(
                user_id=current_user.id,
                total_amount=total,
                status='pending'
            )
            db.session.add(order)
            db.session.flush()  # This assigns an ID to the order without committing
            
            # Create order items and update stock
            for cart_item, product in cart_items:
                # Create order item
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=cart_item.quantity,
                    price=product.price
                )
                db.session.add(order_item)
                
                # Update product stock
                product.stock -= cart_item.quantity
                
                # Delete cart item
                db.session.delete(cart_item)
            
            # Commit all changes
            db.session.commit()
            flash('Order placed successfully!', 'success')
            return redirect(url_for('order_detail', order_id=order.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error placing order: {str(e)}")
            flash('Error placing order. Please try again.', 'error')
            return redirect(url_for('checkout'))
    
    # GET request
    addresses = ShippingAddress.query.filter_by(user_id=current_user.id).order_by(ShippingAddress.is_default.desc()).all()
    if not addresses:
        flash('Please add a shipping address before checkout.', 'warning')
        return redirect(url_for('shipping_addresses'))
    
    return render_template('checkout.html', cart_items=cart_items, total=total, addresses=addresses)

@app.route('/api/cart/add', methods=['POST'])
@login_required
def api_add_to_cart():
    """Add a product to the cart"""
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid request data'}), 400
        
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        if not product_id:
            return jsonify({'error': 'Product ID is required'}), 400
        
        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return jsonify({'error': 'Quantity must be greater than 0'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid quantity'}), 400
        
        # Get the product
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if product is in stock
        if product.stock <= 0:
            return jsonify({'error': 'Product is out of stock'}), 400
        
        # Check if adding to cart would exceed stock
        cart_item = CartItem.query.filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).first()
        
        new_quantity = quantity
        if cart_item:
            new_quantity += cart_item.quantity
        
        if new_quantity > product.stock:
            return jsonify({'error': f'Cannot add {quantity} more items. Only {product.stock} available.'}), 400
        
        # Update or create cart item
        if cart_item:
            cart_item.quantity = new_quantity
        else:
            cart_item = CartItem(
                user_id=current_user.id,
                product_id=product_id,
                quantity=quantity
            )
            db.session.add(cart_item)
        
        db.session.commit()
        
        # Get updated cart count
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        
        return jsonify({
            'message': 'Product added to cart successfully',
            'cart_count': cart_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to cart: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/orders')
@login_required
def orders():
    # Get all orders for the current user with their items
    user_orders = db.session.query(Order).filter_by(
        user_id=current_user.id
    ).order_by(Order.date_ordered.desc()).all()
    
    return render_template('orders.html', orders=user_orders)

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    # Get the order and verify ownership
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('orders'))
    
    # Get order items with product information
    order_items = db.session.query(OrderItem, Product).join(
        Product, OrderItem.product_id == Product.id
    ).filter(OrderItem.order_id == order_id).all()
    
    return render_template('order_detail.html', order=order, order_items=order_items)

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    products = Product.query.all()
    categories = Category.query.all()
    return render_template('admin/dashboard.html', products=products, categories=categories)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        image_url = request.form.get('image_url')
        if not image_url:
            image_url = None  # This will trigger the default image
            
        product = Product(
            name=request.form.get('name'),
            description=request.form.get('description'),
            price=float(request.form.get('price')),
            stock=int(request.form.get('stock')),
            image_url=image_url,
            category_id=int(request.form.get('category_id'))
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully!')
        return redirect(url_for('admin_dashboard'))
        
    categories = Category.query.all()
    return render_template('admin/add_product.html', categories=categories)

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        image_url = request.form.get('image_url')
        if not image_url:
            image_url = None  # This will trigger the default image
            
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.stock = int(request.form.get('stock'))
        product.image_url = image_url
        product.category_id = int(request.form.get('category_id'))
        
        db.session.commit()
        flash('Product updated successfully!')
        return redirect(url_for('admin_dashboard'))
        
    categories = Category.query.all()
    return render_template('admin/edit_product.html', product=product, categories=categories)

@app.route('/admin/product/delete/<int:id>')
@login_required
def delete_product(id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
        
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    flash('Product deleted successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-category', methods=['POST'])
@login_required
def add_category():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if Category.query.filter_by(name=name).first():
        flash('Category already exists.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    category = Category(name=name)
    db.session.add(category)
    db.session.commit()
    
    flash('Category added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    # Search for products that match the query
    products = Product.query.filter(
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%'),
            Product.category.has(Category.name.ilike(f'%{query}%'))
        )
    ).filter(Product.is_active == True).limit(10).all()
    
    # Format the results
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'category': product.category.name if product.category else 'Uncategorized',
            'description': product.description
        })
    
    return jsonify(results)

@app.route('/search-suggestions')
def search_suggestions():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])

    # Search products
    products = Product.query.filter(Product.name.ilike(f'%{query}%')).filter(Product.is_active == True).limit(5).all()
    product_suggestions = [{'type': 'product', 'id': p.id, 'name': p.name} for p in products]

    # Search approved shops
    shops = Seller.query.filter(
        Seller.shop_name.ilike(f'%{query}%'),
        Seller.status == 'approved'
    ).limit(5).all()
    shop_suggestions = [{'type': 'shop', 'id': s.id, 'name': s.shop_name} for s in shops]

    # Combine and sort suggestions
    all_suggestions = product_suggestions + shop_suggestions
    all_suggestions.sort(key=lambda x: x['name'].lower().find(query.lower()))

    return jsonify(all_suggestions)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('index'))

    # Search products
    products = Product.query.filter(
        Product.name.ilike(f'%{query}%')
    ).filter(Product.is_active == True).all()

    # Search approved shops
    shops = Seller.query.filter(
        Seller.shop_name.ilike(f'%{query}%'),
        Seller.status == 'approved'
    ).all()

    return render_template('search_results.html', 
                         query=query, 
                         products=products, 
                         shops=shops)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        flash('This product is not available.', 'error')
        return redirect(url_for('index'))
    return render_template('product_detail.html', product=product)

@app.route('/become-seller', methods=['GET', 'POST'])
@login_required
def become_seller():
    if current_user.is_seller():
        flash('You are already a seller!', 'warning')
        return redirect(url_for('seller_dashboard'))

    if request.method == 'POST':
        shop_name = request.form.get('shop_name')
        description = request.form.get('description')
        instagram_link = request.form.get('instagram_link')

        if not shop_name or not description:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('become_seller'))

        # Check if shop name is unique
        existing_shop = Seller.query.filter_by(shop_name=shop_name).first()
        if existing_shop:
            flash('Shop name already exists. Please choose another name.', 'danger')
            return redirect(url_for('become_seller'))

        # Create new seller
        seller = Seller(
            shop_name=shop_name,
            user_id=current_user.id,
            description=description,
            status='pending',
            instagram_link=instagram_link
        )
        db.session.add(seller)
        db.session.commit()

        flash('Your seller account has been created and is pending approval!', 'success')
        return redirect(url_for('seller_dashboard'))

    return render_template('become_seller.html')

@app.route('/seller/dashboard')
@login_required
def seller_dashboard():
    if not current_user.is_seller():
        flash('You need to create a seller account first!', 'warning')
        return redirect(url_for('become_seller'))
    
    products = Product.query.filter_by(seller_id=current_user.seller_account.id).filter(Product.is_active == True).all()
    return render_template('seller_dashboard.html', products=products)

@app.route('/seller/products/add', methods=['GET', 'POST'])
@login_required
def seller_add_product():
    if not current_user.has_approved_seller_account():
        flash('Your seller account must be approved to add products!', 'warning')
        return redirect(url_for('seller_dashboard'))
    
    categories = Category.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        category_id = request.form.get('category_id')
        image_url = request.form.get('image_url')
        
        product = Product(
            name=name,
            description=description,
            price=price,
            stock=stock,
            category_id=category_id,
            image_url=image_url,
            seller_id=current_user.seller_account.id
        )
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('seller_dashboard'))
    
    return render_template('seller_add_product.html', categories=categories)

@app.route('/seller/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def seller_edit_product(id):
    if not current_user.has_approved_seller_account():
        flash('Your seller account must be approved to edit products!', 'warning')
        return redirect(url_for('seller_dashboard'))
    
    product = Product.query.get_or_404(id)
    if product.seller_id != current_user.seller_account.id:
        flash('You can only edit your own products!', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    categories = Category.query.all()
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.stock = int(request.form.get('stock'))
        product.category_id = request.form.get('category_id')
        product.image_url = request.form.get('image_url')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('seller_dashboard'))
    
    return render_template('seller_edit_product.html', product=product, categories=categories)

@app.route('/seller/products/<int:id>/delete', methods=['POST'])
@login_required
def seller_delete_product(id):
    if not current_user.has_approved_seller_account():
        flash('Your seller account must be approved to delete products!', 'warning')
        return redirect(url_for('seller_dashboard'))
    
    product = Product.query.get_or_404(id)
    if product.seller_id != current_user.seller_account.id:
        flash('You can only delete your own products!', 'danger')
        return redirect(url_for('seller_dashboard'))
    
    product.is_active = False
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('seller_dashboard'))

@app.route('/admin/sellers')
@login_required
def admin_sellers():
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    sellers = Seller.query.all()
    return render_template('admin_sellers.html', sellers=sellers)

@app.route('/admin/sellers/<int:id>/approve', methods=['POST'])
@login_required
def admin_approve_seller(id):
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    seller = Seller.query.get_or_404(id)
    seller.status = 'approved'
    db.session.commit()
    flash('Seller approved successfully!', 'success')
    return redirect(url_for('admin_sellers'))

@app.route('/admin/sellers/<int:id>/reject', methods=['POST'])
@login_required
def admin_reject_seller(id):
    if not current_user.is_admin:
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    seller = Seller.query.get_or_404(id)
    seller.status = 'rejected'
    db.session.commit()
    flash('Seller rejected!', 'success')
    return redirect(url_for('admin_sellers'))

@app.route('/shops')
def shops():
    sellers = Seller.query.filter_by(status='approved').all()
    return render_template('shops.html', sellers=sellers)

@app.route('/shop/<int:seller_id>')
def shop_details(seller_id):
    seller = Seller.query.get_or_404(seller_id)
    if seller.status != 'approved':
        flash('This shop is not available.', 'error')
        return redirect(url_for('shops'))
    products = Product.query.filter_by(seller_id=seller_id).filter(Product.is_active == True).all()
    return render_template('shop_details.html', seller=seller, products=products)

@app.route('/profile')
@login_required
def profile():
    # Get user's orders
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
    
    # Get user's shipping addresses
    addresses = ShippingAddress.query.filter_by(user_id=current_user.id).all()
    
    # If user is a seller, get their shop info
    seller_info = None
    if current_user.is_seller():
        seller_info = current_user.seller_account
    
    return render_template('profile.html', 
                         user=current_user, 
                         orders=orders, 
                         addresses=addresses,
                         seller_info=seller_info)

@app.route('/admin/chat')
@login_required
def admin_chat():
    if not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    return render_template('admin_chat.html')

def add_sample_data():
    # Add categories
    categories = [
        Category(name='Electronics'),
        Category(name='Books'),
        Category(name='Clothing'),
        Category(name='Home & Garden'),
        Category(name='Sports')
    ]
    for category in categories:
        db.session.add(category)
    db.session.commit()

    # Create admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

    # Create a sample seller
    seller = Seller(
        shop_name='Sample Shop',
        user_id=admin.id,
        description='This is a sample shop with various products',
        status='approved'
    )
    db.session.add(seller)
    db.session.commit()

    # Add sample products
    products = [
        {
            'name': 'Laptop',
            'description': 'High-performance laptop with latest specifications',
            'price': 999.99,
            'stock': 10,
            'category_id': 1,
            'image_url': 'laptop.jpg'
        },
        {
            'name': 'Smartphone',
            'description': 'Latest smartphone with advanced features',
            'price': 699.99,
            'stock': 15,
            'category_id': 1,
            'image_url': 'smartphone.jpg'
        },
        {
            'name': 'Python Programming Book',
            'description': 'Comprehensive guide to Python programming',
            'price': 49.99,
            'stock': 20,
            'category_id': 2,
            'image_url': 'book.jpg'
        },
        {
            'name': 'T-Shirt',
            'description': 'Comfortable cotton t-shirt',
            'price': 19.99,
            'stock': 50,
            'category_id': 3,
            'image_url': 'tshirt.jpg'
        },
        {
            'name': 'Garden Tools Set',
            'description': 'Complete set of essential garden tools',
            'price': 79.99,
            'stock': 8,
            'category_id': 4,
            'image_url': 'garden-tools.jpg'
        }
    ]

    for product_data in products:
        product = Product(
            name=product_data['name'],
            description=product_data['description'],
            price=product_data['price'],
            stock=product_data['stock'],
            category_id=product_data['category_id'],
            image_url=product_data['image_url'],
            seller_id=seller.id
        )
        db.session.add(product)
    
    db.session.commit()
    print("Sample data added successfully!")

if __name__ == '__main__':
    with app.app_context():
        try:
            # Only create tables if they don't exist
            db.create_all()
        except Exception as e:
            print(f"Error initializing database: {e}")
    
    app.run(debug=True)
