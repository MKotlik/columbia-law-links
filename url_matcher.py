import requests
import csv
from pprint import pprint

ERRORS_LIST_FILENAME = 'www-law-columbia-edu_20170522T210719Z_CrawlErrors.csv'


def process_errors(errors_filename, start=0, end=None):
    errors_list = catch_old_404s(errors_filename, start, end)
    return errors_list[start:end]


def catch_old_404s(errors_filename, start=0, end=None):
    errors_list = get_errors_list(errors_filename)
    if end is None:
        end = len(errors_list)
    for error in errors_list[start:end]:
        resp = requests.get(error['url'])
        error['oldServerCode'] = resp.status_code
        if resp.status_code == 404:
            error['searchStatus'] = 'deadPage'
    return errors_list[start:end]


def compare_with_new(errors_filename, start=0, end=None):
    pass


def scrape_headings(errors_filename, start=0, end=None):
    pass


def get_possible_matches(errors_filename, start=0, end=None):
    pass


def get_errors_list(errors_filename):
    errors_list = []
    with open(errors_filename, 'rb') as errors_csv:
        error_reader = csv.DictReader(errors_csv)
        for row in error_reader:
            errors_list.append({'url': row['URL'],
                                'lastCrawled': row['Last crawled'],
                                'origCode': row['Response Code'],
                                'oldServerCode': None,
                                'newServerCode': None,
                                'searchStatus': 'unchecked',
                                'possibleUrls': []})
    return errors_list


pprint(process_errors(ERRORS_LIST_FILENAME, 0, 10))
# # resp = requests.get('http://web.law.columbia.edu')
# resp = requests.get('http://www.law.columbia.edu/academics/curriculum')
# print resp.status_code
# pprint(resp.text)
