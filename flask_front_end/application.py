#!/usr/bin/env python3

import ast
import base64
import boto3

from botocore.exceptions import ClientError
from flask import Flask, render_template, request, jsonify
from use_postgres import UseDatabase
from psycopg2 import sql

application = Flask(__name__)
app = application

@app.before_first_request
def before_first_request():
    """Retrieve secret credentials for AWS RDS Aurora Database
    from AWS Secrets Manager.
    """
    secret_name = "grow-data-key"
    region_name = "eu-west-1"
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    # We rethrow the exception by default.
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
    global aurora_creds
    aurora_creds = {
        'host': aurora_secret['host'],
        'port': aurora_secret['port'],
        'dbname': aurora_secret['engine'],
        'user': aurora_secret['username'],
        'password': aurora_secret['password']
    }

@app.route('/login')
def entry() -> 'html':
    """Renders Entry page with two statistics from SQL queries"""
    with UseDatabase(aurora_creds) as cursor:
        sql_select_sensors = """select count(*) from all_sensor_info ;"""
        cursor.execute(sql_select_sensors)
        sensors = cursor.fetchone()[0]
        sql_select_owners = """SELECT COUNT(DISTINCT(owner_id)) 
                                FROM all_sensor_info;"""
        cursor.execute(sql_select_owners)
        owners = cursor.fetchone()[0]

    return render_template('login.html', number_sensors=sensors,
                            number_owners=owners)

@app.route('/all_grow_map')
def all_grow_map() -> 'html':
    """Renders GROW map page with four statistics from SQL queries"""
    with UseDatabase(aurora_creds) as cursor:
        sql_select_sensors = """select count(*) from all_sensor_info ;"""
        cursor.execute(sql_select_sensors)
        total_sensors = cursor.fetchone()[0]
        sql_select_healthy = """SELECT count(*)
                        FROM all_sensor_info 
                        WHERE sensor_id NOT IN 
                            (SELECT SUBSTRING(grow_table, 11, 8) 
					        FROM grow_anomalies);"""
        cursor.execute(sql_select_healthy)
        healthy_sensors = cursor.fetchone()[0]
        sql_select_recovered = """SELECT count(*)
                        FROM all_sensor_info 
                        WHERE sensor_id IN 
                            (SELECT SUBSTRING(grow_table, 11, 8) 
					        FROM grow_anomalies
				   	        WHERE days_since_anomaly >= 2);"""
        cursor.execute(sql_select_recovered)
        recovered_sensors = cursor.fetchone()[0]
        sql_select_faulty = """SELECT count(*)
                        FROM all_sensor_info 
                        WHERE sensor_id IN 
                            (SELECT SUBSTRING(grow_table, 11, 8) 
					        FROM grow_anomalies
				   	        WHERE days_since_anomaly < 2);"""
        cursor.execute(sql_select_faulty)
        faulty_sensors = cursor.fetchone()[0]
    return render_template('new_grow_map.html', healthy_sensors=healthy_sensors,
                            recovered_sensors=recovered_sensors, faulty_sensors=faulty_sensors,
                            number_sensors=total_sensors)

@app.route('/owner_map')
def owner_map() -> 'html':
    """Renders Owner map page"""
    return render_template('owner_map.html')

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    """Accepts HTML input and searces text in SQL statement,
    returns all results matching the HTML input text.
    """
    with UseDatabase(aurora_creds) as cursor:
        search = request.args.get('q')
        search_str = f'%{search}%'
        sql_select = sql.SQL("""SELECT address 
                                FROM all_sensor_info
                                WHERE address LIKE {}""").format(sql.Literal(search_str))
        cursor.execute(sql_select)
        results = [i[0] for i in cursor.fetchall()]
        return jsonify(matching_results=results)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
