import os
import requests
import redis
import time

_token = None
_token_expires = 0
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


def get_token():
    global _token
    global _token_expires
    time_now = int(time.time())
    if _token_expires < time_now:
        client_token = os.getenv('CLIENT_TOKEN')
        client_id = os.getenv('CLIENT_ID')
        data = {
            'client_id': client_id,
            'client_secret': client_token,
            'grant_type': 'client_credentials'
        }
        response = requests.post('https://api.moltin.com/oauth/access_token', data=data)
        response.raise_for_status()
        _token_expires = int(response.json()['expires_in']) + time_now
        _token = response.json()['access_token']
    return _token


def get_products():
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get('https://api.moltin.com/v2/products', headers=headers)
    response.raise_for_status()
    return response.json()


def get_product_description(product_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/products/{product_id}', headers=headers)
    response.raise_for_status()
    description = response.json()['data']['description']
    return description


def get_image_url(product_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response_product = requests.get(f'https://api.moltin.com/v2/products/{product_id}', headers=headers)
    response_product.raise_for_status()
    file_id = response_product.json()['data']['relationships']['main_image']['data']['id']
    response_file_id = requests.get(f'https://api.moltin.com/v2/files/{file_id}', headers=headers)
    response_file_id.raise_for_status()
    image_url = response_file_id.json()['data']['link']['href']
    return image_url


def add_product_to_cart(reference, product_id, quantity):
    token = get_token()
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    }
    data = {'data': {
        'id': product_id,
        'type': 'cart_item',
        'quantity': int(quantity)
    }}
    response = requests.post(f'https://api.moltin.com/v2/carts/{reference}/items', headers=headers, json=data)
    response.raise_for_status()
    return response.url


def delete_product_from_cart(reference, product_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.delete(f'https://api.moltin.com/v2/carts/{reference}/items/{product_id}', headers=headers)
    response.raise_for_status()
    return response.json()


def get_cart(reference):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/carts/{reference}/items', headers=headers)
    response.raise_for_status()
    return response.json()['data']


def create_customer(email, name):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    headers['Content-Type'] = 'application/json'
    data = {'data': {
        'type': 'customer',
        'name': name,
        'email': email,
    }}
    response = requests.post('https://api.moltin.com/v2/customers', headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def get_cart_total_sum(chat_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/carts/{chat_id}', headers=headers)
    response.raise_for_status()
    return response.json()['data']['meta']['display_price']['with_tax']


# pizza_delivery

def create_product(pizza):
    token = get_token()
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    description = f'{pizza["description"]}\n Цена: {pizza["price"]}руб.'
    data = {"data": {
        "type": "product",
        "name": pizza['name'],
        "slug": str(pizza['id']),
        "sku": pizza['name'],
        "description": description,
        "manage_stock": False,
        "price": [
            {
                "amount": pizza['price'] * 100,
                "currency": "RUB",
                "includes_tax": True
            }
        ],
        "status": "live",
        "commodity_type": "physical"
    }
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['data']['id']


def download_images(menu):
    os.makedirs('pizza_images', exist_ok=True)
    for number, pizza in enumerate(menu):
        image_path = f'pizza_images/image_{number}.jpg'
        image = requests.get(pizza['product_image']['url'])
        with open(image_path, 'wb') as image_file:
            image_file.write(image.content)


def create_file(number):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    image_path = f'pizza_images/image_{number}.jpg'
    with open(image_path, 'rb') as image:
        files = {
            'file': image,
            'public': True,
        }
        response = requests.post('https://api.moltin.com/v2/files', headers=headers, files=files)
        response.raise_for_status()
    return response.json()['data']['id']


def get_connect_product_with_image(product_id, image_id):
    token = get_token()
    url = f'https://api.moltin.com/v2/products/{product_id}/relationships/main-image'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {'data': {
        'type': 'main_image',
        'id': str(image_id)
    }}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def fill_out_product_cards(menu):
    for number, product in enumerate(menu):
        product_id = create_product(product)
        image_id = create_file(number)
        get_connect_product_with_image(product_id, image_id)
        print('ok')


def create_new_flow(name, slug):
    token = get_token()
    url = 'https://api.moltin.com/v2/flows'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {'data': {
        "type": "flow",
        "name": name,
        "slug": slug,
        "description": "Pizzeria Addresses",
        "enabled": True,
    }}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['data']['id']


def add_flow_fields(field_name, field_type, flow_id):
    token = get_token()
    url = 'https://api.moltin.com/v2/fields'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {"data": {
        "type": "field",
        "name": field_name,
        "slug": field_name,
        "field_type": field_type,
        "validation_rules": [],
        "description": f'Field name: {field_name}, type of field is: {field_type}',
        "required": True,
        "unique": False,
        "default": None,
        "enabled": True,
        "order": None,
        "omit_null": False,
        "relationships": {
            "flow": {
                "data": {
                    "type": "flow",
                    "id": flow_id,
                }
            }
        }
    }
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response


def create_entry(slug, address):
    token = get_token()
    url = f'https://api.moltin.com/v2/flows/{slug}/entries'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {'data': {
        'type': 'entry',
        'alias': address['alias'],
        'latitude': float(address['coordinates']['lat']),
        'longitude': float(address['coordinates']['lon']),
        'address': address['address']['full'],

    }}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response


def get_image_file(file_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/files/{file_id}', headers=headers)
    return response.json()


def create_field_telegram_id(slug, telegram_id):
    token = get_token()
    url = f'https://api.moltin.com/v2/flows/address_details/entries'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {'data': {
        'type': 'entry',
        'telegram_id': telegram_id,
    }}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def put_telegram_id(telegram_id):
    token = get_token()
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    entries = get_all_entries()
    for entry in entries:
        entry_id = entry['id']
        data = {'data': {
            'type': 'entry',
            'telegram_id': telegram_id,
            'id': entry_id,

        }}
        response = requests.put(
            f'https://api.moltin.com/v2/flows/address_details/entries/{entry_id}',
            headers=headers,
            json=data
        )
        response.raise_for_status()


def get_all_entries():
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get('https://api.moltin.com/v2/flows/address_details/entries', headers=headers)
    response.raise_for_status()
    return response.json()['data']


def create_address_customer(lon, lat, chat_id):
    token = get_token()
    url = f'https://api.moltin.com/v2/flows/address_customer/entries'
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    }
    data = {'data': {
        'type': 'entry',
        'latitude': lat,
        'longitude': lon,
        'chat_id': chat_id,
    }}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response


def get_restaurant_chat_id(restaurant_address):
    entries = get_all_entries()
    for entry in entries:
        if entry['address'] == restaurant_address:
            return entry['telegram_id']
            break


#fb-delivery
def fetch_categorie_products(categorie_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/categories/{categorie_id}', headers=headers)
    response.raise_for_status()
    return response.json()['data']['relationships']['products']['data']


def get_product(product_id):
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get(f'https://api.moltin.com/v2/products/{product_id}', headers=headers)
    response.raise_for_status()
    return response.json()['data']


def fetch_description_products(products):
    fb_button_element = [{
        "title": "Меню",
        "image_url": 'https://image.freepik.com/free-vector/pizza-logo-vector_25327-119.jpg',
        "subtitle": "Здесь вы можете выбрать один из вариантов:",
        "buttons": [
            {
                "type": "postback",
                "title": "Корзина",
                "payload": "cart"
            },
            {
                "type": "postback",
                "title": "Акции",
                "payload": "SALE"
            },
            {
                "type": "postback",
                "title": "Сделать заказ",
                "payload": "MAKE AN ORDER"
            }

        ]
    }]
    for product in products:
        fb_button_element.append(
                        {
                            "title": product['name'],
                            "image_url": get_image_url(product['id']),
                            "subtitle": product['description'],
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Добавить в корзину",
                                    "payload": f"add_to_cart {product['id']}"
                                }
                            ]
                        }

                    )

    fb_button_element.append({
        "title": "Не нашли нужную пиццу?",
        "image_url": 'https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg',
        "subtitle": "Остальные пиццы можно посмотреть в одной из категорий",
        "buttons": [
            {
                "type": "postback",
                "title": "Особые",
                "payload": 'special',
            },
            {
                "type": "postback",
                "title": "Острые",
                "payload": 'sharp',
            },
            {
                "type": "postback",
                "title": "Сытные",
                "payload": 'Nourishing',
            }

        ]
    })

    return fb_button_element


def get_fb_cart(sender_id):
    products_in_cart = get_cart(sender_id)
    total_amount = get_cart_total_sum(sender_id)['amount']//100
    fb_button_elements = [{
        "title": "Корзина",
        "image_url": 'https://postium.ru/wp-content/uploads/2018/08/idealnaya-korzina-internet-magazina-1068x713.jpg',
        "subtitle": f"Ваш заказ на сумму: {total_amount} рублей",
        "buttons": [
            {
                "type": "postback",
                "title": "Самовывоз",
                "payload": "take_away"
            },
            {
                "type": "postback",
                "title": "Доставка",
                "payload": "delivery"
            },
            {
                "type": "postback",
                "title": "Меню",
                "payload": "menu"
            }

        ]
    }]
    for product in products_in_cart:
        fb_button_elements.append(
                        {
                            "title": product['name'],
                            "image_url": product['image']['href'],
                            "subtitle": product['description'],
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Добавить ещё одну",
                                    "payload": f"add_to_cart {product['id']}"
                                },
                                {
                                    "type": "postback",
                                    "title": "Убрать из корзины",
                                    "payload": f"del_from_cart {product['id']}"
                                }
                            ]
                        }

                    )

    return fb_button_elements


def fetch_categories():
    token = get_token()
    headers = {'Authorization': 'Bearer ' + token}
    response = requests.get('https://api.moltin.com/v2/categories', headers=headers)
    response.raise_for_status()
    categories = {categorie['slug']:categorie['id'] for categorie in response.json()['data']}
    return categories


