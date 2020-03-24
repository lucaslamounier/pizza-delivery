import logging
import os
import moltin, location
import redis
from dotenv import load_dotenv
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, PreCheckoutQueryHandler
from telegram.ext import Filters, Updater
import json

_database = None
logger = logging.getLogger(__name__)


def get_database_connection():
    global _database
    if _database is None:
        redis_password = os.getenv('REDIS_PASSWORD')
        redis_port = os.getenv('REDIS_PORT')
        redis_host = os.getenv('REDIS_HOST')
        _database = redis.Redis(host=redis_host, port=redis_port,
                                password=redis_password)
    return _database


def get_keyboard(cart_descriptions):
    keyboard = []
    for product in cart_descriptions:
        keyboard.append([InlineKeyboardButton(f'Убрать {product["name"]}', callback_data='button ' + product['id'])])
    keyboard.append([InlineKeyboardButton('В меню', callback_data='back_to_menu')])
    keyboard.append([InlineKeyboardButton('Оплатить', callback_data='button pay')])
    return InlineKeyboardMarkup(keyboard)


def get_cart_details(cart_descriptions):
    cart_details = ''
    for product in cart_descriptions:
        product_price = product['meta']['display_price']['with_tax']['value']['formatted']
        cart_details += f'{product["name"]}\n{product["description"]}\n{product_price}\n\n'
    return cart_details


def get_keyboard_product(start, end):
    products = moltin.get_products()['data']
    amount_products = len(products)
    product_slice = products[start:end]
    if start == 0:
        buttons = {'right': '>'}
    elif amount_products <= end:
        buttons = {'left': '<'}
    else:
        buttons = {'left': '<', 'right': '>'}
    keyboard = [[InlineKeyboardButton(product['name'], callback_data='button ' + product['id'])] for product in
             product_slice]
    keyboard.append([InlineKeyboardButton(char, callback_data=site) for site, char in buttons.items()])
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='button cart')])
    return InlineKeyboardMarkup(keyboard)


def get_pagination_slice(chat_id, pagination_direction, step):
    db = get_database_connection()
    db_datas = json.loads(db.get(chat_id))
    privious_start, privious_end = int(db_datas['start']), int(db_datas['end'])
    if pagination_direction == 'left':
        next_start, next_end = privious_start - step, privious_end - step
    elif pagination_direction == 'right':
        next_start, next_end = privious_start + step, privious_end + step
    else:
        next_start, next_end = privious_start, privious_end
    db_datas['start'] = next_start
    db_datas['end'] = next_end
    db.set(chat_id, json.dumps(db_datas))
    return next_start, next_end


def start(update, context):
    query = update.callback_query
    db = get_database_connection()
    start, step = 0, 4,
    if update.message:
        chat_id = update.message.chat_id
        start_params = json.dumps({
            'state': 'HANDLE_MENU',
            'start': start,
            'end': step,
        })
        db.set(chat_id, start_params)
        reply_markup = get_keyboard_product(start, step)
        update.message.reply_text('Пожалуйста, выберите товар: ', reply_markup=reply_markup)
    else:
        chat_id = query.message.chat_id
        pagination_direction = query.data
        next_start, next_end = get_pagination_slice(chat_id, pagination_direction, step)
        reply_markup = get_keyboard_product(next_start, next_end)
        query.message.reply_text('Пожалуйста, выберите товар: ', reply_markup=reply_markup)
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
    return "HANDLE_MENU"


def handle_menu(update, context):
    query = update.callback_query
    reference = query.message.chat_id
    if query.data.split(' ')[1] == 'cart':
        final_amount = moltin.get_cart_total_sum(reference)
        cart_descriptions = moltin.get_cart(reference)
        reply_markup = get_keyboard(cart_descriptions)
        cart_details = get_cart_details(cart_descriptions)
        query.message.reply_text(f'{cart_details}\n\nСумма заказа: {final_amount["formatted"]}', reply_markup=reply_markup)
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        return "HANDLE_CART"

    else:
        product_id = query.data.split(' ')[1]
        description = moltin.get_product_description(product_id)
        image_url = moltin.get_image_url(product_id)
        keyboard = [[InlineKeyboardButton('1 шт.', callback_data='button ' + product_id + ' 1'),
                     InlineKeyboardButton('2 шт.', callback_data='button ' + product_id + ' 2'),
                     InlineKeyboardButton('5 шт.', callback_data='button ' + product_id + ' 5')],
                    [InlineKeyboardButton('Назад', callback_data='back')],
                    [InlineKeyboardButton('Корзина', callback_data='button cart')]
                    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_photo(
            chat_id=query.message.chat_id,
            caption=description,
            photo=image_url,
            reply_markup=reply_markup,
        )
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        return 'HANDLE_DESCRIPTION'


def handle_description(update, context):
    query = update.callback_query
    reference = query.message.chat_id
    if query.data.split(' ')[1] == 'cart':
        final_amount = moltin.get_cart_total_sum(reference)
        cart_descriptions = moltin.get_cart(reference)
        reply_markup = get_keyboard(cart_descriptions)
        cart_details = get_cart_details(cart_descriptions)
        query.message.reply_text(f'{cart_details}\n\nСумма заказа: {final_amount["formatted"]}$', reply_markup=reply_markup)
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        return "HANDLE_CART"
    else:
        button, product_id, quantity = query.data.split(' ')
        moltin.add_product_to_cart(reference, product_id, quantity)
        update.callback_query.answer('Добавленно в корзину')


def handle_cart(update, context):
    query = update.callback_query
    if query.data.split(' ')[1] == 'pay':
        query.message.reply_text("Пришлите пожалуйста свою геолокацию или напишите ваш район")
        return "HANDLE_WAITING"
    else:
        product_id = query.data.split(' ')[1]
        reference = query.message.chat_id
        moltin.delete_product_from_cart(reference, product_id)
        final_amount = moltin.get_cart_total_sum(reference)
        cart_descriptions = moltin.get_cart(reference)
        reply_markup = get_keyboard(cart_descriptions)
        cart_details = get_cart_details(cart_descriptions)
        query.message.reply_text(f'{cart_details}\n\nСумма заказа: {final_amount["formatted"]}$', reply_markup=reply_markup)
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        return "HANDLE_CART"


def handle_waiting(update, context):
    chat_id = update.message.chat_id
    if update.message.location:
        address = update.message.location
    else:
        address = update.message.text
    try:
        lon, lat = location.fetch_coordinates(address)
        distance = location.get_delivery_raidus(lon, lat)
        message_text = location.get_price_delivery(distance)
        moltin.create_address_customer(lon, lat, chat_id)
        keyboard = [[InlineKeyboardButton('Доставка', callback_data=f'button delivery {lon} {lat}'),
                     InlineKeyboardButton('Самовывоз', callback_data=f'button pickup {lon} {lat}')],
                    ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(message_text, reply_markup=reply_markup)
        return 'HANDLE_DELIVERY'
    except IndexError:
        update.message.reply_text('Вы не правильно ввели адрес, попробуйте ёще раз')
        return 'HANDLE_WAITING'


def handle_location(update, context):
    chat_id = update.message.chat.id
    coordinates = update.message.location
    lon, lat = coordinates.longitude, coordinates.latitude
    distance = location.get_delivery_raidus(lon, lat)
    message_text = location.get_price_delivery(distance)
    moltin.create_address_customer(lon, lat, chat_id)
    keyboard = [[InlineKeyboardButton('Доставка', callback_data=f'button delivery {lon} {lat}'),
                 InlineKeyboardButton('Самовывоз', callback_data=f'button pickup {lon} {lat}')],
                ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message_text, reply_markup=reply_markup)
    return 'HANDLE_DELIVERY'


def send_reminder(context: telegram.ext.CallbackContext):
    context.bot.send_message(
        chat_id=context.job.context,
        text=f'Приятного аппетита! *место для рекламы*\n\n' \
            f'*сообщение что делать если пицца не пришла*')


def handle_delivery(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    print(query.message.text)
    if query.data.split(' ')[1] == 'delivery':
        button, delivery, lon, lat = query.data.split(' ')
        customer_cart = moltin.get_cart(chat_id)
        restaurant_address = location.get_delivery_raidus(lon, lat)['restaurant']
        cart_description = get_cart_details(customer_cart)
        restaurant_chat_id = moltin.get_restaurant_chat_id(restaurant_address)
        context.bot.send_message(chat_id=restaurant_chat_id, text=cart_description)
        context.bot.send_location(chat_id=restaurant_chat_id, latitude=lat, longitude=lon)
        context.job_queue.run_once(send_reminder, 5, context=chat_id)
        return "HANDLE_PAYMENT"
    else:
        button, pickup, lon, lat = query.data.split(' ')
        restaurant_address = location.get_delivery_raidus(lon, lat)['restaurant']
        query.message.reply_text(f'Спасибо за покупку, ожидаем вас в течение часа, по адрессу:\n{restaurant_address}')


def handle_payment(update, context):
    chat_id = update.message.chat_id
    amount = moltin.get_cart_total_sum(chat_id)
    currency = 'RUB'
    title = "Payment Example"
    description = "Payment Example using python-telegram-bot"
    payload = "Custom-Payload"
    provider_token = os.getenv('TELEGRAM_PAYMENTS_TOKEN')
    start_parameter = "test-payment"
    prices = [LabeledPrice("Test", int(amount['amount']))]
    context.bot.sendInvoice(chat_id, title, description, payload,
                            provider_token, start_parameter, currency, prices)


def precheckout_callback(update, context):
    query = update.pre_checkout_query
    if query.invoice_payload != 'Custom-Payload':
        context.bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=False,
                                              error_message="Something went wrong...")
    else:
        context.bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)


def successful_payment_callback(update, context):
    update.message.reply_text("Thank you for your payment!")


def handle_users_reply(update, context):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply in ['/start', 'back', 'back_to_menu', 'right', 'left']:
        user_state = 'START'
    else:
        db_data = json.loads(db.get(chat_id))
        user_state = db_data['state']
    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'HANDLE_WAITING': handle_waiting,
        'HANDLE_DELIVERY': handle_delivery,
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(update, context)
    db_data['state'] = next_state
    db.set(chat_id, json.dumps(db_data))


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    load_dotenv()
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    telegram_token = os.getenv('TELEGRAM_ACCESS_TOKEN')
    updater = Updater(telegram_token, use_context=True)

    dispatcher = updater.dispatcher

    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply, pass_job_queue=True))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply, pass_job_queue=True))
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply))

    dispatcher.add_handler(MessageHandler(Filters.regex('^(Вы)$'), handle_payment))
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))
    dispatcher.add_error_handler(error)
    updater.start_polling()


if __name__ == '__main__':
    main()
