#*-----------------------------------------------------------------------------$
#* UADER-FCyT
#* Ingeniería de Software II
#*
#* Dr. Pedro E. Colla
#* (2003-2025)
#*
#* IS2_TPFI-uuid.py
#* Programa auxiliar para generar ID único (uuid)#*
#*-----------------------------------------------------------------------------$

import uuid
result = uuid.uuid4()
result.hex
print(result.hex)
