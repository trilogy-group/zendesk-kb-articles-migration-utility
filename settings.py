from os import environ

SOURCE_HC_URL = environ.get('SOURCE_HC_URL', None)
DESTINATION_HC_URL = environ.get('DESTINATION_HC_URL', None)
SRC_USER = environ.get('SRC_USER', None)
SRC_PASSWORD = environ.get('SRC_PASSWORD', None)
src_auth = (SRC_USER, SRC_PASSWORD)

DST_USER = environ.get('DST_USER', None)
DST_PASSWORD = environ.get('DST_PASSWORD', None)
dst_auth = (DST_USER, DST_PASSWORD)
