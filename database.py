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

    def add_relation(self, word, user_id, conf_id, text):
        word_id = self.save_word(word)
        date = int(dt.datetime.now().strftime("%s"))
        sql2 = "INSERT OR IGNORE INTO xxx_message('text') VALUES ('%s')" % text
        self.execute(sql2)
        sql3 = "SELECT id FROM `xxx_message` WHERE text = '%s'" % text
        msg_id = self.execute(sql3)[0][0]
        sql = """INSERT OR IGNORE INTO 
        relations('word_id', 'user_id', 'conf_id', 'msg_id', 'date') 
        VALUES ('%s','%s','%s','%s', '%s')""" % (
            word_id,
            user_id,
            conf_id,
            msg_id,
            date
        )
        self.execute(sql)

    def add_alert(self, user_id, conf_id, alert_time, message):
        date = int(dt.datetime.now().strftime("%s"))
        if len(alert_time) < 4:
            alert_time = (dt.datetime.now() + dt.timedelta(minutes=int(alert_time[1:]))).strftime("%H%M")
        sql = """INSERT OR IGNORE INTO 
        alert('conf_id', 'user_id', 'created', 'time', 'message') 
        VALUES ('%s','%s','%s','%s','%s')""" % (
            conf_id,
            user_id,
            date,
            alert_time,
            message
        )
        self.execute(sql)


    def all_conf_users(self, conf_id):
        sql = """
        SELECT DISTINCT(u.username), u.first_name, u.id FROM relations r 
        LEFT JOIN user u 
        ON u.id = r.user_id
        LEFT JOIN conf c 
        ON r.conf_id = c.id
        WHERE c.id = '%s'
        """ % (
            conf_id
        )
        result = self.execute(sql)
        return(result)

    def get_random_word(self, count=1, like="%"):
        sql = "SELECT word FROM word WHERE word LIKE '%s' ORDER BY random() LIMIT %s" % (like, count)
        print(sql)
        result = self.execute(sql)
        return(result)

    def here(self, user_id, conf_id):
        sql = """
        SELECT DISTINCT(u.username), u.id, u.first_name FROM relations r 
        LEFT JOIN user u 
        ON u.id = r.user_id
        LEFT JOIN conf c 
        ON r.conf_id = c.id
        WHERE c.id = '%s' and 
        u.id != '%s'
        """ % (
            conf_id,
            user_id
        )
        result = self.execute(sql)
        return(result)

    def reset(self, user_id, conf_id):
        date = int(dt.datetime.now().strftime("%s"))
        sql = """
        INSERT OR IGNORE INTO reset (user_id, conf_id, date, relation_id) 
        VALUES ('%s', '%s', '%s', (SELECT MAX(rowid) FROM relations));
        """ % (
            user_id,
            conf_id,
            date
        )
        result = self.execute(sql)
        return(result)

    def command(self, sql):
        if 'DELETE' in sql.upper() \
                or 'INSERT' in sql.upper() \
                or 'UPDATE' in sql.upper() \
                or 'DROP' in sql.upper() \
                or 'CREATE' in sql.upper() \
                or 'ALTER' in sql.upper():
            return('gtfo')
        try:
            if 'LIMIT' in sql.upper()[-9:]:
                result = self.execute(sql)
            else:
                result = self.execute(sql + ' limit 20')
        except Exception as err:
            result = err
        return(result)

    def close(self):
        self.conn.close()
