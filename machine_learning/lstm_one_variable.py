#!/usr/bin/env python3

import ast
import base64
import datetime
from typing import Tuple

import boto3
import keras
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from botocore.exceptions import ClientError
from keras.models import Model, Sequential, load_model
from keras.layers import Input, Dense, LSTM
from sklearn.preprocessing import  StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine

def create_training_dataframes(conn) -> Tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    """Create DataFrames to be passed into the neural network 
    models for training.
    """
    # Tables that have been identified as producing only normal data
    good_tables = ['grow_data_5pga25ec','grow_data_5pga25ec','grow_data_5kc81f8r','grow_data_02krq5q5','grow_data_0srkxe23']

    # Concatenate DataFrame of all GROW tables in good_tables list
    big_df = pd.DataFrame()
    for table in good_tables:
        df = pd.read_sql(f"SELECT * FROM {table}", conn, parse_dates=['datetime'])
        df = df.sort_values(axis=0, by=['datetime'])
        big_df = pd.concat([big_df, df])

    # Make big_df divisible by 96, 96 observations per day
    remainder = len(big_df) % 96
    new_df = big_df[remainder:] 

    # Copy 2 new dfs for light and air temp GROW variables
    new_df_2 = new_df.copy(deep=True)
    new_df_3 = new_df.copy(deep=True)

    # Drop extra columns so each df has one column each
    new_dates = new_df['datetime']
    new_df_soil = new_df.drop(['sensor_id'], axis=1) \
                        .drop(['datetime'], axis=1) \
                        .drop(['light'], axis=1) \
                        .drop(['air_temperature'], axis=1) \
                        .drop(['battery_level'], axis=1)
    new_df_light = new_df_2.drop(['sensor_id'], axis=1) \
                            .drop(['datetime'], axis=1) \
                            .drop(['soil_moisture'], axis=1) \
                            .drop(['air_temperature'], axis=1) \
                            .drop(['battery_level'], axis=1)
    new_df_air = new_df_3.drop(['sensor_id'], axis=1) \
                        .drop(['datetime'], axis=1) \
                        .drop(['soil_moisture'], axis=1) \
                        .drop(['light'], axis=1) \
                        .drop(['battery_level'], axis=1)

    # Normalise data to fall between [0,1]
    scaler = MinMaxScaler()
    new_df_soil_scaled = scaler.fit_transform(new_df_soil)
    new_df_light_scaled = scaler.fit_transform(new_df_light)
    new_df_air_scaled = scaler.fit_transform(new_df_air)
    timesteps = 96
    dim = 1
    samples = len(new_df_soil_scaled)
    # Reshape data for fit to neural network model
    new_df_soil_scaled.shape = (int(samples/timesteps),timesteps,dim)
    new_df_light_scaled.shape = (int(samples/timesteps),timesteps,dim)
    new_df_air_scaled.shape = (int(samples/timesteps),timesteps,dim)
    return new_df_soil_scaled, new_df_light_scaled, new_df_air_scaled

def create_models() -> Tuple[Model, Model, Model]:
    """Create LSTM Autoencoder neural network models with Keras."""
    timesteps = 96
    dim = 1
    # Create LSTM Autoencoder neural network for soil moisture
    model_soil = Sequential()
    model_soil.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_soil.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_soil.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_soil.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_soil.add(Dense(1))
    model_soil.compile(loss='mse', optimizer='adam') # starts and finishes with less val_loss & loss
    # model.compile(loss='mae', optimizer='adam') # compared to mae loss parameter
    # prediction mse is slightly less with 'mse' loss parameter
    ########
    # model & predictions performed MUCH better when the train&test datasets were
    # divisible by 96 and there was no observation gap between them

    # Create LSTM Autoencoder neural network for light
    model_light = Sequential()
    model_light.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_light.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_light.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_light.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_light.add(Dense(1))
    model_light.compile(loss='mse', optimizer='adam')

    # Create LSTM Autoencoder neural network for air temperature
    model_air = Sequential()
    model_air.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_air.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_air.add(LSTM(25,input_shape=(timesteps,dim),return_sequences=True))
    model_air.add(LSTM(50,input_shape=(timesteps,dim),return_sequences=True))
    model_air.add(Dense(1))
    model_air.compile(loss='mse', optimizer='adam')
    return model_soil, model_light, model_air

def train_models(soil_df: pd.DataFrame, light_df: pd.DataFrame,
                air_df: pd.DataFrame, model_soil,
                model_light, model_air):
    """Trains the neural networks models with the previously created
    DataFrames. Save models to local directory.
    """    
    nb_epoch = 100
    batch_size = 32

    # Train model on soil moisture data
    start_time = datetime.datetime.now()
    history_soil = model_soil.fit(soil_df, soil_df,
                            epochs=nb_epoch,
                            batch_size=batch_size,
                            shuffle=True,
                            validation_split=0.1,
                            verbose=0
                            )
    end_time = datetime.datetime.now()
    df_history_soil = pd.DataFrame(history_soil.history)

    # Train model on light data
    start_time = datetime.datetime.now()
    history_light = model_light.fit(light_df, light_df,
                            epochs=nb_epoch,
                            batch_size=batch_size,
                            shuffle=True,
                            validation_split=0.1,
                            verbose=0
                            )
    end_time = datetime.datetime.now()
    df_history_light = pd.DataFrame(history_light.history)

    # Train model on air temperature data
    start_time = datetime.datetime.now()
    history_air = model_air.fit(air_df, air_df,
                            epochs=nb_epoch,
                            batch_size=batch_size,
                            shuffle=True,
                            validation_split=0.1,
                            verbose=0
                            )
    end_time = datetime.datetime.now()
    df_history_air = pd.DataFrame(history_air.history)

    # Save the models locally
    model_soil.save('saved_models/soil_model.h5')
    model_light.save('saved_models/light_model.h5')
    model_air.save('saved_models/air_model.h5')

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
    """Creates training data and Keras neural network models. Trains the models
    using training DataFrames, then saves the trained models to a local directory.
    """
    aurora_secret = get_aurora_secret()
    conn = create_engine(f"postgresql+psycopg2://{aurora_secret['username']}:{aurora_secret['password']}@{aurora_secret['host']}/{aurora_secret['engine']}")
    soil_df, light_df, air_df = create_training_dataframes(conn)
    model_soil, model_light, model_air = create_models()
    train_models(soil_df, light_df, air_df, model_soil, model_light, model_air)


if __name__ == '__main__':
    main()




