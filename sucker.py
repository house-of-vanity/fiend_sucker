import requests
import urllib
import logging
import json
import traceback
from database import DataStore
from flask import Response, render_template, request, Flask
from bs4 import BeautifulSoup

app = Flask(__name__)

URL = 'https://www.rlsnet.ru'
HEADERS = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}

SQL_SCHEME = '''
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS `drugs` (
	`url`	TEXT NOT NULL UNIQUE,
        `td_name` TEXT NOT NULL,
	`name`	TEXT,
	`pharm_action`	TEXT,
	`desc`	TEXT,
	`date`	INTEGER,
        PRIMARY KEY(`url`)
);
COMMIT;
'''
SQL_DB_FILE = 'data.sqlite'

db = DataStore(SQL_DB_FILE, SQL_SCHEME, is_scheme_file=False)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('fiend_sucker')

def search(word):
    def urlize(line):
        return 'https://www.{}'.format(line[line.find('rlsnet'):])

    # look in cache for minimizing fetching rlsnet.
    in_cache = db.find_drug(word.capitalize())
    if len(in_cache) != 0:
        log.info("Found in cache - {} ({})".format(in_cache[0][1], in_cache[0][2]))
        return {
            'name': in_cache[0][2],
            'url': in_cache[0][0],
            'td_name': in_cache[0][1],
            'pharm_action': in_cache[0][3],
            'desc': in_cache[0][4],
            'date': in_cache[0][5],
            'cached': True,
        }

    parsed_word = urllib.parse.quote_plus(word.encode('cp1251'))
    log.debug("Word {} converted to {}".format(word, parsed_word))


    # get page
    req = requests.get(
        URL+'/search_result.htm?word={}'.format(parsed_word),
        headers = HEADERS
        )
    req.encoding = "cp1251"
    html = req.text

    # parse page
    html = BeautifulSoup(html, 'html.parser')
    # search in case of trade name page. (tn_index_id)
    search_result = html.find("a", {"class": 'drug__link--article'})
    try:
        url = urlize(search_result['href'])
        if "mnn_index_id" in url:
            log.info("Found '{}' - {}".format(search_result.text, url))
            return {
                'name': search_result.text,
                'url': url,
                'td_name': word,
                'cached': False,
            }
    except:
        pass
    search_results = html.find_all("div")
    for header in search_results:
        if 'в торговых названиях' in header.text:
            first_line = header.find_next_sibling("div", class_="search_serp_one")
            if first_line == None:
                continue
            tn_url = urlize(first_line.a['href'])
            log.info("Found trade name URL'{}' - {}".format(first_line.a.text, tn_url))
        if 'в действующих веществах' in header.text:
            first_line = header.find_next_sibling("div", class_="search_serp_one")
            if first_line == None:
                continue
            url = urlize(first_line.a['href'])
            log.info("Found '{}' - {}".format(first_line.a.text, url))
            return {
                'name': first_line.a.text,
                'url': url,
                'td_name': word,
                'cached': False,
                'tn_url': tn_url,
            }
    return {
        'name': None,
        'url': None,
        'tn_url': None,
        'td_name': word,
        'cached': False,
        'desc': None,
        'pharm_action': None,
        'date': None,
        'TraceRay': {
            'Exception': None,
            'Traceback': None,
            'Comment': "Nothing found. Check if drug name is correct.",
        }
    }

def fetch(data):
    result = dict()
    if data['name'] == None:
        return data
    if data['cached'] == True:
        log.debug('Getting data from cache. {}'.format(data['name']))
        result['name'] = data['name']
        result['pharm_action'] = data['pharm_action']
        result['description'] = data['desc']
        result['td_name'] = data['td_name']
        result['is_cached'] = True
        result['date'] = data['date']
        return result
    req = requests.get(
        data['url'],
        headers = HEADERS
        )
    req.encoding = "cp1251"
    html = req.text

    # parse page
    html = BeautifulSoup(html, 'html.parser')
    try:
        pharm_action = html.find("span", {"class": 'pharm_action'})
        description = pharm_action.find_next_sibling("p", {"class": 'OPIS_DVFLD_BEG'})
        log.debug("{} pharm action text found. {} chars lenght.".format(data['name'], len(pharm_action.text)))
        log.debug("{} description text found. {} chars lenght.".format(data['name'], len(description.text)))
        result['name'] = data['name'].capitalize()
        result['pharm_action'] = pharm_action.text
        result['description'] = description.text
        result['td_name'] = data['td_name'].capitalize()
        result['is_cached'] = False
        result['date'] = None
        db.add_drug(
                url=data['url'],
                name=data['name'],
                pharm_action=pharm_action.text,
                desc=description.text,
                td_name=data['td_name'],
        )
    except AttributeError as e:
        req = requests.get(
            data['tn_url'],
            headers = HEADERS
            )
        req.encoding = "cp1251"
        html = req.text

        # parse page
        html = BeautifulSoup(html, 'html.parser')
        pharm_action = html.find("span", {"class": 'pharm_action'})
        # parse content of drug
        table = html.find("table", {"class": 'sostav_table'})
        table_data = []
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            table_data.append([ele for ele in cols if ele])
        log.debug("{} pharm action text found. {} chars lenght.".format(
            data['td_name'],
            len(pharm_action.text)
            )
        )
        result['name'] = data['td_name'].capitalize()
        result['pharm_action'] = pharm_action.text
        result['description'] = table_data
        result['td_name'] = data['td_name'].capitalize()
        result['is_cached'] = False
        result['date'] = None
        result['Trace'] = {
            'Exception': str(e),
            'Traceback': ''.join(traceback.format_tb(e.__traceback__)),
            'Comment': "Can't parse some fields. Minimal info is available.",
        }

    finally:
        return result


@app.route('/get/', methods=['GET'])
def get_name():
    search_query = request.args.get('search', default="", type=str)
    names = search_query.split('\n')
    data = list()
    for name in names:
        if name != '':
            log.info(name)
            data.append(fetch(search(name)))
    response = app.response_class(
        response=json.dumps(data, ensure_ascii=False, sort_keys=True, indent=4),
        status=200,
        mimetype='application/json; charset=utf-8'
    )
    return response

@app.route('/')
def index():
    return render_template('index.html')

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
