#!/usr/bin/env python3

import ast
import base64
import argparse
from datetime import timedelta

import boto3
from psycopg2 import sql
from botocore.exceptions import ClientError

from use_postgres import UseDatabase

def main():
    """Connects to Aurora Database, calculates the delta between
    most recent GROW anomaly and most recent GROW recorded date.
    Inserts the delta as 'days_since_anomaly' column in 
    'grow_anomalies' Aurora table.
    """
    aurora_secret = get_aurora_secret()
    aurora_creds = {
        'host': aurora_secret['host'],
        'port': aurora_secret['port'],
        'dbname': aurora_secret['engine'],
        'user': aurora_secret['username'],
        'password': aurora_secret['password']
    }
    with UseDatabase(aurora_creds) as cursor:
        sql_anomaly = """SELECT grow_table, 
                        MAX(GREATEST(soil_date, light_date, air_date)) 
                        FROM grow_anomalies
                        GROUP BY grow_table;"""
        cursor.execute(sql_anomaly)
        anomaly_dates = cursor.fetchall()
        all_deltas = []
        for i in anomaly_dates:
            sql_select = sql.SQL("""SELECT MAX(datetime)
                                FROM {}""").format(sql.Identifier(i[0]))
            cursor.execute(sql_select)
            result_datetime = cursor.fetchone()
            all_deltas.append([i[0], result_datetime[0] - i[1]])
        for i in all_deltas:
            sql_update = sql.SQL("""UPDATE public.grow_anomalies
                                    SET days_since_anomaly = {}
                                    WHERE grow_table = {}""").format(
                                        sql.Literal(i[1].days),
                                        sql.Literal(i[0])
                                    )
            cursor.execute(sql_update)

def get_aurora_secret():
    """Retrieve AWS RDS Aurora credentials from AWS Secrets Manager"""
    secret_name = "grow-data-key"
    region_name = "eu-west-1"
    # Create a Secrets Manager client
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
            secret = ast.literal_eval(secret)
            return secret
        else:
            decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])
            return decoded_binary_secret
        
if __name__ == '__main__':
    main()