#!/usr/bin/env python3

import ast
import argparse
import base64
import datetime
from typing import List, Tuple

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import ClientError
from keras.models import load_model
from psycopg2 import sql
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy import create_engine

from use_postgres import UseDatabase

def get_grow_tables_to_analyse(aurora_creds: dict) -> np.ndarray:
    """Return all GROW table names from AWS Aurora DB that have
    not been analysed, or GROW tables with new data that 
    has not yet been analysed.
    """
    with UseDatabase(aurora_creds) as cursor:
        # Fetch all grow data table names
        sql_all = """SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name 
                    LIKE 'grow_data_%%';"""
        cursor.execute(sql_all)
        all_tables_array = cursor.fetchall()
        grow_tables = []
        for i in all_tables_array:
            # Fetch most recent observation date recorded per grow table
            sql_grow = sql.SQL("""SELECT CONCAT('grow_data_', sensor_id), datetime
                                FROM {}
                                WHERE datetime = (SELECT MAX(datetime) FROM {})
                                """).format(sql.Identifier(i[0]),
                                            sql.Identifier(i[0]))
            cursor.execute(sql_grow)
            result_array = cursor.fetchall()
            grow_tables.append(result_array)
        # Fetch most recently analysed grow table & date
        sql_anom = """SELECT grow_table, 
                        MAX(last_analysed) 
                FROM public.grow_anomalies 
                GROUP BY grow_table;"""
        cursor.execute(sql_anom)
        anom_tables_array = cursor.fetchall()
        # Find grow tables that have not been analysed yet, and 
        # grow tables that have new data that needs to be analysed
        tables_to_analyse = []
        for i in grow_tables:
            # If grow table has not been analysed yet
            if i[0][0] not in [x[0] for x in anom_tables_array]:
                tables_to_analyse.append(i[0][0])
                continue
            for tab in anom_tables_array:
                # If grow table has more recent data than that already analysed
                if i[0][0] == tab[0] and i[0][1] > tab[1]:
                    tables_to_analyse.append(i[0][0])
    return tables_to_analyse

def get_keras_models() -> '3 Keras Models':
    """Retrieve previously trained Keras models for anomaly detection"""
    soil_model = load_model('soil_model.h5')
    light_model = load_model('light_model.h5')
    air_model = load_model('air_model.h5')
    return soil_model, light_model, air_model

def predict_df_length_check(table_name: str, conn):
    """Retrieve GROW data from GROW table, convert it 
    to a DataFrame divisible by 96. Declare whether the
    DataFrame has over 96 observations.
    """
    sql_select = f"""SELECT * FROM {table_name}"""
    analyse_datetime = datetime.datetime.now()
    df = pd.read_sql(sql_select, conn, parse_dates=['datetime'])
    # Dataframe is not ordered, sort by datetime
    df = df.sort_values(axis=0, by=['datetime'])
    # Chop off beginning of df to make it divisible by 96
    # 96 observations equal one day of observations
    remainder = len(df) % 96
    predict_df = df[remainder:]
    # If df does not have a minimum of 96 observations, declare it empty
    if len(predict_df) == 0:
        empty_df = True
        return predict_df, analyse_datetime, empty_df
    else:
        empty_df = False
        return predict_df, analyse_datetime, empty_df

def construct_predict_dfs(predict_df: pd.DataFrame) -> Tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,np.ndarray]:
    """Construct 3 DataFrames and one Numpy array from the contents of 
    previously created DataFrame. These DataFrames will be 
    analysed against the Keras models previously built to 
    detect anomalies/anomalous data.
    """
    predict_df_2 = predict_df.copy(deep=True)
    predict_df_3 = predict_df.copy(deep=True)
    predict_df_4 = predict_df.copy(deep=True)
    # Drop all columns except for one for each df [soil, light, air_temp, dates]
    predict_df_soil = predict_df.drop(['sensor_id'], axis=1) \
                                .drop(['datetime'], axis=1) \
                                .drop(['light'], axis=1) \
                                .drop(['air_temperature'], axis=1) \
                                .drop(['battery_level'], axis=1)
    predict_df_light = predict_df_2.drop(['sensor_id'], axis=1) \
                                    .drop(['datetime'], axis=1) \
                                    .drop(['soil_moisture'], axis=1) \
                                    .drop(['air_temperature'], axis=1) \
                                    .drop(['battery_level'], axis=1)
    predict_df_air = predict_df_3.drop(['sensor_id'], axis=1) \
                                .drop(['datetime'], axis=1) \
                                .drop(['soil_moisture'], axis=1) \
                                .drop(['light'], axis=1) \
                                .drop(['battery_level'], axis=1)
    predict_dates = predict_df_4.drop(['sensor_id'], axis=1) \
                                .drop(['soil_moisture'], axis=1) \
                                .drop(['light'], axis=1) \
                                .drop(['air_temperature'], axis=1) \
                                .drop(['battery_level'], axis=1)
    # Normalize data to fall between [0,1]
    scaler = MinMaxScaler()
    predict_df_soil_scaled = scaler.fit_transform(predict_df_soil)
    predict_df_light_scaled = scaler.fit_transform(predict_df_light)
    predict_df_air_scaled = scaler.fit_transform(predict_df_air)
    # Reshape data into chunks of 96 -> ie: (472, 96, 1)
    timesteps = 96
    dim = 1
    samples = len(predict_df_soil_scaled)
    predict_df_soil_scaled.shape = (int(samples/timesteps),timesteps,dim)
    predict_df_light_scaled.shape = (int(samples/timesteps),timesteps,dim)
    predict_df_air_scaled.shape = (int(samples/timesteps),timesteps,dim)
    predict_dates_array = predict_dates.values
    predict_dates_array.shape = (int(samples/timesteps),timesteps,dim)
    return predict_df_soil_scaled, predict_df_light_scaled, \
            predict_df_air_scaled, predict_dates_array

def predict_on_keras_models(predict_soil_df: pd.DataFrame, predict_light_df: pd.DataFrame, 
                            predict_air_df: pd.DataFrame, soil_model, 
                            light_model, air_model) -> Tuple[np.ndarray,np.ndarray,np.ndarray]:
    """Uses the provided DataFrames to predict on the previously built Keras models.
    Calculates and returns their reconstruction error to later detect anomalous data.
    """
    predictions_soil = soil_model.predict(predict_soil_df)
    # Mean-squared error: Reconstruction error
    mse_soil = np.mean(np.power(predict_soil_df - predictions_soil, 2), axis=1)
    predictions_light = light_model.predict(predict_light_df)
    mse_light = np.mean(np.power(predict_light_df - predictions_light, 2), axis=1)
    predictions_air = air_model.predict(predict_air_df)
    mse_air = np.mean(np.power(predict_air_df - predictions_air, 2), axis=1)
    return mse_soil, mse_light, mse_air

def analyse_soil_error(mse_soil: np.ndarray, predict_dates: np.ndarray) -> List:
    """Loop through soil reconsruction error array. If error is 
    identical twice in a row, flag as anomaly. Record error and 
    its respective datetime in result array.
    """
    anomalous_results = []
    for index, mse in enumerate(mse_soil[:-1]):
        if mse[0] == mse_soil[index + 1]:
            anomalous_results.append([mse[0], predict_dates[index][0][0]])
    return anomalous_results

def analyse_light_error(mse_light: np.ndarray, predict_dates: np.ndarray) -> List:
    """Loop through light reconsruction error array. If error is 
    identical twice in a row, flag as anomaly. Record error and 
    its respective datetime in result array.
    """
    anomalous_results = []
    for index, mse in enumerate(mse_light[:-1]):
        if mse[0] == mse_light[index + 1]:
            anomalous_results.append([mse[0], predict_dates[index][0][0]])
    return anomalous_results

def analyse_air_error(mse_air: np.ndarray, predict_dates: np.ndarray) -> List:
    """Loop through air reconsruction error array. If error is 
    identical twice in a row, flag as anomaly. Record error and 
    its respective datetime in result array.
    """
    anomalous_results = []
    for index, mse in enumerate(mse_air[:-1]):
        if mse[0] == mse_air[index + 1]:
            anomalous_results.append([mse[0], predict_dates[index][0][0]])
    return anomalous_results

def create_anomaly_table(conn) -> None:
    """Create table to store anomalous information in 
    AWS Aurora instance (Postgresql compatible)
    """
    sql_create = """CREATE TABLE IF NOT EXISTS grow_anomalies(
            grow_table varchar(18),
            soil_date timestamp, 
            light_date timestamp, 
            air_date timestamp,
            last_analysed timestamp
            )"""
    conn.execute(sql_create)

def insert_anomalies(soil_anomalies: List, light_anomalies: List,
                    air_anomalies: List, table_name: str,
                    aurora_creds: dict, analyse_datetime: str) -> None:
    """Insert anomalous datetimes into AWS Aurora grow_anomalies table"""
    with UseDatabase(aurora_creds) as cursor:
        # If grow sensor table is already in grow_anomalies, delete the rows
        # so fresh data can be inserted in its place
        sql_check = sql.SQL("""SELECT * FROM grow_anomalies
                            WHERE grow_table = {}
                            LIMIT 1;""").format(sql.Literal(table_name))
        cursor.execute(sql_check)
        results = cursor.fetchall()
        if results:
            sql_delete = sql.SQL("""DELETE FROM grow_anomalies
                                WHERE grow_table = {}""").format(sql.Literal(table_name))
            cursor.execute(sql_delete)
        for anom in soil_anomalies:
            sql_insert = sql.SQL("""INSERT INTO grow_anomalies
                            (grow_table, soil_date, last_analysed)
                            VALUES({},{},{})""") \
                            .format(sql.Literal(table_name),
                                    sql.Literal(str(anom[1])),
                                    sql.Literal(analyse_datetime))
            cursor.execute(sql_insert)
        for anom in light_anomalies:
            sql_insert = sql.SQL("""INSERT INTO grow_anomalies
                            (grow_table, light_date, last_analysed)
                            VALUES({},{},{})""") \
                            .format(sql.Literal(table_name),
                                    sql.Literal(str(anom[1])),
                                    sql.Literal(analyse_datetime))
            cursor.execute(sql_insert)
        for anom in air_anomalies:
            sql_insert = sql.SQL("""INSERT INTO grow_anomalies
                            (grow_table, air_date, last_analysed)
                            VALUES({},{},{})""") \
                            .format(sql.Literal(table_name),
                                    sql.Literal(str(anom[1])),
                                    sql.Literal(analyse_datetime))
            cursor.execute(sql_insert)

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

def main():
    """Scans through all GROW data to find anomalies. 
    Stores anomalous findings (datetimes of anomalies)
    in AWS Aurora 'grow_anomalies' table.
    """
    aurora_secret = get_aurora_secret()
    aurora_creds = {
        'host': aurora_secret['host'],
        'port': aurora_secret['port'],
        'dbname': aurora_secret['engine'],
        'user': aurora_secret['username'],
        'password': aurora_secret['password']
    }
    conn = create_engine(f"postgresql+psycopg2://{aurora_secret['username']}:{aurora_secret['password']}@{aurora_secret['host']}/{aurora_secret['engine']}")

    tables_to_analyse = get_grow_tables_to_analyse(aurora_creds)
    soil_model, light_model, air_model = get_keras_models()
    for table in tables_to_analyse:
        predict_df, analyse_datetime, empty_df = predict_df_length_check(table, conn)
        if empty_df == True:
            continue
        predict_soil, predict_light, predict_air, predict_dates = construct_predict_dfs(predict_df)
        mse_soil, mse_light, mse_air = predict_on_keras_models(predict_soil, predict_light, predict_air,
                                                                soil_model, light_model, air_model)
        anomalous_soil = analyse_soil_error(mse_soil, predict_dates)
        anomalous_light = analyse_light_error(mse_light, predict_dates)
        anomalous_air = analyse_air_error(mse_air, predict_dates)
        create_anomaly_table(conn)
        insert_anomalies(anomalous_soil, anomalous_light, anomalous_air, table,
                        aurora_creds, analyse_datetime)

if __name__ == '__main__':
    main()

