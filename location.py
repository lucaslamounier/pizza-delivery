import os
import requests
import moltin
from geopy import distance


def fetch_coordinates(address):
    try:
        address.longitude
        lon, lat = address.longitude, address.latitude
    except AttributeError:
        apikey = os.getenv('YANDEX_TOKEN')
        base_url = "https://geocode-maps.yandex.ru/1.x"
        params = {"geocode": address, "apikey": apikey, "format": "json"}
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        places_found = response.json()['response']['GeoObjectCollection']['featureMember']
        most_relevant = places_found[0]
        lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


def get_delivery_raidus(lon,lat):
    distance_rating = []
    if float(lon) > 90:
        lon = 180 - float(lon)
    customer_geo = (lon,lat)

    restaurants = moltin.get_all_entries()
    for restaurant in restaurants:
        restaurant_geo = (restaurant['longitude'], restaurant['latitude'])
        distance_km = distance.distance(customer_geo, restaurant_geo).km
        distance_rating.append({'restaurant': restaurant['address'],'distance':distance_km})

    distance_min = min(distance_rating, key=lambda km: km['distance'])
    return distance_min


def get_price_delivery(distance):
    distance = round(distance['distance'], 1)
    if distance <= 0.5:
        message_text = 'Вы можете забрать пиццу самостоятельно, либо с бесплатной доставкой'
    elif 0.5 > distance <= 5:
        message_text = 'Вы можете забрать пиццу самостоятельно, либо заплатить 100руб за доставку'
    elif 5 > distance <= 20:
        message_text = 'Вы можете забрать пиццу самостоятельно, либо заплатить 300руб за доставку'
    elif 20 > distance < 40:
        message_text = 'К сожалению, мы не можем доставить пицу так далеко, возможен только самовывоз'
    else:
        message_text = f'Простите, но вы слишком далеко, ближайшая пиццерия {distance}км от вас'
    return message_text
