import datetime as dt
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class DataStore:
    def __init__(self, basefile, scheme, is_scheme_file=True):
        import sqlite3
        self.scheme = ''
        try:
            self.conn = sqlite3.connect(basefile, check_same_thread=False)
        except Exception as e:
            log.error('Could not connect to DataBase - {}'.format(e))
            return False
        if is_scheme_file:
            with open(scheme, 'r') as scheme_sql:
                sql = scheme_sql.read()
                self.scheme = sql
        elif not is_scheme_file:
            self.scheme = scheme
        if self.conn is not None:
            try:
                cursor = self.conn.cursor()
                cursor.executescript(self.scheme)
            except Exception as e:
                log.error('Could not create scheme - {}'.format(e))
                return False
        log.info('DB ready and connected in {}'.format(basefile))

    def execute(self, sql):
        cursor = self.conn.cursor()
        cursor.execute(sql)
        self.conn.commit()
        return cursor.fetchall()

    def add_drug(self,
                 url,
                 name,
                 pharm_action,
                 desc,
                 td_name):
        date = int(dt.datetime.now().strftime("%s"))
        try:
            sql = """
            UPDATE drugs
            SET
                name = '%s',
                pharm_action = '%s',
                desc = '%s',
                td_name = '%s'
            WHERE
                url = '%s'
            """ % (
                name.capitalize(),
                pharm_action,
                desc,
                td_name.capitalize(),
                url,
            )
            self.execute(sql)
        except:
            pass
        sql = """INSERT OR IGNORE INTO 
        drugs('url', 'name', 'pharm_action', 'desc', 'date', 'td_name') 
        VALUES ('%s','%s','%s','%s','%s','%s')""" % (
            url,
            name.capitalize(),
            pharm_action,
            desc,
            date,
            td_name.capitalize(),
        )
        self.execute(sql)
        log.debug("{} ({}) has been added to drug database.".format(td_name, name))

    def find_drug(self, drug):
        sql = """
        SELECT * FROM `drugs`
        WHERE td_name LIKE '%%%s%%' LIMIT 1
        """ % (
            drug
        )
        result = self.execute(sql)
        return(result)

