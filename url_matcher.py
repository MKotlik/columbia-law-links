import requests
from requests.exceptions import TooManyRedirects
import csv
import time
import sys
import json
from bs4 import BeautifulSoup
from pprint import pprint
import searcher

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
    print "LENGTH OF errors_list: " + str(len(errors_list))
    print "STARTING INDEX: " + str(start) + "; ENDING INDEX: " + str(end)
    print "---Checking for download links---"
    errors_list = ignore_downloads(errors_list, start, end)
    print "---Checking for already redirected pages---"
    print "HOSTS: Setting hosts file to point to new server"
    set_redirect(False)
    errors_list = check_new_redirects(errors_list, start, end)
    print "---Analyzing pages on old server---"
    print "HOSTS: Setting hosts file to point to old server"
    set_redirect(True)
    errors_list = parse_old_pages(errors_list, start, end)
    print "---Searching new server for possible matches---"
    print "HOSTS: Setting hosts file to point to new server"
    set_redirect(True)
    errors_list = get_possible_matches(errors_list, start, end)
    # Cleanup
    print "---Cleaning up---"
    print "HOSTS: Resetting hosts file to point to new server"
    set_redirect(False)
    return errors_list[start:end]


def analyze_results(results):
    ignored = [er for er in results if er['searchStatus'] == 'ignoredDwnld']
    done = [er for er in results if er['searchStatus'] == 'alreadyRedirected']
    dead_pages = [er for er in results if er['searchStatus'] == 'deadPage']
    redirected = [er for er in results if er['searchStatus'] == 'serverRedirect']
    server_500 = [er for er in results if er['searchStatus'] == 'serverError']
    redirects = [er for er in results if er['searchStatus'] == 'redirectsError']
    new_redirects = [er for er in results if er['searchStatus'] == 'newServerRedirectsError']
    new_unknown = [er for er in results if er['searchStatus'] == 'unknownNewRequestError']
    old_unknown = [er for er in results if er['searchStatus'] == 'unknownOldRequestError']
    need_login = [er for er in results if er['searchStatus'] == 'needsLogin']
    check = [er for er in results if er['searchStatus'] == 'check']
    short_name = [er for er in results if er['searchStatus'] == 'shortName']
    found_name = [er for er in results if er['searchStatus'] == 'foundName']
    no_matches = [er for er in results if er['searchStatus'] == 'noMatches']
    matched = [er for er in results if er['searchStatus'] == 'matched']
    report = []
    report.append('===== ANALYSIS OF PROCESSED ERRORS =====')
    report.append("Length of Errors List: " + str(len(results)))
    report.append('Number of ignored downloads: ' + str(len(ignored)))
    report.append('Number of already redirected pages: ' + str(len(done)))
    report.append('Number of pages dead on old server: ' + str(len(dead_pages)))
    report.append('Number of pages giving error 500 on old server: ' + str(len(server_500)))
    report.append('Number of pages redirecting on old server: ' + str(len(redirected)))
    report.append('Number of pages giving redirection errors on old server: ' + str(len(redirects)))
    report.append('Number of pages giving redirection errors on new server: ' + str(len(new_redirects)))
    report.append('Number of pages giving unknown errors on old server: ' + str(len(old_unknown)))
    report.append('Number of pages giving unknown errors on new server: ' + str(len(new_unknown)))
    report.append('Number of pages needing login on old server: ' + str(len(need_login)))
    report.append('Number of pages with one-word titles: ' + str(len(short_name)))
    report.append('Number of pages with matcheable names: ' + str(len(found_name)))
    report.append('Number of pages requiring hand matching: ' + str(len(check)))
    report.append('Number of pages with no matches: ' + str(len(no_matches)))
    report.append('Number of pages that have been matched: ' + str(len(matched)))
    report.append('===== END ANALYSIS OF PROCESSED ERRORS =====')
    report_str = "\n".join(report)
    analysis = {'results': results, 'ignored': ignored, 'done': done,
                'dead_pages': dead_pages, 'server_errors': server_500,
                'old_redirects': redirects, 'new_redirects': new_redirects,
                'redirected': redirected, 'new_unknown_errors': new_unknown,
                'old_unknown_errors': old_unknown, 'need_login': need_login,
                'short_names': short_name, 'found_name': found_name,
                'no_matches': no_matches, 'matched': matched,
                'check': check, 'report': report_str}
    print report_str
    return analysis


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
                elif resp.status_code == 302 or resp.status_code == 301:
                    error['searchStatus'] = 'serverRedirect'
                elif resp.status_code == 500:
                    error['searchStatus'] = 'serverError'
                else:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    title = soup.find('title')
                    pre_404 = soup.find('pre')
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
                            heading, full_heading = parse_title(title)
                            if heading is not None:
                                if ' ' not in heading:
                                    # If name is one word, mark and hand check
                                    error['searchStatus'] = 'shortName'
                                else:
                                    # Mark that probable name was found
                                    error['searchStatus'] = 'foundName'
                                # Always set name to whatever was found
                                error['pageName'] = heading
                                error['fullName'] = full_heading
                    elif pre is not None:
                        if '404' in pre.text:
                            # DEBUG PRINT STATEMENT FOR 404 TITLES
                            print 'FOUND TITLE 404 PAGE: ' + error['url']
                            error['old404Redirect'] = True
                            error['searchStatus'] = 'deadPage'
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


def get_possible_matches(errors_list, start=0, end=None):
    if end is None:
        end = len(errors_list)
    api_key = searcher.load_config()
    cse_id = "013164244572636035941:csl0bhjaaa4"
    base_url = searcher.get_base_url(api_key, cse_id)
    for error in errors_list[start:end]:
        if error['searchStatus'] == 'foundName':
            matches = searcher.search(base_url, error['pageName'])
            if matches is None:
                break
            elif len(matches) == 0:
                error['searchStatus'] = 'noMatches'
            else:
                error['possibleUrls'] = matches[0:10]
                error['searchStatus'] = 'matched'
        print 'Searched for: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list

def parse_title(page_title):
    # Return tuple of first element of title and string of all title parts
    if '|' in page_title:
        title_parts = page_title.split('|')
    elif ':' in page_title:
        title_parts = page_title.split(':')
    else:
        title_parts = [page_title]
    heading = None
    full_heading = []
    for part in title_parts:
        part = part.strip().lower()
        if part != 'columbia law school' and part != 'event':
            full_heading.append(part)
            # First element of title is most likely name, so use only that
            if heading is None:
                heading = part
    return (heading, ' '.join(full_heading))


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
                                'fullName': None,
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


def save_results(errors_list, start, end):
    filename = 'proccesed_errors_' + str(start) + '-' + str(end) + '.json'
    with open(filename, 'w') as errors_file:
        json.dump(errors_list, errors_file)


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
