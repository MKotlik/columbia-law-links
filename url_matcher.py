import requests
from requests.exceptions import TooManyRedirects
import csv
import time
import sys
from bs4 import BeautifulSoup
from pprint import pprint

# TODO: add timeouts to limit how long this takes
# TODO: add title field to errors to prevent double-scraping?

ERRORS_LIST_FILENAME = 'www-law-columbia-edu_20170522T210719Z_CrawlErrors.csv'


def timed_process_errors(errors_filename, start=0, end=None):
    print "======== BEGIN PROCESSING LINK ERRORS ========"
    time_start = time.time()
    print "TIME AT START: " + str(time_start)
    result = process_errors(errors_filename, start, end)
    print "======== END PROCESSING LINK ERRORS ========"
    time_end = time.time()
    print "TIME AT END: " + str(time_end)
    print "TIME TAKEN: " + str(round(time_end - time_start)) + "ms"
    return result


def process_errors(errors_filename, start=0, end=None):
    errors_list = get_errors_list(errors_filename)
    if end is None:
        end = len(errors_list)
    print "Length of errors_list: " + str(len(errors_list))
    print "Starting index: " + str(start) + "; Ending index: " + str(end)
    errors_list = ignore_downloads(errors_list, start, end)
    print "HOSTS: Setting hosts file to point to new server"
    set_redirect(False)
    errors_list = check_new_redirects(errors_list, start, end)
    print "HOSTS: Setting hosts file to point to old server"
    set_redirect(True)
    errors_list = parse_old_pages(errors_list, start, end)
    # Cleanup
    print "HOSTS: Resetting hosts file to point to new server"
    set_redirect(False)
    return errors_list[start:end]


def parse_old_pages(errors_list, start=0, end=None):
    # NOTE: combined with title scraper, since Soup-ing twice is inefficient
    for error in errors_list[start:end]:
        if error['searchStatus'] == 'check':
            try:
                resp = requests.get(error['url'])
                error['oldServerCode'] = resp.status_code
                # DEBUG
                # print "Url: " + resp.url + '; Code: ' + str(resp.status_code)
                if resp.status_code == 404:
                    error['searchStatus'] = 'deadPage'
                elif resp.status_code == 500:
                    error['searchStatus'] = 'serverError'
                else:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    title = soup.find('title')
                    if title is not None:
                        title = title.text.lower()
                        if '404' in title:
                            # DEBUG PRINT STATEMENT FOR 404 TITLES
                            print 'FOUND TITLE 404 PAGE: ' + error['url']
                            error['old404Redirect'] = True
                            error['searchStatus'] = 'deadPage'
                        elif 'login' in title or 'sign in' in title:
                            # DEBUG PRINT STATEMENT FOR LOGIN TITLES
                            print 'FOUND TITLE LOGIN PAGE: ' + error['url']
                            error['searchStatus'] = 'needsLogin'
                        else:
                            heading = parse_title(title)
                            if heading is not None:
                                error['pageName'] = heading
            except TooManyRedirects as e:
                error['searchStatus'] = 'redirectsError'
                print "TOO MANY REDIRECTS ERROR for " + error['url']
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                error['searchStatus'] = 'unknownOldRequestError'
                print 'CAUGHT UNKNOWN ERROR WHILE QUERYING OLD SERVER'
                for item in sys.exc_info():
                    print item
                print 'CONTINUING'
        # Completion DEBUG
        print 'Parsed old: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list


def check_new_redirects(errors_list, start=0, end=None):
    for error in errors_list[start:end]:
        if error['searchStatus'] == 'check':
            try:
                resp = requests.get(error['url'])
                error['newServerCode'] = resp.status_code
                if resp.status_code == 200:
                    # DEBUG PRINT STATEMENT FOR REDIRECTED PAGES
                    print 'FOUND REDIRECTED PAGE: ' + error['url']
                    error['searchStatus'] = 'alreadyRedirected'
            except TooManyRedirects as e:
                print "TOO MANY REDIRECTS ERROR for " + error['url']
                error['searchStatus'] = 'newServerRedirectsError'
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                error['searchStatus'] = 'unknownNewRequestError'
                print 'CAUGHT UNKNOWN ERROR WHILE QUERYING NEW SERVER'
                for item in sys.exc_info():
                    print item
                print 'CONTINUING'
        # Completion DEBUG
        print 'Parsed new: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list


def ignore_downloads(errors_list, start=0, end=None):
    for error in errors_list[start:end]:
        has_null = error['url'].startswith('http://www.law.columbia.edu/null')
        if has_null or 'filemgr' in error['url']:
            error['searchStatus'] = 'ignoredDwnld'
    return errors_list


def get_possible_matches(errors_filename, start=0, end=None):
    pass


def parse_title(page_title):
    if '|' in page_title:
        title_parts = page_title.split('|')
    elif ':' in page_title:
        title_parts = page_title.split(':')
    else:
        title_parts = [page_title]
    heading = None
    for part in title_parts:
        part = part.strip().lower()
        if part != 'columbia law school' and part != 'event':
            heading = part
    return heading


def get_errors_list(errors_filename):
    errors_list = []
    with open(errors_filename, 'rb') as errors_csv:
        error_reader = csv.DictReader(errors_csv)
        for row in error_reader:
            errors_list.append({'url': row['URL'],
                                'lastCrawled': row['Last crawled'],
                                'origCode': row['Response Code'],
                                'oldServerCode': None,
                                'old404Redirect': False,
                                'newServerCode': None,
                                'searchStatus': 'check',
                                'pageName': None,
                                'possibleUrls': []})
    return errors_list


def set_redirect(bool):
    hosts_rule = '128.59.176.155   www.law.columbia.edu'
    if bool is True:  # Add rule to hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] == hosts_rule:
            print "HOSTS: Hosts file already set for old server"
        else:
            with open('/etc/hosts', 'a') as hosts_file:
                hosts_file.write(hosts_rule)
    else:  # Remove rule from hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] != hosts_rule:
            print "HOSTS: Hosts file already set for new server"
        else:
            with open('/etc/hosts', 'w') as hosts_file:
                for line in hosts_lines[:-1]:
                    hosts_file.write(line)


def timer(method):
    def wrapper(*args, **kw):
        startTime = int(round(time.time() * 1000))
        result = method(*args, **kw)
        endTime = int(round(time.time() * 1000))

        print(endTime - startTime, 'ms')
        return result

    return wrapper


if __name__ == "__main__":
    pprint(process_errors(ERRORS_LIST_FILENAME, 0, 10))
