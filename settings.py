from os import environ

SOURCE_HC_URL = environ.get('SOURCE_HC_URL', None)
DESTINATION_HC_URL = environ.get('DESTINATION_HC_URL', None)
USER = environ.get('USER', None)
TOKEN = environ.get('TOKEN', None)
auth = (USER, TOKEN)
