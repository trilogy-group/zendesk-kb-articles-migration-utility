from os import environ

SOURCE_HC_URL = environ.get('SOURCE_HC_URL', None)+'/api/v2'
DESTINATION_HC_URL = environ.get('DESTINATION_HC_URL', None)+'/api/v2'
CROSSREF_ARTICLE_SOURCE = environ.get('SOURCE_HC_URL', None)+'/en-us/articles/' # TODO I made this a list with the two possible source urls (e.g. www.support.gfi.com and www.gfi-support-helpdesk.zendesk.com)
CROSSREF_ARTICLE_DESTINATION = environ.get(
    'DESTINATION_HC_URL', None)+'en-us/articles/'
SRC_USER = environ.get('SRC_USER', None)
SRC_PASSWORD = environ.get('SRC_PASSWORD', None)
src_auth = (SRC_USER, SRC_PASSWORD)

#DST_USER = environ.get('DST_USER', None)
#DST_PASSWORD = environ.get('DST_PASSWORD', None)
dst_auth = ('centralsupport-ai-service@versata.com', 'relay-z+#Rwd3JLBGE8uP')
