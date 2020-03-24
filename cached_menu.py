import redis
import moltin
import time, json, os


_database = None


def get_database_connection():
    global _database
    if _database is None:
        redis_password = os.getenv('REDIS_PASSWORD')
        redis_port = os.getenv('REDIS_PORT')
        redis_host = os.getenv('REDIS_HOST')
        _database = redis.Redis(host=redis_host, port=redis_port,
                                password=redis_password)
    return _database


def create_menu():
    categories = moltin.fetch_categories()
    products_by_categories = {}
    for category_slug, category_id in categories.items():
        products_ids = moltin.fetch_categorie_products(category_id)
        products = [moltin.get_product(product['id']) for product in products_ids]
        products_by_categories[category_slug] = products
    cached_time = int(time.time())
    cached_menu = json.dumps({'created_at': cached_time, 'products': products_by_categories})
    return cached_menu


def get_menu():
    db = get_database_connection()
    cached_menu = json.loads(db.get("menu"))
    time_diff = int(time.time()) - cached_menu['created_at']
    if time_diff > 3600:
        menu = create_menu()
        db.set("menu", menu)
    else:
        menu = cached_menu
    return menu
