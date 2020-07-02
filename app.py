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
    print(url)
    response = helpcenter.get(url)
    print(response)
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
    articles = get(src_helpcenter, 'articles', url('categories','360001122813','articles')) # TODO hardcoded string
    print('Downloading categories...')
    categories = get(src_helpcenter, 'categories', url('categories'))
    print('Downloading sections...')
    sections = get(src_helpcenter, 'sections', url('sections'))

    categories = list(filter(lambda c: c['id'] in [360001122813], categories)) # TODO hardcoded string
    sections = list(filter(lambda s: s['category_id'] in list(map(lambda c: c['id'], categories)), sections))
    articles = list(filter(lambda a: a['section_id'] in list(map(lambda s: s['id'],sections)) , articles))
    save_to_file(categories, 'categories')
    save_to_file(sections, 'sections')
    save_to_file(articles, 'articles')



def map_source_destination(data, field_name, mapping, default_value):
    current_value = str(data[field_name])
    new_value = mapping.get(current_value, default_value)
    print(new_value)
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
    user_segments_mapping = {'360000084973': '360000084993',  # '360000084993',  # Project Rural - Public Articles // signedin
                             # '360000084973'}  # Project Rural - Internal Articles //staff
                             '360000084993': '360000084993'}
    default_user_segment = "" #'360000535154'  # 360000985254'


    print('Downloading categories...')
    dst_categories = get(dst_helpcenter, 'categories', make_destination_url('categories'))
    print('Downloading sections...')
    dst_sections = get(dst_helpcenter, 'sections', make_destination_url('sections'))

    src_categories = load_from_file('categories')
    src_sections = load_from_file('sections')

    categories_mapping = {}
    for src_cat in src_categories:
        dst_category_id = False
        for dst_cat in dst_categories:
            if dst_cat['name'] == src_cat['name']:
                dst_category_id = dst_cat['id']
                break
        if not(dst_category_id):
            url = make_destination_url('categories')
            response = dst_helpcenter.post(url, json={'category': src_cat})
            dst_category_id = response.json()['category']['id']

        for src_sec in src_sections:
            if(src_sec['category_id'] != src_cat['id']):
                continue
            else:
                is_section_mapped = False
                for dst_sec in dst_sections:
                    if(dst_sec['category_id'] != dst_category_id):
                        continue
                    else:
                        if dst_sec['name'] == src_sec['name']:
                            categories_mapping[str(src_sec['id'])] = dst_sec['id']
                            is_section_mapped = True
                            break
                if(not(is_section_mapped)):
                    url = make_destination_url('categories', dst_category_id, 'sections')
                    src_sec['category_id'] = dst_category_id
                    src_sec['parent_section_id'] = None # TODO check how to handle parent_section_id
                    response = dst_helpcenter.post(url, json={'section': src_sec})
                    dst_section_id = response.json()['section']['id']
                    categories_mapping[str(src_sec['id'])] = dst_section_id


#     categories_mapping = {
# '360003474374': 360003810559,
# '360003517214': 360003810259,
# '360003520413': 360003765540,
# '360003520473': 360003765400,
# '360003515374': 360003765280,
# '360003474394': 360003765480,
# '360003521733': 360003810479,
# '360003567093': 360003810439,
# '360003474414': 360003765460,
# '360003474434': 360003810459,
# '360003516954': 360003765260,
# '360003517014': 360003765240,
# '360003474454': 360003765380,
# '360003474754': 360003765440,
# '360003516894': 360003810379,
# '360003521813': 360003765640,
# '360003521873': 360003765360,
# '360003516874': 360003765420,
# '360003527933': 360003810339,
# '360003474594': 360003765300,
# '360003515354': 360003765340,
# '360003567393': 360003765180,
# '360003521893': 360003765600,
# '360003474654': 360003765520,
# '360003516914': 360003810319,
# '360003521913': 360003765580,
# '360003517054': 360003810299,
# '360003564573': 360003810419,
# '360003521933': 360003765660,
# '360003521953': 360003765620,
# '360003521853': 360003810539,
# '360003711199': 360003810199,
# '360003521993': 360003810499,
# '360003522033': 360003765720,
# '360003474694': 360003765560,
# '360003522053': 360003765680,
# '360003515394': 360003765500,
# '360003522073': 360003810359,
# '360003474734': 360003765740,
# '360003522093': 360003810519,
# '360003517074': 360003810279,
# '360003367380': 360003810219,
# '360002996920': 360003810239,
# '360003006480': 360003765320,
# '360003079179': 360003810399,
# '360003522113': 360003765760,
# '360003474774': 360003765700,
# '360003567333': 360003765220,
# '360003567353': 360003765200,
# '360003757899': 360003765160,
# '360003522153': 360003810579
#
#                           }

    articles = load_from_file('articles')
    #articles = [map_source_destination(
    #    article, 'user_segment_id', user_segments_mapping, default_user_segment) for article in articles]

    #articles = [inject_category_id(article) for article in articles]

    articles = [map_source_destination(
        article, 'section_id', categories_mapping, None) for article in articles]
    # cleanup unused keys
    keys = ['url', 'html_url', 'author_id']#, 'permission_group_id']
    articles = [remove_keys(article, keys) for article in articles]
    save_to_file(articles, 'articles_for_migration')


def migrate_articles():
    print('Starting migration ...')
    articles = load_from_file('articles_for_migration')
    mapping = {}
    errors = []
    count=0
    try:
        for article in articles:
            count+=1
            print(f'Migrating {article["id"]} ...')
            print(str(count) + ' from ' + str(len(articles)))
            url = make_destination_url(
                'sections', article['section_id'], 'articles')
            article.pop('section_id')

            try:
                response = dst_helpcenter.post(url, json={'article': article})
                new_id = response.json()['article']['id']
                mapping.update({str(article['id']): str(new_id)})
            except Exception as e:
                errors.append(str(article['id'])+" "+ response.reason + " " + str(e))
        save_to_file(mapping, 'migrated_articles_mapping')
        save_to_file(errors, 'migrated_articles_mapping_errors')
    except Exception  as e:
        print(e)
        save_to_file(mapping, 'migrated_articles_mapping_error_backup')
        save_to_file(errors, 'migrated_articles_mapping_errors')
        quit()


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

    already_uploaded_attachments = []
    try:
        uploaded_attachments = load_from_file('uploaded_attachments_error_backup')
        for article_id, attachments in uploaded_attachments.items():
            for attachment in attachments:
                already_uploaded_attachments.append(attachment['old_url'])
                already_uploaded_attachments.append('https://support.gfi.com/hc/article_attachments/360004297139/Screen_Shot_2019-08-27_at_4.04.37_PM.png')

    except Exception as e:
        uploaded_attachments = {}

    errors = []
    try:
        for article_id, attachments in downloaded_attachments.items():

            if article_id not in migrated_articles_mapping:
                # probably an error from last phase, will add to the logs and continue
                errors.append("article " + str(article_id) + " " + " not found in migrated articles")
                continue
            mapped_id = migrated_articles_mapping[article_id]
            if mapped_id not in uploaded_attachments:
                uploaded_attachments.update({mapped_id: []})

            for attachment in attachments:
                try:
                    if(attachment['url'] in already_uploaded_attachments):
                        # check backup and skip attachment if it was already uploaded
                        continue
                    print(f'uploading {attachment}...')


                    response = upload_file(
                        f'data/attachments/{article_id}/{attachment["filename"]}')
                    attachment_url = response.json(
                    )['article_attachment']['content_url']
                    attachment_id = response.json(
                    )['article_attachment']['id']
                    uploaded_attachments[mapped_id].append(
                        {'id': attachment_id, 'old_url': attachment['url'], 'new_url': attachment_url})
                except Exception as e:
                    errors.append(str(article_id) + " " + response.reason + " " + str(e))
        save_to_file(uploaded_attachments, 'uploaded_attachments')
        save_to_file(errors, 'migrated_articles_mapping_errors')
    except Exception  as e:
        print(e)
        save_to_file(uploaded_attachments, 'uploaded_attachments_error_backup')
        save_to_file(errors, 'migrated_articles_mapping_errors')
        quit()


def fix_attachments_links():

    uploaded_attachments = load_from_file('uploaded_attachments')
    articles = load_from_file('articles')
    migrated_articles_mapping = load_from_file('migrated_articles_mapping')

    articles_to_update = {}
    for article in articles:
        body = article['body']

        if str(article['id']) not in migrated_articles_mapping:
            # missing due error in last phase
            continue
        new_id = migrated_articles_mapping[str(article['id'])]
        articles_to_update.update({new_id: {'body': body, 'attachments': []}})

        if new_id not in uploaded_attachments:
            # missing due error in last phase
            continue
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
        for crossref_source in CROSSREF_ARTICLE_SOURCE:
            if not article['body']:
                continue
            crossref_links = re.findall(
                r'(?<='+crossref_source+').+?(?=\"|-|/)', article['body'])
            body = article['body']
            for refid in crossref_links:
                new_id = migrated_articles_mapping.get(refid, None)
                if new_id:
                    old_link = f'{crossref_source}{refid}'
                    new_link = f'{CROSSREF_ARTICLE_DESTINATION}{new_id}'
                    body = body.replace(old_link, new_link)

                    print(
                        f'{article["id"]}\t\nChanged:\nFrom:{old_link}\nTo:{new_link}')
                else:
                    print(
                        f'{article["id"]}\t\nError:\nCould not find migrated article for id {refid}')
            if body != article['body']:
                update_list.append({'id': article['id'], 'body': body})
    return update_list


def fix_cross_reference_links():
    print('fix_cross_reference_links')
    update_list = search_cross_reference_links()
    for article in update_list:
        url = make_destination_url(
            'articles', article['id'], 'translations', 'en-us') 
        print('updating article with url' + url)
        response = dst_helpcenter.put(
            url, json={'translation': {'body': article['body']}})
        if response.status_code == 200:
            print(f'Crossreference links updated for {article["id"]}')
        else:
            print(f'FAIL fixing Crossreference links for {article["id"]}')


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
