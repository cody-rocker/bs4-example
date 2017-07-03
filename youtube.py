#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys
import urllib
import urllib2
import random

from bs4 import BeautifulSoup

_log_wrapper = '%s/ {tag}: {msg}'

DEBUG = False
VERBOSE = False

BASE_URL = 'https://www.youtube.com'
THUMB_URL = 'https://i.ytimg.com/vi/{stub}/hqdefault.jpg'
SEARCH_URL = BASE_URL + '/results?search_query={query}'

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.109 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.10240',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36 OPR/37.0.2178.31',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.10240',
    # '',
]

#########################################################
##    Class Definitions
#########################################################

class Log:
    ''' Utility class for convenient console logging
    '''
    global _log_wrapper

    @staticmethod
    def verbose(tag, message):
        verbose_output = _log_wrapper % ('verbose')
        if VERBOSE: print(verbose_output.format(tag=tag, msg=message))

    @staticmethod
    def debug(tag, message):
        debug_output = _log_wrapper % ('debug' if VERBOSE else 'D')
        if DEBUG: print(debug_output.format(tag=tag, msg=message))

    @staticmethod
    def info(tag, message):
        info_output = _log_wrapper % ('info' if VERBOSE else 'I')
        print(info_output.format(tag=tag, msg=message))

    @staticmethod
    def error(tag, message, error_code=-1, exit=False):
        error_output = _log_wrapper % ('error' if VERBOSE else 'E')
        print(error_output.format(tag=tag, msg=message))
        if exit: sys.exit(error_code)

class UserAgent:
    """ Utility class for easy UserAgent selection
    """
    global UA_LIST

    @staticmethod
    def get_random():
        """ Return a (pseudo)random User-Agent from UA_LIST
        """
        if len(UA_LIST) == 1: return UA_LIST[0]
        elif len(UA_LIST) > 1:
            selected_ua = UA_LIST[random.randint(0, len(UA_LIST) - 1)]
            Log.debug('UserAgent.get_random', '"{}"'.format(
                selected_ua if len(selected_ua) <= 64 else \
                selected_ua[:61] + '...'))
            return selected_ua
        else:
            Log.error('UserAgent.get_random', 'Empty user_agent list', exit=True)

class Entity(object):
    ''' This object holds the necessary data for a media item 
        e.g: swamp_db media_item, kodi addon item
    '''

    def __repr__(self):
        """ Formal string representation
        """
        return '\n{\n\ttitle: %s,\n\tsrc: %s,\n\tgenre: %s,\n\tinfo: %s,\n\tthumbnail: %s,\n\tfanart: %s\n}' % (
            self.title, self.src, self.genre, self.info, self.thumbnail, self.fanart)

    def __str__(self):
        """ Simple string representation
        """
        return '{:24}: <{}/watch?v={}>'.format(
            self.title if len(self.title) <= 24 else self.title[:21] + '...', 
            BASE_URL, self.src)

    def __eq__(self, obj):
        """ Ensure unique content in set generation
        """
        return True if self.src == obj.src else False

    def create(self, item_dict):
        """ create assumes this dictionary is correctly formatted and all
            keys are present
        """
        self.title = item_dict['title']
        self.src = item_dict['src']
        self.genre = item_dict['genre']
        self.info = item_dict['info']
        self.thumbnail = item_dict['thumb']
        self.fanart = item_dict['fanart']

        Log.verbose('Entity.create', 'Created entity: {}'.format(repr(self)))

        return self

    def to_xml(self):
        pass

#########################################################
##    Function Definitions
#########################################################

def parse_args():
    """ Parse command line arguments and return a dict containting script
        parameters
    """
    args = {'debug': DEBUG, 'verbose': VERBOSE, 'query': None}

    for argument in sys.argv:
        if argument in ['-d', '--debug']: args['debug'] = True
        if argument in ['-vv', '--verbose']: args['verbose'] = True

        if argument.startswith('-q=') or argument.startswith('--query='):
            tmp = argument.split('=')[1].replace('"', '')
            args['query'] = urllib.quote_plus(tmp)

    return args


def get_soup(url):
    """ Builds a urllib2.Request object with a random User-Agent and
        returns a BeautifulSoup object from passed in url
    """
    try:
        # Some sites have bot protection, you can spoof headers to subvert these
        request = urllib2.Request(url, None, {'User-Agent': UserAgent.get_random()})
        html = urllib2.urlopen(request).read()

    except Exception as err:
        Log.error('get_soup', 'url failed to parse: {}'.format(err), exit=True)

    return BeautifulSoup(html, 'html.parser')


def parse_entity(video_soup):
    """ Create and return a new Entity object from html entity with class
        'yt-lockup-content'
    """
    tmp_title = video_soup.find('h3', class_='yt-lockup-title')
    tmp_stub = tmp_title.find('a').get('href').split('=')[1]
    tmp_channel = video_soup.find('div', class_='yt-lockup-byline').find('a')
    tmp_info = video_soup.find('ul', class_='yt-lockup-meta-info')
    if tmp_info is not None: 
        tmp_info = tmp_info.find_all('li')

    return Entity().create({
        'title': tmp_title.find('a').text.encode('utf-8'),
        'src': tmp_stub.encode('utf-8'),
        'thumb': THUMB_URL.format(stub=tmp_stub.encode('utf-8')),
        'fanart': None,
        'genre': tmp_channel.text.encode('utf-8'),
        'info': '; '.join([_.text.encode('utf-8') for _ in tmp_info])})


def parse_videos_to_list(video_soup):
    """ Parse an arbitrary set of html elements containing children of class
        'yt-lockup-content' to a list of unique Entities
    """
    videos = []
    for video in video_soup.find_all('div', class_='yt-lockup-content'):
        videos.append(parse_entity(video))

    return set(videos)


def parse_feed_to_dict(feed, _dict=None):
    """ Create or append an html entity with class 'feed-item-dismissable' to
        a dictionary
    """
    if _dict == None: results = {}
    else: results = dict(_dict)

    # grab the section title to use as dictionary key
    section_label = feed.find('span', class_='branded-page-module-title-text')

    results[section_label.text] = parse_videos_to_list(feed)

    video_count = len(results[section_label.text])
    Log.debug('parse_feed_to_dict', '{} scraped successfully'.format(
        section_label.text) if video_count == 15 \
        else '{} result(s) for {}'.format(video_count, section_label.text))

    return results


def scrape_homepage():
    """ Default script operation. Simply scrapes videos from YouTube homepage
    """
    Log.info('scrape_homepage', 'Scraping <{}> for video links ...'.format(BASE_URL))
    results = None  # going to be a dict, but needs default value
    soup = get_soup(BASE_URL)  # parse the youtube homepage

    # this grabs each section on the default homepage and returns a list
    default_feeds = soup.find_all('div', class_='feed-item-dismissable')

    if len(default_feeds) > 0:  # if we found results
        for feed in default_feeds:  # loop through the results
            results = parse_feed_to_dict(feed, results)
    else: 
        Log.error('scrape_homepage', 'no results found', exit=True)
    
    return results


def scrape_query_results(query):
    """ Alternative script operation. Scrapes the results from a query provided
        from a command line argument
    """
    query_url = SEARCH_URL.format(query=query)
    Log.info('scrape_query_results', 'Scraping <{}> for video links ...'.format(query_url))
    soup = get_soup(query_url)

    query_results = soup.find('ol', class_='item-section')

    return {'Search Results': parse_videos_to_list(query_results)}


def show_results(results):
    """ Format and write results to terminal
    """
    display_num = 5 if not VERBOSE else 25
    if results is not None and len(results) > 0:
        print('')
        for section in results:
            print(' :: {}'.format(section))
            for i, entity in enumerate(results[section]):
                if i < display_num: print('    {}) {}'.format(i + 1, entity))
                else:
                    print('{}... {} more'.format(
                        '\t' * 8, len(results[section]) - display_num))
                    break
            print('')

#########################################################
##    Script Execution Definition
#########################################################

if __name__ == '__main__':
    args = parse_args()  # check command line arguments ...
    
    # ... to set script parameters
    DEBUG = args['debug'] or args['verbose']
    if DEBUG: Log.debug(__name__, 'debug output enabled')
    VERBOSE = args['verbose']
    if VERBOSE: Log.debug(__name__, 'verbose output enabled')

    Log.verbose(__name__, 'args={}'.format(args))

    query = args['query']

    # perform script operation
    show_results(
        scrape_homepage() if query else \
        scrape_query_results(query)
        )

    # at this point we should have a 'results' dictionary along the lines of:
    # {
    #   'Section A': [<Entity.a1>, <Entity.a2>, ...],
    #   'Section B': [<Entity.b1>, <Entity.b2>, ...],
    #   ...
    # }
