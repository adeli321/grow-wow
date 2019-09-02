#! /usr/bin/env python3

import argparse
import datetime
import json
from typing import List, Tuple

import requests
import pandas as pd
import psycopg2
from psycopg2 import sql 

from use_postgres import UseDatabase

def grab_grow_sensor_uptimes() -> List:
    """Fetch and return all GROW sensor IDs and their start and end datetimes"""
    url = 'https://grow.thingful.net/api/entity/timeSeriesInformations/get'
    header = {'Authorization': ''}
    response = requests.post(url, headers=header)
    json_object = response.json()
    current_sensors = []
    sensor_uptime_list = []
    for i in json_object['TimeSeriesInformations']:
        sensor_id = json_object['TimeSeriesInformations'][i]['LocationIdentifier'][-8:]
        if sensor_id not in current_sensors:
            current_sensors.append(sensor_id)
            sensor_details = []
            sensor_details.append(sensor_id)
            sensor_details.append(json_object['TimeSeriesInformations'][i]['StartDate'])
            sensor_details.append(json_object['TimeSeriesInformations'][i]['EndDate'])
            sensor_uptime_list.append(sensor_details)
    return sensor_uptime_list

def check_most_recent_grow_data(aurora_creds: dict, sensor_id: str, 
                                start_date: str, end_date: str) -> Tuple[str, List]:
    """Check to see if the most recent sensor reading is already stored in AWS Aurora.
    If it is not already stored, calculate the delta time interval between last 
    stored reading and last recorded reading, and calculate 10 day intervals 
    that add up to the delta interval. This is done because the GROW API
    only allows query ranges to be 10 days maximum.
    """
    with UseDatabase(aurora_creds) as cursor:
        table_name = f"grow_data_{sensor_id}"
        try:
            # Get the most recent sensor recording datetime
            cursor.execute(sql.SQL("SELECT MAX(datetime) FROM {}").format(sql.Identifier(table_name)))
            stored_end_date = cursor.fetchone()[0]
            if stored_end_date == None:
                stored_end_date = datetime.datetime.strptime(start_date, '%Y%m%d%H%M%S')
        except psycopg2.ProgrammingError: 
            # If table does not exist
            stored_end_date = datetime.datetime.strptime(start_date, '%Y%m%d%H%M%S')
    end_dt = datetime.datetime.strptime(end_date, '%Y%m%d%H%M%S')
    delta = end_dt - stored_end_date
    print('delta', delta, 'stored_end_date', stored_end_date, 'sensor', sensor_id)
    if delta == datetime.timedelta(0):
        # If the stored end date and most recent end date are the same, no updates need to be made
        sensor_start_end_intervals = []
    else:
        sensor_start_end_intervals = []
        start = stored_end_date
        while delta > datetime.timedelta(0):
            if delta < datetime.timedelta(days=9):
                interval = []
                end = end_dt 
                interval.append(start.strftime('%Y%m%d%H%M%S'))
                interval.append(end.strftime('%Y%m%d%H%M%S'))
                sensor_start_end_intervals.append(interval)
                break
            else:
                interval = []
                end = start + datetime.timedelta(days=9)
                interval.append(start.strftime('%Y%m%d%H%M%S'))
                interval.append(end.strftime('%Y%m%d%H%M%S'))
                sensor_start_end_intervals.append(interval)
                delta -= datetime.timedelta(days=9)
                start = end 
    return sensor_id, sensor_start_end_intervals

def grab_grow_data(sensor_id: str, sensor_start_end_intervals: List) -> Tuple[str, List, List, List]:
    """Query specific GROW sensor for each interval in sensor_start_end_intervals list.
    Store data in a separate list for each GROW variable.
    """
    header = {'Authorization': ''}
    url = 'https://grow.thingful.net/api/timeSeries/get'
    soil_moisture = []
    light = []
    air_temperature = []
    battery_level = []
    for datetime_interval in sensor_start_end_intervals:
        payload = {'Readers': [{'DataSourceCode': 'Thingful.Connectors.GROWSensors',
                                'Settings': 
                                    {'LocationCodes': [sensor_id], # 02krq5q5
                                    'VariableCodes': ['Thingful.Connectors.GROWSensors.light',
                                                    'Thingful.Connectors.GROWSensors.air_temperature',
                                                    'Thingful.Connectors.GROWSensors.calibrated_soil_moisture',
                                                    'Thingful.Connectors.GROWSensors.battery_level'],
                                    'StartDate': datetime_interval[0], # 20181028200000
                                    'EndDate': datetime_interval[1]
                                }}]}
        while True:
            # While loop to ensure script retries requests 'post' command after error
            response = requests.post(url, headers=header, json=payload)
            if 'json' in response.headers.get('Content-Type'):
                json_object = response.json()
            else:
                continue
            try:
                for i in json_object['Data']:
                    if i['VariableCode'].endswith('soil_moisture'):
                        for reading in i['Data']:
                            indiv_reading = []
                            datetime = reading['DateTime']
                            edit_datetime = datetime[:8] + 'T' + datetime[8:]
                            indiv_reading.append(edit_datetime)
                            indiv_reading.append(reading['Value'])
                            soil_moisture.append(indiv_reading)
                    elif i['VariableCode'].endswith('light'):
                        for reading in i['Data']:
                            indiv_reading = []
                            datetime = reading['DateTime']
                            edit_datetime = datetime[:8] + 'T' + datetime[8:]
                            indiv_reading.append(edit_datetime)
                            indiv_reading.append(reading['Value'])
                            light.append(indiv_reading)
                    elif i['VariableCode'].endswith('temperature'):
                        for reading in i['Data']:
                            indiv_reading = []
                            datetime = reading['DateTime']
                            edit_datetime = datetime[:8] + 'T' + datetime[8:]
                            indiv_reading.append(edit_datetime)
                            indiv_reading.append(reading['Value'])
                            air_temperature.append(indiv_reading)
                    elif i['VariableCode'].endswith('level'):
                        for reading in i['Data']:
                            indiv_reading = []
                            datetime = reading['DateTime']
                            edit_datetime = datetime[:8] + 'T' + datetime[8:]
                            indiv_reading.append(edit_datetime)
                            indiv_reading.append(reading['Value'])
                            battery_level.append(indiv_reading)
                print('Success')
            except Exception as error:
                print(json_object, "Error: ", error, "Sensor_id: ", sensor_id)
                continue
            break
    return sensor_id, soil_moisture, light, air_temperature, battery_level

def convert_lists_to_dataframe(sensor_id: str, soil_moisture: List,
                                light: List, air_temperature: List,
                                battery_level: List) -> 'DataFrame':
    """Convert GROW data lists to 1 DataFrame. 
    Save DataFrame to local file.
    """
    df = pd.DataFrame(soil_moisture, columns=['datetime', 'soil_moisture'])
    df['light'] = [x[1] for x in light]
    df['air_temperature'] = [x[1] for x in air_temperature]
    df['battery_level'] = [x[1] for x in battery_level]
    df['sensor_id'] = sensor_id
    df.to_csv(f'temp_csvs/grow_data_{sensor_id}.csv', index=False)

def insert_df_to_aurora(aurora_creds: dict, sensor_id: str) -> None:
    """Create table in AWS Aurora and insert GROW data"""
    with UseDatabase(aurora_creds) as cursor:
        table_name = f"grow_data_{sensor_id}"
        sql_create = sql.SQL("""CREATE TABLE IF NOT EXISTS {}(
                        sensor_id varchar(8),
                        datetime timestamp, 
                        soil_moisture numeric, 
                        light numeric, 
                        air_temperature numeric,
                        battery_level numeric
                        )""").format(sql.Identifier(table_name))
        cursor.execute(sql_create)
        with open(f'temp_csvs/grow_data_{sensor_id}.csv') as csv:
            next(csv)
            cursor.copy_from(csv, table_name, columns=('datetime','soil_moisture','light','air_temperature','battery_level','sensor_id'), sep=',')

def main(aurora_host: str, db_name: str, aurora_username: str, aurora_password: str):
    """Extracts all GROW data from all GROW sensors and inserts that data
    to AWS Aurora database tables. 1 table for each GROW sensor.
    """
    aurora_creds = {
        'host': aurora_host,
        'port': 5432,
        'dbname': db_name,
        'user': aurora_username,
        'password': aurora_password
    }
    sensor_uptime_list = grab_grow_sensor_uptimes()
    for i in sensor_uptime_list:
        sensor_id, sensor_start_end_intervals = check_most_recent_grow_data(aurora_creds, i[0], i[1], i[2])
        if sensor_start_end_intervals == []:
            continue
        sensor_id, soil_moisture, light, air_temperature, battery_level = grab_grow_data(sensor_id, sensor_start_end_intervals)
        convert_lists_to_dataframe(sensor_id, soil_moisture, light, air_temperature, battery_level)
        insert_df_to_aurora(aurora_creds, sensor_id)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('aurora_host')
    parser.add_argument('db_name')
    parser.add_argument('aurora_username')
    parser.add_argument('aurora_password')
    args = parser.parse_args()
    main(args.aurora_host, args.db_name, args.aurora_username, args.aurora_password)




        





