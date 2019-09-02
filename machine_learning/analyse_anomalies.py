#!/usr/bin/env python3

from datetime import timedelta
from psycopg2 import sql

from use_postgres import UseDatabase

aurora_creds = {
        'host': 'grow-data-instance-1.cynbkpreeybn.eu-west-1.rds.amazonaws.com',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'grow_user',
        'password': 'ILoveGROW'
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
        


        # if result_datetime[0] - i[1] < timedelta(days=2):
        #     present_anomaly.append(i[0])
    # 436 GROW sensors currently reporting anomalous data < 4 days apart
    # 324 GROW sensors currently reporting anomalous data < 2 days apart
    # 0 GROW sensors currently reporting anomalous data < 1 days apart

# Long python version without using GREATEST SQL keyword
# with UseDatabase(aurora_creds) as cursor:
#     sql_anomaly = """SELECT grow_table,
#                             MAX(soil_date),
#                             MAX(light_date),
#                             MAX(air_date)
#                     FROM public.grow_anomalies
#                     GROUP BY grow_table;"""
#     cursor.execute(sql_anomaly)
#     anomaly_dates = cursor.fetchall()
#     max_anomaly_dates = []
#     # Remove nulls from result list
#     for i in anomaly_dates:
#         grow_sensor = []
#         grow_sensor.append(i[0])
#         if i[1] is not None:
#             grow_sensor.append(i[1])
#         if i[2] is not None:
#             grow_sensor.append(i[2])
#         if i[3] is not None:
#             grow_sensor.append(i[3])
#         max_anomaly_dates.append(grow_sensor)
#     # max_date consists of GROW sensor id and most recent anomaly date
#     max_date = []
#     for i in max_anomaly_dates:
#         max_date.append([i[0], max(i[1:])])

#     present_anomaly = []
#     all_deltas = []
#     for i in max_date:
#         sql_select = sql.SQL("""SELECT MAX(datetime)
#                             FROM {}""").format(sql.Identifier(i[0]))
#         cursor.execute(sql_select)
#         result_datetime = cursor.fetchone()
#         all_deltas.append([i[0], result_datetime[0] - i[1]])