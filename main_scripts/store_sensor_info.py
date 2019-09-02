#!/usr/bin/env python3

import argparse
import json
import itertools
import time
from datetime import datetime
from typing import List

import requests

from use_postgres import UseDatabase

def grab_grow_sensors() -> List:
    """Grabs all GROW sensor IDs, last upload date, days active"""
    url = 'https://grow.thingful.net/api/entity/timeSeriesInformations/get'
    header = {'Authorization': ''}
    response = requests.post(url, headers=header)
    json_object = response.json()
    current_sensors = []
    sensor_info_list = []
    for i in json_object['TimeSeriesInformations']:
        sensor_id = json_object['TimeSeriesInformations'][i]['LocationIdentifier'][-8:]
        if sensor_id not in current_sensors:
            current_sensors.append(sensor_id)
            sensor_list = []
            start_date = json_object['TimeSeriesInformations'][i]['StartDate']
            end_date = json_object['TimeSeriesInformations'][i]['EndDate']
            start_dt = datetime.strptime(start_date, '%Y%m%d%H%M%S')
            end_dt = datetime.strptime(end_date, '%Y%m%d%H%M%S')
            delta_dt = end_dt - start_dt
            days_active = delta_dt.days # difference in days from start to end dates
            edit_start_date = start_date[:8] + 'T' + start_date[8:] # add T for later insert to Aurora
            edit_end_date = end_date[:8] + 'T' + end_date[8:] 
            sensor_list.append(sensor_id)
            sensor_list.append(days_active)
            sensor_list.append(edit_start_date)
            sensor_list.append(edit_end_date)
            sensor_info_list.append(sensor_list)
    return sensor_info_list

def filter_for_new_sensor_updates(aurora_creds: dict, new_sensor_list: List) -> List:
    """Compare sensor info to Aurora table to see if the individual sensor 
    info is already in the table. If not present, keep the sensor info for further 
    processing and eventual insert into Aurora table"""
    with UseDatabase(aurora_creds) as cursor:
        sql_check = """SELECT EXISTS (SELECT 1 FROM pg_tables
                                        WHERE tablename = 'all_sensor_info');"""
        cursor.execute(sql_check)
        response = cursor.fetchone()
        if response[0] == True:
            sql_collect = """SELECT row_to_json(all_sensor_info)
                                FROM all_sensor_info;"""
            cursor.execute(sql_collect)
            all_stored_sensors = cursor.fetchall()
        else:
            # If 'all_sensor_info' table does not exist
            all_stored_sensors = []
    stored_sensor_ids = []
    for i in all_stored_sensors:
        stored_sensor_ids.append(i[0]['sensor_id'])
    new_sensor_info = []
    for i in new_sensor_list:
        # If sensor is not already stored
        if i[0] not in stored_sensor_ids:
            new_sensor_info.append(i)
        else:
            for stored_sensor in all_stored_sensors:
                # If sensor has new data not yet stored
                if stored_sensor[0]['sensor_id'] == i[0] and \
                    stored_sensor[0]['end_date'].replace('-','').replace(':','') != i[3]:
                    new_sensor_info.append(i)
    return new_sensor_info, stored_sensor_ids

def lookup_location_coords(sensor_list: List, gcloud_api_key: str) -> List:
    """Find and append location coords, address, owner id to GROW sensor list"""
    url = 'https://grow.thingful.net/api/entity/locations/get'
    header = {'Authorization': ''}
    payload = {'DataSourceCodes': ['Thingful.Connectors.GROWSensors']}
    response = requests.post(url, headers=header, json=payload)
    json_object = response.json()
    for sensor in sensor_list:
        for i in json_object['Locations']:
            if json_object['Locations'][i]['Code'] == sensor[0]:
                lat = json_object['Locations'][i]['Y']
                lon = json_object['Locations'][i]['X']
                owner_id = json_object['Locations'][i]['UserUid']
                full_address = get_address(str(lat) + ',' + str(lon), gcloud_api_key)
                sensor.append(lat)
                sensor.append(lon)
                sensor.append(full_address)
                sensor.append(owner_id)
                time.sleep(0.025)
    return sensor_list

def get_address(latlng: str, api_key: str) -> List:
    """Query Google Geocoding API to reverse geocode latlng to full address"""
    url = 'https://maps.googleapis.com/maps/api/geocode/json' 
    payload = {'latlng': latlng, 'key': api_key} 
    response = requests.get(url, params=payload)
    json_object = response.json()
    full_address = []
    try:
        for i in json_object['results'][0]['address_components']:
            full_address.append(i['long_name'])
    except:
        full_address.append('')
    return ' '.join(full_address)

def insert_to_aurora(aurora_creds: dict, sensor_list: List, stored_sensor_ids: List) -> None:
    """Insert sensor list details to AWS Aurora DB"""
    with UseDatabase(aurora_creds) as cursor:
        sql_create = """CREATE TABLE IF NOT EXISTS all_sensor_info(
                        sensor_id varchar(8),
                        days_active integer, 
                        start_date timestamp, 
                        end_date timestamp, 
                        latitude numeric, 
                        longitude numeric, 
                        address varchar(140), 
                        owner_id varchar(36));"""
        cursor.execute(sql_create)
        for i in sensor_list:
            if i[0] in stored_sensor_ids:
                cursor.execute("""UPDATE all_sensor_info
                            SET days_active = %s,
                            start_date = %s,
                            end_date = %s
                            WHERE sensor_id = %s""",
                            (i[1], i[2], i[3], i[0]))
            else:
                cursor.execute("""INSERT INTO all_sensor_info
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s)""",
                            (i[0], i[1], i[2], i[3], i[4], i[5], i[6], i[7]))

def main(aurora_host: str, db_name: str, aurora_username: str, 
        aurora_password: str, gcloud_api_key: str):
    """Creates/Updates Aurora 'all_sensor_info' table to 
    include all GROW sensor information, including full
    address.
    """
    aurora_creds = {
        'host': aurora_host,
        'port': 5432,
        'dbname': db_name,
        'user': aurora_username,
        'password': aurora_password
    }
    sensor_info = grab_grow_sensors()
    new_sensor_info, stored_sensor_ids = filter_for_new_sensor_updates(aurora_creds, sensor_info)
    sensor_list = lookup_location_coords(new_sensor_info, args.gcloud_api_key)
    insert_to_aurora(aurora_creds, sensor_list, stored_sensor_ids)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('aurora_host')
    parser.add_argument('db_name')
    parser.add_argument('aurora_username')
    parser.add_argument('aurora_password')
    parser.add_argument('gcloud_api_key')
    args = parser.parse_args()
    main(args.aurora_host, args.db_name, args.aurora_username, 
            args.aurora_password, args.gcloud_api_key)