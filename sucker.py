import requests
import urllib
import logging
import json
import traceback
import os
import genanki.genanki as genanki 
import datetime as dt
from database import DataStore
from flask import Response, render_template, request, Flask, send_file
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder='decks')
__version__ = '1.0.2'
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

CSS = None
with open('styles/style.css') as css:
    CSS = css.read()
QFMT = None
with open('styles/qfmt.html') as qfmt:
    QFMT = qfmt.read()
AFMT = None
with open('styles/afmt.html') as afmt:
    AFMT = afmt.read()



db = DataStore(SQL_DB_FILE, SQL_SCHEME, is_scheme_file=False)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('fiend_sucker')
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

def urlize(line):
    return 'https://www.{}'.format(line[line.find('rlsnet'):])

def search(word):

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
    # look for drug replacement banner.
    drug_replacement =  html.find("a", {"class": 'drug__replacement--link'})
    if drug_replacement != None:
        log.info("Found replacement for {} - {} ({})".format(
            word.capitalize(),
            drug_replacement.text.capitalize(),
            urlize(drug_replacement['href'])))
        url = urlize(drug_replacement['href'])
        html = curl(url)
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
                'tn_url': req.url
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
            tn_url = url
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
        'description': None,
        'pharm_action': None,
        'date': None,
        'TraceRay': {
            'Exception': None,
            'Traceback': None,
            'Comment': "Nothing found. Check if drug name is correct.",
        }
    }

def curl(url, headers=HEADERS, encoding="cp1251"):
    log.debug("CURLing {}".format(url))
    req = requests.get(
        url,
        headers = HEADERS
        )
    req.encoding = "cp1251"
    return req.text

def look_replacement(html):
    drug_replacement =  html.find("a", {"class": 'drug__replacement--link'})
    if drug_replacement != None:
        log.info("Found replacement - {} ({})".format(
            drug_replacement.text.capitalize(),
            urlize(drug_replacement['href'])))
        url = urlize(drug_replacement['href'])
        html = curl(url)
        html = BeautifulSoup(html, 'html.parser')
    else:
        pass
    return html


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
        result['url'] = data['url']
        return result
    html = curl(data['url'])

    # parse page
    html = BeautifulSoup(html, 'html.parser')
    html = look_replacement(html)
    try:
        pharm_action = html.find("span", {"class": 'pharm_action'})
        description = pharm_action.find_next_sibling("p", {"class": 'OPIS_DVFLD_BEG'})
        while len(description.text) <= 30:
            description = description.find_next_sibling("p")
        log.debug("{} pharm action text found. {} chars lenght.".format(data['name'], len(pharm_action.text)))
        log.debug("{} description text found. {} chars lenght.".format(data['name'], len(description.text)))
        result['name'] = data['name'].capitalize()
        result['pharm_action'] = pharm_action.text
        result['description'] = description.text
        result['td_name'] = data['td_name'].capitalize()
        result['is_cached'] = False
        result['date'] = None
        result['url'] = data['url']
        db.add_drug(
                url=data['url'],
                name=data['name'],
                pharm_action=pharm_action.text,
                desc=description.text,
                td_name=data['td_name'],
        )
    except AttributeError as e:
        html = curl(data['tn_url'])

        # parse page
        html = BeautifulSoup(html, 'html.parser')
        html = look_replacement(html)
        pharm_action = html.find("span", {"class": 'pharm_action'})
        # parse content of drug
        table = html.find("table", {"class": 'sostav_table'})
        if table != None:
            table_data = []
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                cols = [ele.text.strip() for ele in cols]
                table_data.append([ele for ele in cols if ele])
        else:
            table_data = None
        if pharm_action != None:
            log.debug("{} pharm action text found. {} chars lenght.".format(
                data['td_name'],
                len(pharm_action.text)
                )
            )
            result['pharm_action'] = pharm_action.text
        else:
            result['pharm_action'] = None
        result['name'] = data['td_name'].capitalize()
        result['description'] = table_data
        result['td_name'] = data['td_name'].capitalize()
        result['is_cached'] = False
        result['date'] = None
        result['url'] = data['tn_url']
        result['Trace'] = {
            'Exception': str(e),
            'Traceback': ''.join(traceback.format_tb(e.__traceback__)),
            'Comment': "Can't parse some fields. Minimal info is available.",
        }

    except Exception as e:
        log.error("Can't fetch data - {}".format(e))
    finally:
        return result

def gen_deck(data, name='DesuDeck', output='decks/output.apkg', css=CSS, qfmt=QFMT, afmt=AFMT):
    deck_id = 0
    try:
        os.makedirs('decks/')
    except FileExistsError:
        pass

    for c in name:
        deck_id += ord(c)
    my_deck = genanki.Deck(
      deck_id,
      name)
    my_model = genanki.Model(
      14881337,
      'DesuModel',
      css = css,
      fields=[
        {'name': 'Trade name'},
        {'name': 'Agent name'},
        {'name': 'Action'},
        {'name': 'Description'},
        {'name': 'URL'},
      ],
      templates=[
        {
          'name': 'Drug card',
          'qfmt': qfmt,
          'afmt': afmt,
        },
      ])
    for drug in data:
        log.debug("Generate note for {}.".format(drug['name'] if drug['name'] != None else drug['td_name']))
        try:
            if isinstance(drug['description'], (list,)):
                html = '<table><caption><em>Табл. 1. Состав.</em></caption><tbody>'
                for row in drug['description']:
                    if len(row) < 2:
                        row.append('')
                    html += '<tr><td>{}</td><td>{}</td></tr>'.format(row[0], row[1])
                html += '</tbody></table>'
                drug['description'] = html
            note = genanki.Note(
              model=my_model,
              fields=[
                  drug['td_name'] if drug['td_name'] != None else 'N/D',
                  drug['name'] if drug['name'] != None else 'N/D',
                  drug['pharm_action'] if drug['pharm_action'] != None else 'N/D',
                  drug['description'] if drug['description'] != None else 'N/D',
                  drug['url'] if drug['url'] != None else URL,
              ]
            )
            my_deck.add_note(note)
        except Exception as e:
            log.warning("Skip some drug.{} - {}".format(drug['td_name'], e))
    genanki.Package(my_deck).write_to_file(output)



@app.route('/get/', methods=['GET'])
def get():
    search_query = request.args.get('search', default="", type=str)
    css = request.args.get('css', default=CSS, type=str)
    qfmt = request.args.get('qfmt', default=QFMT, type=str)
    afmt = request.args.get('afmt', default=AFMT, type=str)
    deck_name = request.args.get('deck_name', default='DesuDeck', type=str)
    show_json = request.args.get('show_json', default=False, type=bool)
    names = search_query.split('\n')
    data = list()
    for name in names:
        if name != '':
            fetched_data = fetch(search(name))
            if fetched_data != {}:
                data.append(fetched_data)
            else:
                log.error("Drug {} fetch failed!".format(name))
    if show_json:
        response = app.response_class(
            response=json.dumps(data, ensure_ascii=False, sort_keys=True, indent=4),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
        return response
    else:
        date = int(dt.datetime.now().strftime("%s"))
        path = 'decks/{}.apkg'.format(date)
        gen_deck(data, name=deck_name, output=path, css=css, afmt=afmt, qfmt=qfmt)
        return send_file(path, as_attachment=True)

@app.route('/')
def index():
    return render_template(
            'index.html',
            css=CSS,
            qfmt=QFMT,
            afmt=AFMT,
            version=__version__,
            )

def main():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
