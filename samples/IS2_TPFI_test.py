#*---------------------------------------------------------------------------------------------------------------
#* UADER-FCyT
#* Ingeniería de Software II
#*
#* Dr. Pedro E. Colla
#* (2003-2025)
#*
#* IS2_TPFI_test.py
#* Programa auxiliar para verificar instalación de librerías y pre-requisitos AWS BOTO3 y credenciales de uso
#*
#*---------------------------------------------------------------------------------------------------------------
import boto3
import botocore
from decimal import Decimal
import json
import uuid
import os
from os import system, name
import sys
import platform
from botocore.exceptions import ClientError

#*----- Acquire running environment

VERSION="1.1"
CPUid=uuid.getnode()
CPUplatform=platform.system()
OSname=os.name
CPUrelease=platform.release()
CPUnode=platform.node()
CPUmachine=platform.machine()

#*----- Clear screen
# for windows
if name == 'nt':
   _ = system('cls')
 
# for mac and linux(here, os.name is 'posix')
else:
   _ = system('clear')

print("Program: %s Version %s UADER-FCyT-IS2 Programa de test y diagnóstico\n" % (os.path.basename(__file__),VERSION))
print("CPU ID[%s] OS(%s) platform(%s) release(%s) node(%s) machine(%s)" % (CPUid,OSname,CPUplatform,CPUrelease,CPUnode,CPUmachine))
print("Session ID(%s)" % (uuid.uuid4()))


# Instantiate a table resource object without actually
# creating a DynamoDB table. Note that the attributes of this table
# are lazy-loaded: a request is not made nor are the attribute
# values populated until the attributes
# on the table resource are accessed or its load() method is called.
# Print out some data about the table.
# This will cause a request to be made to DynamoDB and its attribute
# values will be set based on the response.

# Previously the command aws configure must be ran to provide the 
# AWS API Key and Secret string

#*----- Connect to DB, table CorporateData, get table details

try:
	dynamodb = boto3.resource('dynamodb')

	table = dynamodb.Table('CorporateData')
	print("Corporate Data table creation date ",table.creation_date_time)

	table = dynamodb.Table('CorporateLog')
	print("Corporate Log table creation date ",table.creation_date_time)

#*---- Handle exceptions

except Exception as e:
	print("Unexpected error: %s" % e)
	sys.exit()

#*---- End program
print("Completed successfully")

