import json
import requests
import os
from settings import SOURCE_HC_URL, DESTINATION_HC_URL, auth
authd = requests.auth.HTTPBasicAuth(*auth)
headers = {
    'Content-Type': 'application/json',
}

helpcenter = requests.Session()
authd(helpcenter)


def make_source_url(*args):
    url_parts = map(lambda x: str(x) if x else '', args)
    return "/".join([SOURCE_HC_URL, *url_parts])


def make_destination_url(*args):
    url_parts = map(lambda x: str(x) if x else '', args)
    return "/".join([DESTINATION_HC_URL, *url_parts])


def page_response(response, key):
    response = response.json()
    next_url = response.get('next_page', None)
    data = response[key]
    while next_url:
        response = helpcenter.get(next_url).json()
        data = data + response[key]
        next_url = response.get('next_page', None)

    return data


def get(data_key, url):
    response = helpcenter.get(url)
    return page_response(response, data_key)


def save_to_file(obj, filename):
    with open('data/%s.json' % filename, 'w+') as f:
        f.write(json.dumps(obj))


def load_from_file(filename):
    with open(f'data/{filename}.json') as f:
        return json.loads(f.read())


def download(url, filename):
    get_response = helpcenter.get(url, stream=True)
    filename = 'data/attachments/%s' % filename
    path = os.path.dirname(filename)
    os.makedirs(path, exist_ok=True)

    with open(filename, 'wb') as f:
        for chunk in get_response.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)


def get_articles_attachments():

    articles = load_from_file('articles')
    for article in articles:
        article_id = article['id']
        url = make_source_url('articles',
                              str(article_id), 'attachments')
        attachments = get('article_attachments', url)
        for attachment in attachments:
            url = attachment['content_url']
            filename = attachment['file_name']
            download(url, f'{str(article_id)}/{filename}')


def dump_source_helpcenter():
    url = make_source_url
    articles = get('articles', url('articles'))
    categories = get('categories', url('categories'))
    sections = get('sections', url('sections'))
    user_segments = get('user_segments', url('user_segments'))
    save_to_file(articles, 'articles')
    save_to_file(categories, 'categories')
    save_to_file(sections, 'sections')
    save_to_file(user_segments, 'user_segments')


def map_source_destination(data, field_name, mapping, default_value):
    current_value = str(data[field_name])
    new_value = mapping.get(current_value, default_value)
    data[field_name] = new_value
    return data


def inject_category_id(data):
    sections = load_from_file('sections')
    for section in sections:
        if section['id'] == data['section_id']:
            data['section_id'] = section['category_id']
            return data
    data['section_id'] = None
    return data


def remove_keys(data, keys):
    for key in keys:
        data.pop(key)
    return data


def prepare_articles_for_migration():
    dump_source_helpcenter()
    user_segments_mapping = {'360000790354': '360000985254',
                             '360000788034': '360000985234'}
    default_user_segment = '360000985254'

    categories_mapping = {'360001386453': '360003516014',  # implementation
                          '360001380034': '360003565573',  # Merchandising
                          '360001386493': '360003516034',  # Reporting
                          '360001386473': '360003565573'  # announcements
                          }

    articles = load_from_file('articles')
    articles = [map_source_destination(
        article, 'user_segment_id', user_segments_mapping, default_user_segment) for article in articles]

    articles = [inject_category_id(article) for article in articles]

    articles = [map_source_destination(
        article, 'section_id', categories_mapping, None) for article in articles]
    # cleanup unused keys
    keys = ['url', 'html_url', 'author_id', 'created_at',
            'updated_at', 'edited_at', 'permission_group_id']
    articles = [remove_keys(article, keys) for article in articles]
    save_to_file(articles, 'articles_for_migration')


def migrate_articles():
    articles = load_from_file('articles_for_migration')
    mapping = {}
    for article in articles:
        url = make_destination_url(
            'sections', article['section_id'], 'articles')
        article.pop('section_id')
        response = helpcenter.post(url, json={'article': article})
        new_id = response.json()['article']['id']
        mapping.update({str(article['id']): str(new_id)})
    save_to_file(mapping, 'migrated_articles_mapping')


def migrate_attachments():
    pass


if __name__ == '__main__':
    # get_articles_attachments()
    # prepare_articles_for_migration()
    # migrate_articles()
