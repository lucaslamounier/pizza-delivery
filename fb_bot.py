import os
import json
import moltin
import requests
import cached_menu


def create_keyboard(recipient_id, fb_keyboard_elements):
    request_content = json.dumps({
        "recipient": {
            "id": recipient_id,
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": fb_keyboard_elements
                }
            }
        }
    }
    )
    return request_content


def send_cart(recipient_id):
    params = {"access_token": os.getenv("PAGE_ACCESS_TOKEN")}
    headers = {'Content-Type': 'application/json'}
    fb_keyboard_elements = moltin.get_fb_cart(recipient_id)
    request_content = create_keyboard(recipient_id, fb_keyboard_elements)
    response = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers,
                             data=request_content)
    response.raise_for_status()


def send_message(recipient_id, message_text):
    params = {"access_token": os.environ["PAGE_ACCESS_TOKEN"]}
    headers = {"Content-Type": "application/json"}
    request_content = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    response = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers,
                             data=request_content)
    response.raise_for_status()


def send_keyboard(recipient_id, products):
    params = {"access_token": os.getenv("PAGE_ACCESS_TOKEN")}
    headers = {'Content-Type': 'application/json'}
    fb_keyboard_elements = moltin.fetch_description_products(products)
    request_content = create_keyboard(recipient_id, fb_keyboard_elements)
    response = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers,
                             data=request_content)
    response.raise_for_status()


def handle_start(recipient_id, message_text):
    menu = cached_menu.get_menu()
    if message_text in ['sharp', 'special', 'Nourishing']:
        products = menu['products'][message_text]
        send_keyboard(recipient_id, products)
    elif message_text.split(' ')[0] == 'add_to_cart':
        postback, product_id = message_text.split(' ')
        product_name = moltin.get_product(product_id)['name']
        moltin.add_product_to_cart(recipient_id, product_id, 1)
        send_message(recipient_id, product_name)
    elif message_text == 'cart':
        send_cart(recipient_id)
        return "MENU"
    else:
        products = menu['products']['front_page']
        send_keyboard(recipient_id, products)
    return "START"


def handle_menu(recipient_id, message_text):
    postback, product_id = message_text.split(' ')
    if postback == 'add_to_cart':
        moltin.add_product_to_cart(recipient_id, product_id, 1)
        response_message = 'Пицца добавлена корзину'
    elif postback == 'del_from_cart':
        moltin.delete_product_from_cart(recipient_id, product_id)
        response_message = 'Пицца удалена из корзины'
    send_message(recipient_id, response_message)
    send_cart(recipient_id)
    return "MENU"


def handle_users_reply(recipient_id, message_text):
    db = cached_menu.get_database_connection()
    db_sender_id = f'facebook_{recipient_id}'
    start = ['/start', 'menu']
    states_functions = {
        'START': handle_start,
        'MENU': handle_menu,

    }
    recorded_state = db.get(db_sender_id)
    if not recorded_state or recorded_state.decode("utf-8") not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state.decode("utf-8")
    if message_text in start:
        user_state = "START"

    state_handler = states_functions[user_state]
    next_state = state_handler(recipient_id, message_text)
    db.set(db_sender_id, next_state)
