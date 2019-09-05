This is the README.md for the source code authored by Anthony Delivanis for his 
2019 MSc Degree Project in Data Engineering. The title of the project is:
Integrating Met Office WOW Data with GROW Data and Detecting Faulty GROW Sensors with
Machine Learning.

This document explains how to run the software/scripts in case you want to 
replicate it yourself. The end product of this project is a user interface
that showcases the data integration and machine learning results.
To replicate my environment and setup, you need to have an Amazon Web
Services account (AWS). Three AWS services are used: Elastic Cloud Compute
(EC2), Elastic Beanstalk, and Relational Database Service (RDS).
Also, one of the scripts (store_sensor_info.py) and two of the HTML files
(owner_map.html, new_grow_map.html) require a valid Google Cloud Platform API Key. 

Note: you can't replicate the project completely as you need the
API keys for the GROW Thingful and Met Office WOW APIs to get data.

1. Create an RDS instance - AWS Aurora was used as the production database for this project
    1. Select Aurora - PostgreSQL compatible database
    2. Set up with default settings
    3. Enter personal credentials for access to database
    4. Create database

2. Create an EC2 instance for Python ETL Scripts
    1. Select default Amazon Linux 2 AMI 
    2. Select default settings
    3. Change Security Group rules to only allow SSH from your personal computer IP
        ie: Source: Custom 91.235.112.12/32
    4. Click launch, assign a key pair to your instance
    5. Save your key pair somewhere secure, this is needed to SSH into instance
    6. Copy Python ETL files to new EC2 instance
        1. Download files locally: extract_all_grow_data.py, 
            find_nearest_wow_live.py, store_sensor_info.py, 
            wow_observations_europe.json, detect_anomalies.py, 
            analyse_anomalies.py, air_model.h5,
            light_model.h5, soil_model.h5
        2. SCP these files to EC2 instance
            ie: scp -i path/to/key_pair.pem soil_model.h5 ec2-user@{EC2_INSTANCE_PUBLIC_DNS}:/soil_model.h5
            - Note: Port 22 (SSH) from your computer IP address must be accepted
                by the EC2 instance for the SCP to work
    7. Add RDS Security Group to Inbound connections in EC2 Security Group 
        through port 5432
    8. SSH into EC2 instance
        ie: ssh -i path/to/key_pair.pem ec2-user@{EC2_INSTANCE_PUBLIC_DNS} 
    9. Type the command 'crontab -e'
    10. Enter in Cron jobs for each Python ETL script you want to schedule
        - ie: 14 13 * * * python3 /home/ec2-user/store_sensor_info.py {Google API Key}
        - The running order should be:
            1. store_sensor_info.py
            2. find_nearest_wow_live.py
            3. extract_all_grow_data.py
            4. detect_anomalies.py
                - Script takes around 90 minutes to run
            5. analyse_anomalies.py
        - Except for detect_anomalies.py, leave at least 40 minutes in 
            between each script to ensure one finishes before the next starts
        - Cron jobs can be replaced with Apache Airflow
    11. Type the command 'crontab -l' to see your scheduled Cron jobs

3. Launch front end and back end Flask applications with Elastic Beanstalk
    1. Bundle the front end and back end applications and launch Beanstalk
        1. Change directory to flask_back_end
        2. Run command: python3 -m zipfile -c backend_zip application.py use_postgres.py requirements.txt
        3. Go to Elastic Beanstalk Console
        4. Create New Application
        5. Create New Environment - Web server environment
        6. Choose Preconfigured Python platform
        7. Upload your code: find and select your backend_zip file
        8. Create Environment - application should now be running
    2. Change directory to flask_front_end
        1. Run command: python3 -m zipfile -c frontend_zip application.py use_postgres.py requirements.txt static templates
        2. Same commands as backend Beanstalk environment creation
    3. Navigate to EC2 Console
    4. Select {Beanstalk_backend} instance
    5. Select Security Group for that instance
    6. Add RDS Security Group to Beanstalk_backend instance inbound rules on port 5432
    7. Add Beanstalk_frontend Security Group to Beanstalk_backend instance inbound rules on port 80
    8. Add RDS Security Group to Beanstalk_frontend instance inbound rules on port 5432
    9. Add HTTP rule to Beanstalk_frontend instance open to all IPs port 80 (0.0.0.0/0)
    10. Add Beanstalk_frontend & Beanstalk_backend Security Group to RDS Security Group Inbound rules on port 5432

4. Navigate to {Public_DNS}/login of Beanstalk_frontend EC2 instance to see the user interface
    - Alternatively, navigate to Elastic Beanstalk console, click on front end environment, click on that URL/login

5. For these scripts to run, you need to have access to a few credentials
    1. Store Database credentials in AWS Secrets Manager
        1. Navigate to AWS Secrets Manager Console
        2. Store a new secret
        3. Credentials for RDS database
        4. Select default settings
        5. Store secret
        6. Edit scripts to include the new secret_name and region_name in the get_secret functions
    2. Store GROW API key
        1. Same steps, except manually enter API key and value to AWS Secrets Manager
        




