#!/usr/bin/python
import daemon
from daemon import runner
import psycopg2
import psycopg2.extras
import smtplib
import sys
import logging
import logging.handlers
from time import sleep,gmtime
import re

CONNECTION_STRING="host='localhost' dbname='class4_pr' user='postgres'"
PIDFILE='/var/tmp/dnl_ad.pid'
LOGFILE='/var/tmp/dnl_ad.log'
LOGLEVEL='DEBUG'



from logging import config

class GZipRotator:
    def __call__(self, source, dest):
        os.rename(source, dest)
        f_in = open(dest, 'rb')
        f_out = gzip.open("%s.gz" % dest, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        os.remove(dest)

def rotating_file_handler(filename, maxBytes,backupCount):
    log=logging.handlers.RotatingFileHandler(
              filename, maxBytes=int(maxBytes), backupCount=int(backupCount)
    log.rotator=GZipRotator()
    return log


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
        'rotated': {
            '()':rotating_file_handler,
	    'level':LOGLEVEL,
            'formatter': 'verbose',
            'filename':LOGGILE,
            'maxBytes':20,
            'backupCount':5,
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
#            'handlers': ['sys-logger6','rotated','stdout'],
            'handlers': ['rotated'],
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
    def _res(row,descr):
      class Rec:
         pass
      r=Rec()
      i=0
      for ds in descr:
        r.__dict__[ds.name]=row[i]
        i+=1
      return r
    conn_string=CONNECTION_STRING
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    #cursor = conn.cursor()
    LOG.info('query:'+sql)
    cursor.execute(sql)
    conn.commit()
    result=[]
    #LOG.info('cursor desc:'+str(cursor.description))
    #return result
    if cursor.description is not None:
      desc=cursor.description
      for row in cursor:
        #print row
        result.append(_res(row,desc))
    return result       

def get_mail_params():
    params=''
    try:
       p=query("select * from system_parameter")[0]
    except Exception as e:   
       LOG.error("system_parameters not ready: %s",str(e))
       raise e
    #mail_host=params['mailserver_host']
    #mail_from=params['mail_server_from']
    return p.mail_server_from, p.mailserver_host

def run_notify_client_balance():
  while True:
     LOG.info("start notify client balanse")    
     mail_from,mail_host = get_mail_params()
     clients=query("select * from client where notify_client_balance=1")
     for cl in clients:
        LOG.info("%d : %s" % ( cl.client_id,cl.email ))
        sendMail(mail_from,cl.email,'NOTIFY BALANCE','bla bla bla',mail_host)
        query("update client set notify_client_balance=0 where client_id=%d" % cl.client_id)
     sleep(10)

class App():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  PIDFILE
        self.pidfile_timeout = 5
    def run(self):
        run_notify_client_balance()
app=App()
  

if __name__ == '__main__':
    print 'This is a Dnl Alert Daemon'
   
    dr=runner.DaemonRunner(app)
    for h in LOG.handlers:
        if hasattr(h,'stream'):
           if dr.daemon_context.files_preserve is None:
              dr.daemon_context.files_preserve=[h.stream]
           else:
              dr.daemon_context.files_preserve.append(h.stream)
    dr.do_action()
    LOG.info('dnl_ad terminated!')
