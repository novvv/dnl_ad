#!/usr/bin/python
import daemon
import psycopg2
import psycopg2.extras
import smtplib
import sys
import logging
import logging.handlers

CONNECTION_STRING="host='localhost' dbname='class4_pr' user='postgres'"


from logging import config

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(module)s P%(process)d T%(thread)d %(message)s'
            },
        },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
            'formatter': 'verbose',
            },
        'sys-logger6': {
            'class': 'logging.handlers.SysLogHandler',
            'address': '/dev/log',
            'facility': "local6",
            'formatter': 'verbose',
            },
        },
    'loggers': {
        'my-logger': {
            'handlers': ['sys-logger6','stdout'],
            'level': logging.DEBUG,
            'propagate': True,
            },
        }
    }

config.dictConfig(LOGGING)

LOG=logging.getLogger("my-logger")



def sendMail(FROM,TO,SUBJECT,TEXT,SERVER):
    """this is some test documentation in the function"""
    message = """\
        From: %s
        To: %s
        Subject: %s
        %s
        """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    # Send the mail
    try:
      server = smtplib.SMTP(SERVER)
      server.connect()
      server.sendmail(FROM, TO, message)
      server.quit()
    except Exception as e:
      LOG.error("sending mail: %s",str(e))

def query(sql,all=True):
    conn_string=CONNECTION_STRING
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    LOG.info(sql)
    cursor.execute(sql)
    if all:
       return cursor.fetchall()
    else:
       return cursor.fetchone()

def get_mail_params():
    try:
       params=query("select * from system_parameter")[0]
    except Exception as e:   
       LOG.error("system_parameters not ready: %s",str(e))
       raise e
    mail_host=params['mailserver_host']
    mail_from=params['mail_server_from']
    return mail_from, mail_host

def run_notify_client_balance():
    mail_from,mail_host = get_mail_params()
    clients=query("select * from client where notify_client_balance=1")
    for cl in clients:
       LOG.info("%d : %s" % ( cl['client_id'],cl['email'] ))
       sendMail(mail_from,cl['email'],'NOTIFY BALANCE','bla bla bla',mail_host)


if __name__ == '__main__':
    print 'This is a Dnl Alert Daemon'
    run_notify_client_balance()
