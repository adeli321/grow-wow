#!/usr/bin/env python3

import ast
import os
import base64
from typing import List

import boto3
from botocore.exceptions import ClientError
import requests
from psycopg2 import sql
from flask_cors import CORS, cross_origin
from flask import Flask, jsonify, request, Response

from use_postgres import UseDatabase

application = Flask(__name__)
app = application
CORS(app)

@app.before_first_request
def before_first_request():
    """Retrieve secret credentials for AWS RDS Aurora Database,
    GROW Thingful API & Met Office WOW API from AWS Secrets Manager.
    """
    secret_name = "grow-data-key"
    region_name = "eu-west-1"
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    # Rethrow the exception by default.
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            # Convert string to dictionary to later access secret values
            aurora_secret = ast.literal_eval(secret)
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])

    # Retrieve secret credentials for GROW Thingful API
    secret_name = "grow-api"
    region_name = "eu-west-1"
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            global grow_api_secret
            grow_api_secret = ast.literal_eval(secret)
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])

    # Retrieve secret credentials for Met Office WOW API
    secret_name = "wow-api"
    region_name = "eu-west-1"
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            global wow_api_secret
            wow_api_secret = ast.literal_eval(secret)
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])

    global aurora_creds
    aurora_creds = {
            'host': aurora_secret['host'],
            'port': aurora_secret['port'],
            'dbname': aurora_secret['engine'],
            'user': aurora_secret['username'],
            'password': aurora_secret['password']
        }
    return aurora_creds, grow_api_secret, wow_api_secret

@app.route('/api/all_grow_true_json')
@cross_origin()
def fetch_all_json() -> 'JSON':
    """Fetch all GROW sensor info as JSON"""
    with UseDatabase(aurora_creds) as cursor:
        resp_list = []
        SQL = """SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info;"""
        cursor.execute(SQL)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/api/all_grow_healthy_json')
@cross_origin()
def fetch_all_healthy_json() -> 'JSON':
    """Fetch all healthy GROW sensor info as JSON"""
    with UseDatabase(aurora_creds) as cursor:
        resp_list = []
        SQL = """SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info 
                WHERE sensor_id NOT IN 
                    (SELECT SUBSTRING(grow_table, 11, 8) 
					FROM grow_anomalies);"""
        cursor.execute(SQL)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/api/all_grow_recovered_json')
@cross_origin()
def fetch_all_recovered_json() -> 'JSON':
    """Fetch all recovered GROW sensor info as JSON"""
    with UseDatabase(aurora_creds) as cursor:
        resp_list = []
        SQL = """SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info 
                WHERE sensor_id IN 
                    (SELECT SUBSTRING(grow_table, 11, 8) 
					FROM grow_anomalies
				   	WHERE days_since_anomaly >= 2);"""
        cursor.execute(SQL)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/api/all_grow_faulty_json')
@cross_origin()
def fetch_all_faulty_json() -> 'JSON':
    """Fetch all faulty GROW sensor info as JSON"""
    with UseDatabase(aurora_creds) as cursor:
        resp_list = []
        SQL = """SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info 
                WHERE sensor_id IN 
                    (SELECT SUBSTRING(grow_table, 11, 8) 
					FROM grow_anomalies
				   	WHERE days_since_anomaly < 2);"""
        cursor.execute(SQL)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/api/indiv_grow_data')
@cross_origin()
def get_me_grow() -> 'JSON': 
    """Fetch GROW data for specified sensor & time interval"""
    start = request.args.get('start', None)
    start = start.replace('-','').replace('T','').replace(':','')
    end = request.args.get('end', None)
    end = end.replace('-','').replace('T','').replace(':','')
    sensor_id = request.args.get('sensor_id', None)
    header = grow_api_secret
    url = 'https://grow.thingful.net/api/timeSeries/get'
    payload = {'Readers': [{'DataSourceCode': 'Thingful.Connectors.GROWSensors',
                            'Settings': 
                                {'LocationCodes': [sensor_id], # 02krq5q5
                                'VariableCodes': ['Thingful.Connectors.GROWSensors.light',
                                                'Thingful.Connectors.GROWSensors.air_temperature',
                                                'Thingful.Connectors.GROWSensors.calibrated_soil_moisture'],
                                'StartDate': start, # 20181028200000
                                'EndDate': end }}]}
    response = requests.post(url, headers=header, json=payload)
    return response.content

@app.route('/api/check_faulty_grow')
@cross_origin()
def check_faulty_grow() -> List:
    """Fetch most recent anomaly date for specific GROW sensor"""
    sensor_id = request.args.get('sensor_id', None)
    grow_table = f'grow_data_{sensor_id}'
    with UseDatabase(aurora_creds) as cursor:
        sql_select = sql.SQL("""SELECT days_since_anomaly, 
                                MAX(GREATEST(soil_date, light_date, air_date))
                                FROM grow_anomalies
                                WHERE grow_table = {}
                                GROUP BY days_since_anomaly;""").format(sql.Literal(grow_table))
        cursor.execute(sql_select)
        response = cursor.fetchall()
    return jsonify(response)

@app.route('/api/get_wow_data')
@cross_origin()
def get_me_wow() -> 'JSON':
    """Fetch WOW data for specific GROW sensor. Another function
    match_wow_site is used to retrieve the nearest WOW site
    """
    sensor_id = request.args.get('sensor_id', None)
    start = request.args.get('start', None)
    end = request.args.get('end', None)
    wow_site_id, distance = match_wow_site(sensor_id)
    header = wow_api_secret
    url = 'https://apimgmt.www.wow.metoffice.gov.uk/api/observations/byversion'
    payload = {'site_id': wow_site_id,
            'start_time': start, # 2019-05-24T20:00:00
            'end_time': end}
    response = requests.get(url, headers=header, params=payload)
    json_object = response.json()
    data_dict = dict()
    data_dict['distance'] = []
    data_dict['datetime'] = []
    data_dict['air_temp'] = []
    data_dict['rainfall'] = []
    for i in json_object['Object']:
        data_dict['air_temp'].append(i['DryBulbTemperature_Celsius'])
        data_dict['rainfall'].append(i['RainfallAmount_Millimetre'])
        data_dict['datetime'].append(i['ReportEndDateTime'])
    data_dict['distance'].append(float(distance))
    return jsonify(data_dict)

def match_wow_site(sensor_id: str) -> str:
    """Find closest WOW site to select grow sensor"""
    with UseDatabase(aurora_creds) as cursor:
        cursor.execute("""SELECT site_id, distance
                            FROM grow_to_wow_mapping
                            WHERE sensor_id = %s;""", (sensor_id,))
        site_id = cursor.fetchone() 
    return site_id 

@app.route('/grow_by_address')
def grow_by_address() -> 'JSON':
    """Fetch all sensor info by address"""
    with UseDatabase(aurora_creds) as cursor:
        address = request.args.get('address')
        resp_list = []
        sql_select = sql.SQL("""SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info
                WHERE address = {};""").format(sql.Literal(address))
        cursor.execute(sql_select)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/grow_by_owner')
def grow_by_owner() -> 'JSON':
    """Fetch all sensor info by owner"""
    with UseDatabase(aurora_creds) as cursor:
        owner = request.args.get('owner_id')
        resp_list = []
        sql_select = sql.SQL("""SELECT row_to_json(all_sensor_info)
                FROM all_sensor_info
                WHERE owner_id = {};""").format(sql.Literal(owner))
        cursor.execute(sql_select)
        response = cursor.fetchall()
        for i in response:
            resp_list.append(i[0])
    return jsonify(resp_list)

@app.route('/owner_stats')
def owner_stats() -> 'DataTable':
    """Return count of healthy, recovered, & faulty GROW sensors
    per GROW owner.
    """
    with UseDatabase(aurora_creds) as cursor:
        owner = request.args.get('owner_id')
        sql_healthy = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id NOT IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_healthy)
        healthy_sensors = [x[0] for x in cursor.fetchall()]
        sql_recovered = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies
				   	            WHERE days_since_anomaly >= 2)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_recovered)
        recovered_sensors = [x[0] for x in cursor.fetchall()]
        sql_faulty = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies
				   	            WHERE days_since_anomaly < 2)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_faulty)
        faulty_sensors= [x[0] for x in cursor.fetchall()]
        sensor_dict = dict()
        sensor_dict['owner_id'] = owner
        sensor_dict['healthy'] = healthy_sensors
        sensor_dict['recovered'] = recovered_sensors
        sensor_dict['faulty'] = faulty_sensors
        print(jsonify(sensor_dict))
    return jsonify(sensor_dict)

@app.route('/healthy_stats')
def healthy_stats() -> 'JSON':
    """Return most recent healthy GROW data"""
    with UseDatabase(aurora_creds) as cursor:
        owner = request.args.get('owner_id')
        sql_healthy = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id NOT IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_healthy)
        healthy_sensors = [x[0] for x in cursor.fetchall()]
        healthy_data = []
        for i in healthy_sensors:
            sql_select = sql.SQL("""SELECT sensor_id, 
                                    battery_level, 
                                    soil_moisture, 
                                    light, 
                                    air_temperature, 
                                    datetime
                                    FROM {}
                                    WHERE datetime = (SELECT MAX(datetime)
                                        FROM {})""").format(sql.Identifier(f'grow_data_{i}'),
                                        sql.Identifier(f'grow_data_{i}'))
            cursor.execute(sql_select)
            results = cursor.fetchall()
            healthy_data.append(results)
    return jsonify(healthy_data)

@app.route('/recovered_stats')
def recovered_stats() -> 'JSON':
    """Return most recent recovered GROW data"""
    with UseDatabase(aurora_creds) as cursor:
        owner = request.args.get('owner_id')
        sql_recovered = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies
				   	            WHERE days_since_anomaly >= 2)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_recovered)
        recovered_sensors = [x[0] for x in cursor.fetchall()]
        recovered_data = []
        for i in recovered_sensors:
            sql_select = sql.SQL("""SELECT sensor_id, 
                                    battery_level, 
                                    soil_moisture, 
                                    light, 
                                    air_temperature, 
                                    datetime
                                    FROM {}
                                    WHERE datetime = (SELECT MAX(datetime)
                                        FROM {})""").format(sql.Identifier(f'grow_data_{i}'),
                                        sql.Identifier(f'grow_data_{i}'))
            cursor.execute(sql_select)
            results = cursor.fetchall()
            recovered_data.append(results)
    return jsonify(recovered_data)

@app.route('/faulty_stats')
def faulty_stats() -> 'JSON':
    """Return most recent faulty GROW data"""
    with UseDatabase(aurora_creds) as cursor:
        owner = request.args.get('owner_id')
        sql_faulty = sql.SQL("""SELECT sensor_id
                            FROM all_sensor_info 
                            WHERE sensor_id IN 
                                (SELECT SUBSTRING(grow_table, 11, 8) 
					            FROM grow_anomalies
				   	            WHERE days_since_anomaly < 2)
                            AND sensor_id IN
                                (SELECT sensor_id
                                FROM all_sensor_info
                                WHERE owner_id = {});""").format(sql.Literal(owner))
        cursor.execute(sql_faulty)
        faulty_sensors = [x[0] for x in cursor.fetchall()]
        faulty_data = []
        for i in faulty_sensors:
            sql_select = sql.SQL("""SELECT sensor_id, 
                                    battery_level, 
                                    soil_moisture, 
                                    light, 
                                    air_temperature, 
                                    datetime
                                    FROM {}
                                    WHERE datetime = (SELECT MAX(datetime)
                                        FROM {})""").format(sql.Identifier(f'grow_data_{i}'),
                                        sql.Identifier(f'grow_data_{i}'))
            cursor.execute(sql_select)
            results = cursor.fetchall()
            faulty_data.append(results)
    return jsonify(faulty_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')