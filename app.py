import json
import requests
import os
import re
from settings import (SOURCE_HC_URL,
                      DESTINATION_HC_URL,
                      CROSSREF_ARTICLE_DESTINATION,
                      CROSSREF_ARTICLE_SOURCE,
                      dst_auth, src_auth)

dst_auth = requests.auth.HTTPBasicAuth(*dst_auth)
src_auth = requests.auth.HTTPBasicAuth(*src_auth)
headers = {
    'Content-Type': 'application/json',
}

dst_helpcenter = requests.Session()
src_helpcenter = requests.Session()

dst_auth(dst_helpcenter)
src_auth(src_helpcenter)


def make_source_url(*args):
    url_parts = map(lambda x: str(x) if x else '', args)
    return "/".join([SOURCE_HC_URL, *url_parts])


def make_destination_url(*args):
    url_parts = map(lambda x: str(x) if x else '', args)
    return "/".join([DESTINATION_HC_URL, *url_parts])


def page_response(helpcenter, response, key):
    response = response.json()
    next_url = response.get('next_page', None)
    data = response[key]
    while next_url:
        response = helpcenter.get(next_url).json()
        data = data + response[key]
        next_url = response.get('next_page', None)

    return data


def get(helpcenter, data_key, url):
    response = helpcenter.get(url)
    return page_response(helpcenter, response, data_key)


def save_to_file(obj, filename):
    with open('data/%s.json' % filename, 'w') as f:
        f.write(json.dumps(obj))


def load_from_file(filename):
    with open(f'data/{filename}.json') as f:
        return json.loads(f.read())


def download(url, filename):
    get_response = src_helpcenter.get(url, stream=True)
    filename = 'data/attachments/%s' % filename
    path = os.path.dirname(filename)
    os.makedirs(path, exist_ok=True)

    with open(filename, 'wb') as f:
        for chunk in get_response.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)


def get_articles_attachments():
    downloaded_attachments = {}
    articles = load_from_file('articles')
    for article in articles:
        article_id = article['id']
        downloaded_attachments.update({article_id: []})
        url = make_source_url('articles',
                              str(article_id), 'attachments')
        attachments = get(src_helpcenter, 'article_attachments', url)
        for attachment in attachments:

            url = attachment['content_url']
            filename = attachment['file_name']
            downloaded_attachments[article_id].append(
                {'filename': filename, 'url': url})
            print(f'downloading {filename}...')
            download(url, f'{str(article_id)}/{filename}')
    save_to_file(downloaded_attachments, 'downloaded_attachments')


def dump_source_helpcenter():
    url = make_source_url
    print('Downloading articles...')
    articles = get(src_helpcenter, 'articles', url('articles'))
    print('Downloading categories...')
    categories = get(src_helpcenter, 'categories', url('categories'))
    print('Downloading sections...')
    sections = get(src_helpcenter, 'sections', url('sections'))

    save_to_file(articles, 'articles')
    save_to_file(categories, 'categories')
    save_to_file(sections, 'sections')


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
    user_segments_mapping = {'360000790354': '360000535154',  # '360000084993',  # Project Rural - Public Articles // signedin
                             # '360000084973'}  # Project Rural - Internal Articles //staff
                             '360000788034': '360000535134'}
    default_user_segment = '360000535154'  # 360000985254'

    categories_mapping = {'360001386453':  '360003516014',  # 360003515354',  # implementation
                          '360001380034': '360003565553',  # '360003564573',  # Merchandising
                          '360001386493':  '360003516034',  # '360003515394',  # Reporting
                          '360001386473': '360003565573'  # '360003515374'  # announcements
                          }

    articles = load_from_file('articles')
    articles = [map_source_destination(
        article, 'user_segment_id', user_segments_mapping, default_user_segment) for article in articles]

    articles = [inject_category_id(article) for article in articles]

    articles = [map_source_destination(
        article, 'section_id', categories_mapping, None) for article in articles]
    # cleanup unused keys
    keys = ['url', 'html_url', 'author_id', 'permission_group_id']
    articles = [remove_keys(article, keys) for article in articles]
    save_to_file(articles, 'articles_for_migration')


def migrate_articles():
    print('Starting migration ...')
    articles = load_from_file('articles_for_migration')
    mapping = {}
    for article in articles:
        print(f'Migrating {article["id"]} ...')
        url = make_destination_url(
            'sections', article['section_id'], 'articles')
        article.pop('section_id')
        response = dst_helpcenter.post(url, json={'article': article})
        new_id = response.json()['article']['id']
        mapping.update({str(article['id']): str(new_id)})
    save_to_file(mapping, 'migrated_articles_mapping')


def delete_all_destination_articles():
    url = make_destination_url('articles')
    articles = get(dst_helpcenter, 'articles', url)
    print(f'Deleting {len(articles)} articles')
    for article in articles:
        print(f'Deleting article {article["id"]}...')
        dst_helpcenter.delete(make_destination_url('articles',  article['id']))
    print('Done.')


def upload_file(filename):
    url = make_destination_url('articles', 'attachments')
    return dst_helpcenter.post(url, data={'inline': True}, files={'file': open(filename, 'rb')})


def migrate_attachments():
    downloaded_attachments = load_from_file('downloaded_attachments')
    migrated_articles_mapping = load_from_file('migrated_articles_mapping')
    uploaded_attachments = {}
    for article_id, attachments in downloaded_attachments.items():
        mapped_id = migrated_articles_mapping[article_id]
        uploaded_attachments.update({mapped_id: []})
        for attachment in attachments:
            print(f'uploading {attachment}...')
            response = upload_file(
                f'data/attachments/{article_id}/{attachment["filename"]}')
            attachment_url = response.json(
            )['article_attachment']['content_url']
            attachment_id = response.json(
            )['article_attachment']['id']
            uploaded_attachments[mapped_id].append(
                {'id': attachment_id, 'old_url': attachment['url'], 'new_url': attachment_url})
    save_to_file(uploaded_attachments, 'uploaded_attachments')


def fix_attachments_links():

    uploaded_attachments = load_from_file('uploaded_attachments')
    articles = load_from_file('articles')
    migrated_articles_mapping = load_from_file('migrated_articles_mapping')

    articles_to_update = {}
    for article in articles:
        body = article['body']
        new_id = migrated_articles_mapping[str(article['id'])]
        articles_to_update.update({new_id: {'body': body, 'attachments': []}})
        attachments = uploaded_attachments[new_id]
        for attachment in attachments:
            attachment_id = attachment['id']
            old_url = attachment['old_url']
            new_url = attachment['new_url']
            body = body.replace(old_url, new_url)
            articles_to_update[new_id]['attachments'].append(attachment_id)
        articles_to_update[new_id]['body'] = body
    save_to_file(articles_to_update, 'articles_attachments_fix')


def apply_fix():
    articles_attachments_fix = load_from_file('articles_attachments_fix')
    for article_id, payload in articles_attachments_fix.items():
        if len(payload['attachments']) > 0:
            print(f'Applying fix to {article_id}...')
            url = make_destination_url(
                'articles', article_id, 'translations', 'en-us')
            response = dst_helpcenter.put(
                url, json={'translation': {'body': payload['body']}})
            if response.status_code == 200:
                print('Fixed.')
            else:
                print('Error.')
            url = make_destination_url(
                'articles', article_id, 'bulk_attachments')
            response = dst_helpcenter.post(
                url, json={"attachment_ids": payload['attachments']})
            if response.status_code == 200:
                print('Fixed.')
            else:
                print('Error.')


def search_cross_reference_links():
    migrated_articles_mapping = load_from_file('migrated_articles_mapping')
    url = make_destination_url('articles')
    articles = get(dst_helpcenter, 'articles', url)
    update_list = []
    for article in articles:
        crossref_links = re.findall(
            r'(?<='+CROSSREF_ARTICLE_SOURCE+').+?(?=\")', article['body'])
        body = article['body']
        for refid in crossref_links:
            new_id = migrated_articles_mapping.get(refid, None)
            if new_id:
                old_link = f'{CROSSREF_ARTICLE_SOURCE}{refid}'
                new_link = f'{CROSSREF_ARTICLE_DESTINATION}{new_id}'
                body = body.replace(old_link, new_link)

                print(
                    f'{article["id"]}\t\nChanged:\nFrom:{old_link}\nTo:{new_link}')
            else:
                print(
                    f'{article["id"]}\t\nError:\nCould not find migrated article for id {refid}')
        if body != article['body']:
            update_list.append({'id': refid, 'body': article['body']})
    return update_list


def fix_cross_reference_links():
    update_list = search_cross_reference_links()
    for article in update_list:
        url = make_destination_url(
            'articles', article['id'], 'translations', 'en-us')
        response = dst_helpcenter.put(
            url, json={'translation': {'body': article['body']}})
        if response.status_code == 200:
            print(f'Crossreference links updated for {article["id"]}')


if __name__ == '__main__':
    # delete_all_destination_articles()
    dump_source_helpcenter()
    get_articles_attachments()
    prepare_articles_for_migration()
    migrate_articles()
    migrate_attachments()
    fix_attachments_links()
    apply_fix()
    fix_cross_reference_links()
