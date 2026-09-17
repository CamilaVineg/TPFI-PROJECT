#*---------------------------------------------------------------------------------------------------------------
#* UADER-FCyT
#* Ingeniería de Software II
#* 
#* (c) Dr. Pedro E. Colla (2003-2025)
#*
#* IS2_TPFI_insert.py
#* Programa auxiliar para verificar la inserción de registros en la tabla Log
#*
#*---------------------------------------------------------------------------------------------------------------
import boto3
import botocore
from decimal import Decimal
from os import system, name
import json
import uuid
import os
import platform
import subprocess
from datetime import datetime

#*----- Clear screen
# for windows
if name == 'nt':
   _ = system('cls')

# for mac and linux(here, os.name is 'posix')
else:
   _ = system('clear') 

print("Program %s Dynamo DB Insert test data\n" % (os.path.basename(__file__)))

#*---- Acquire AWS DynamoDB resources, table CorporateData

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('CorporateLog')

#*---- Create unique record ID and establish data
uniqueID=str(uuid.uuid4())
CPUid=str(uuid.getnode())
sessionid=str(uuid.uuid4())

now = datetime.now()
ts = now.strftime("%Y-%m-%d %H:%M:%S")

#*---- Insert Record 
print("Inserted record at DynamoDB table (%s)\n" % (table))
response = table.put_item(
           Item={
            'id': uniqueID,
            'CPUid' : CPUid,
            'sessionid' : sessionid,
            'timestamp': ts
        }
)
    
print("id=%s CPU=%s session=%s time=%s\n" % (uniqueID,CPUid,sessionid,ts))
status_code = response['ResponseMetadata']['HTTPStatusCode']
print("status code:",status_code)

