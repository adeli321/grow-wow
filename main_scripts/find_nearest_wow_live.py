#!/usr/bin/env python3

import argparse
import json
from typing import List
from math import cos, asin, sqrt

import requests

from use_postgres import UseDatabase

def grab_grow_ids() -> List:
    """Grabs distinct sensor IDs and coordinates from grow location api"""
    url = 'https://grow.thingful.net/api/entity/locations/get'
    header = {'Authorization': ''}
    payload = {'DataSourceCodes': ['Thingful.Connectors.GROWSensors']}
    response = requests.post(url, headers=header, json=payload)
    json_object = response.json()
    grow_current_sensors = []
    for i in json_object['Locations']:
        sensor_id = json_object['Locations'][i]['Code']
        if sensor_id not in grow_current_sensors:
            lat = json_object['Locations'][i]['Y']
            lon = json_object['Locations'][i]['X']
            grow_current_sensors.append([sensor_id, lat, lon])
    return grow_current_sensors

def grow_sensors_to_insert(aurora_creds: dict, grow_current_sensors: List) -> List:
    """Retrieve GROW sensor IDs of all GROW sensors not currently 
    in 'grow_to_wow_mapping' Aurora table."""
    with UseDatabase(aurora_creds) as cursor:
        sql_table_check = """SELECT EXISTS (SELECT 1 FROM pg_tables
                                            WHERE tablename = 'grow_to_wow_mapping');"""
        cursor.execute(sql_table_check)
        response = cursor.fetchone()
        if response[0] == True:
            sql_collect = """SELECT sensor_id
                                FROM grow_to_wow_mapping;"""
            cursor.execute(sql_collect)
            all_stored_sensors = cursor.fetchall()
        else:
            all_stored_sensors = []
    sensors_to_insert = []
    for i in grow_current_sensors:
        if i[0] not in [x[0] for x in all_stored_sensors]:
            sensors_to_insert.append(i)
    return sensors_to_insert

def grab_wow_ids_and_coords() -> List:
    """Grabs WOW site IDs and location coordinates from static file"""
    with open('wow_observations_europe.json', 'r') as reader:
        json_object = json.load(reader)
        wow_site_list = []
        for i in range(len(json_object['Object'])):
            try:
                if json_object['Object'][i]['RainfallAmount_Millimetre'] is not None and \
                    json_object['Object'][i]['DryBulbTemperature_Celsius'] is not None:
                    site_id = json_object['Object'][i]['SiteId']
                    lat = json_object['Object'][i]['Latitude']
                    lon = json_object['Object'][i]['Longitude']
                    wow_site_list.append([site_id, lat, lon])
            except KeyError:
                pass
    return wow_site_list

def distance(lat1: int, lon1: int, lat2: int, lon2: int) -> int:
    """Use Haversine formula to compute distance between lat/lon coordinates"""
    p = 0.017453292519943295
    a = 0.5 - cos((lat2-lat1)*p)/2 + cos(lat1*p)*cos(lat2*p) * (1-cos((lon2-lon1)*p)) / 2
    return 12742 * asin(sqrt(a))

def closest(data: List, v: List) -> List:
    """Finds the closest lat/lon coords near v"""
    return min(data, key=lambda p: distance(v[1],v[2],p[1],p[2]))

def close_distance(data: List) -> List:
    """Returns the distance between GROW and WOW"""
    for i in data:
        dist = distance(i[1], i[2], i[3][1], i[3][2])
        i.append(dist)
    return data 

def find_nearest_wow(sensors_to_insert: List, wow_site_list: List) -> List:
    """For each grow sensor, find the nearest WOW observation site"""
    for i in range(len(sensors_to_insert)):
        closest_wow = closest(wow_site_list, sensors_to_insert[i])
        sensors_to_insert[i].append(closest_wow)
    return sensors_to_insert

def insert_to_db(aurora_creds: dict, mappings_and_distance: List) -> None:
    """Insert the GROW/WOW sensor/site mappings to AWS Aurora DB"""
    with UseDatabase(aurora_creds) as cursor:
        sql_create = """CREATE TABLE IF NOT EXISTS grow_to_wow_mapping(
                        sensor_id varchar(8),
                        grow_lat numeric, 
                        grow_lon numeric,
                        site_id varchar(36),
                        wow_lat numeric, 
                        wow_lon numeric,
                        distance numeric);"""
        cursor.execute(sql_create)
        for i in mappings_and_distance:
            cursor.execute("""INSERT INTO grow_to_wow_mapping
                            VALUES(%s, %s, %s, %s, %s, %s, %s)""",
                            (i[0], i[1], i[2], i[3][0], i[3][1], i[3][2], i[4]))

def main(aurora_host: str, db_name: str, aurora_username: str, aurora_password: str):
    """Updates Aurora 'grow_to_wow_mapping' table by adding new GROW sensors
    mapped to their nearest WOW site. 
    """
    aurora_creds = {
        'host': aurora_host,
        'port': 5432,
        'dbname': db_name,
        'user': aurora_username,
        'password': aurora_password
    }
    all_grow_sensor_ids = grab_grow_ids()
    sensors_to_insert = grow_sensors_to_insert(aurora_creds, all_grow_sensor_ids)
    wow_site_list = grab_wow_ids_and_coords()
    sensor_site_mappings = find_nearest_wow(sensors_to_insert, wow_site_list)
    mappings_and_distance = close_distance(sensor_site_mappings)
    insert_to_db(aurora_creds, mappings_and_distance)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('aurora_host')
    parser.add_argument('db_name')
    parser.add_argument('aurora_username')
    parser.add_argument('aurora_password')
    args = parser.parse_args()
    main(args.aurora_host, args.db_name, args.aurora_username, args.aurora_password)
