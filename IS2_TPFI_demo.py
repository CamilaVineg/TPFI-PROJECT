#*-----------------------------------------------------------------------------$
#* UADER-FCyT
#* Ingeniería de Software II
#*
#* Dr. Pedro E. Colla
#* (2003-2025)
#*
#* IS2_TPFI_demo.py
#* Programa auxiliar para verificar instalación de librerías y pre-requisitos A$
#*
#*-----------------------------------------------------------------------------$
import boto3
import botocore
from decimal import Decimal
import json
import uuid
import os
import platform
from os import system, name

#*-----------------------------------------------------------------------------$
#*----- Clear screen
#*-----------------------------------------------------------------------------$

# for windows
if name == 'nt':
   _ = system('cls')

# for mac and linux(here, os.name is 'posix')
else:
   _ = system('clear') 


#*-----------------------------------------------------------------------------$
# Print out some data about the table.
# This will cause a request to be made to DynamoDB and its attribute
# values will be set based on the response.
#*-----------------------------------------------------------------------------$
print("Execution Environment\n")
print("Script ejecutando en CPU [%s] OS(%s) platform(%s) release(%s) node(%s) machine(%s)" % 
(uuid.getnode(),os.name,platform.system(),platform.release(),platform.node(),platform.machine()))
uniqueID = uuid.uuid4()
print("Session ID (%s)" % (uniqueID)) 

#*-----------------------------------------------------------------------------$
# Get the service resource.
#*-----------------------------------------------------------------------------$
dynamodb = boto3.resource('dynamodb')

#*-----------------------------------------------------------------------------$
# Instantiate a table resource object without actually
# creating a DynamoDB table. Note that the attributes of this table
# are lazy-loaded: a request is not made nor are the attribute
# values populated until the attributes
# on the table resource are accessed or its load() method is called.
#*-----------------------------------------------------------------------------$

table = dynamodb.Table('CorporateData')
print("Table %s creation date: %s" % (table.name,table.creation_date_time))

#*-----------------------------------------------------------------------------$
#* Access the record
#*-----------------------------------------------------------------------------$
response = table.get_item(
    Key={
        'id': 'UADER-FCyT-IS2'
    }
)

item = response['Item']
print("Response (JSON)")
print("---------------")
print(item)
print("---------------")

#*----------------------------------------------------------------------------
#* Manipulate data
#*----------------------------------------------------------------------------
print("All data elements in tuple")
print(" ")
for item in response['Item']:
        print(item)
print(" ")

x = {
	"sede" : response['Item']['sede'],
	"domicilio" : response['Item']['domicilio'],
	"localidad" : response['Item']['localidad'],
	"provincia" : response['Item']['provincia']
}
print("Python object dump")
print("------------------")
y=json.dumps(x)
print(y)
print("------------------")

print("Update test")
print("------------------")
#newid=20
oldnewid=response['Item']['idreq']
newid=oldnewid+1
print("Updating item newid (%d)-->(%d)" % (oldnewid,newid))
try:
	response = table.update_item(
                Key={"id": "UADER-FCyT-IS2"},
                UpdateExpression="set idreq = :r",
                ExpressionAttributeValues={":r": Decimal(str(newid))},
                ReturnValues="UPDATED_NEW",
            )
except botocore.exceptions.ClientError as err:
		print("error accediendo tabla %s Error [%s,%s]" % (table.name,err.response["Error"]["Code"],err.response["Error"]["Message"]))
		raise
else:
		print(response["Attributes"])
print("Update completed")



