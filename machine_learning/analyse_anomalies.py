#!/usr/bin/env python3

import argparse
from datetime import timedelta
from psycopg2 import sql

from use_postgres import UseDatabase

def main(aurora_host: str, db_name: str, db_username: str, db_password: str):
    """Connects to Aurora Database, calculates the delta between
    most recent GROW anomaly and most recent GROW recorded date.
    Inserts the delta as 'days_since_anomaly' column in 
    'grow_anomalies' Aurora table.
    """
    aurora_creds = {
            'host': aurora_host,
            'port': 5432,
            'dbname': db_name,
            'user': db_username,
            'password': db_password
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
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('aurora_host')
    parser.add_argument('db_name')
    parser.add_argument('aurora_username')
    parser.add_argument('aurora_password')
    args = parser.parse_args()
    main(args.aurora_host, args.db_name, args.aurora_username, args.aurora_password)