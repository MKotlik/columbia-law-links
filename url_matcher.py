import requests
import csv
from pprint import pprint

ERRORS_LIST_FILENAME = 'www-law-columbia-edu_20170522T210719Z_CrawlErrors.csv'


def process_errors(errors_filename, start=0, end=None):
    print "Setting hosts file to point to new server"
    set_redirect(False)
    errors_list = compare_with_new(errors_filename, start, end)
    print "Setting hosts file to point to old server"
    set_redirect(True)
    errors_list = catch_old_404s(errors_filename, start, end)
    return errors_list[start:end]


def catch_old_404s(errors_filename, start=0, end=None):
    errors_list = get_errors_list(errors_filename)
    if end is None:
        end = len(errors_list)
    for error in errors_list[start:end]:
        if error['newServerCode'] != 200:
            resp = requests.get(error['url'])
            error['oldServerCode'] = resp.status_code
            if resp.status_code == 404:
                error['searchStatus'] = 'deadPage'
            else:
                error['searchStatus'] = 'onOld'
    return errors_list[start:end]


def compare_with_new(errors_filename, start=0, end=None):
    errors_list = get_errors_list(errors_filename)
    if end is None:
        end = len(errors_list)
    for error in errors_list[start:end]:
        resp = requests.get(error['url'])
        error['newServerCode'] = resp.status_code
        if resp.status_code == 200:
            print 'FOUND REDIRECTED PAGE: ' + error['url']
            error['searchStatus'] = 'alreadyRedirected'
        else:
            error['searchStatus'] = 'notOnNew'
    return errors_list[start:end]


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


def set_redirect(bool):
    hosts_rule = '128.59.176.155   www.law.columbia.edu'
    if bool is True:  # Add rule to hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] == hosts_rule:
            print "Hosts file already set for old server"
        else:
            with open('/etc/hosts', 'a') as hosts_file:
                hosts_file.write(hosts_rule)
    else:  # Remove rule from hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] != hosts_rule:
            print "Hosts file already set for new server"
        else:
            with open('/etc/hosts', 'w') as hosts_file:
                for line in hosts_lines[:-1]:
                    hosts_file.write(line)


if __name__ == "__main__":
    pprint(process_errors(ERRORS_LIST_FILENAME, 0, 10))
