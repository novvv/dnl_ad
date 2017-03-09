#!/usr/bin/python
#dnl_ad daemon
import daemon
from daemon import runner
import psycopg2
import psycopg2.extras
import smtplib
import sys
import logging
import logging.handlers
from time import sleep,gmtime
from datetime import date,datetime,timedelta,time
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
              filename, maxBytes=int(maxBytes), backupCount=int(backupCount))
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
            'filename':LOGFILE,
            'maxBytes':20000,
            'backupCount':50,
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
            'handlers': ['stdout'],
            'level': logging.DEBUG,
            'propagate': True,
            },
        }
    }


config.dictConfig(LOGGING)

LOG=logging.getLogger("my-logger")

def get_mail_params(fr):
    params=''
    try:
       p=query("select * from system_parameter")[0]
    except Exception as e:   
       LOG.error("system_parameters not ready: %s",str(e))
       raise e
    return (p.smtphost, p.smtpport,p.emailusername,p.emailpassword,p.__dict__[fr])


def sendMail(from_field,TO,SUBJECT,TEXT):
    """sending email"""
    (host,port,user,passw,mfrom) = get_mail_params(from_field)
    message = """\
        From: %s
        To: %s
        Subject: %s
        content-type: "text/html"
        %s
        """ % (mfrom, ", ".join(TO), SUBJECT, TEXT)
    LOG.info('mail:'+host+':'+port+' '+user+':'+passw+'from:'+mfrom)
    try:
      server = smtplib.SMTP(host+':'+port)
      server.ehlo()
      server.starttls()
      #server.ehlo
      server.login(user, passw)      
      server.sendmail(mfrom, TO, message)
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


def process_template(templ,env):
    try:
        r=re.compile('{ (?P<name> [^}]* ) }', re.VERBOSE)
        fields= r.findall(templ)
        LOG.info('template fields:'+str(fields) )
        out=templ
        for f in fields:
            if hasattr(env,f):
                r=re.compile('{%s}' % f, re.VERBOSE)
                out=r.sub(str(env.__dict__[f]),out)
            if hasattr(env,'has_key') and env.has_key(f):
                r=re.compile('{%s}' % f, re.VERBOSE)
                out=r.sub(str(env[f]),out)
        LOG.info('rendered:'+out)
        return out
    except Exception as e:
        LOG.error('template error:'+str(e) )
        return templ

def do_notify_client_balance(sleep_time,no_send_mail):
     LOG.info("start notify low client balance")    
     clients=query("select * from client c,client_balance b where c.client_id::text=b.client_id and balance::numeric <= notify_client_balance and status=true")
     try:
          templ=query('select * from mail_tmplate')[0]
     except Exception as e:
          LOG.error('no template table:'+str(e) )
     for cl in clients:
        LOG.warning('NOTIFY LOW BALANCE ALERT! client_id:%s, name:%s' % (cl.client_id,cl.name) )
        if cl.payment_term_id:
            try:
                cl.payment_terms=query( "select * from payment_term where payment_term_id=%s" % cl.payment_term_id)[0].name 
            except:
                LOG.error('no payment_term table:'+str(e) )
        else:
            cl.payment_terms='(default)'
        #prepare in template fields mapping
        cl.date=date.today()
        cl.time=datetime.now().time()
        cl.now=datetime.now()
        sendtime_a=datetime.combine(cl.date,cl.daily_balance_send_time) - timedelta(seconds=sleep_time*2)
        sendtime_b=datetime.combine(cl.date,cl.daily_balance_send_time) + timedelta(seconds=sleep_time*2)
        if cl.last_lowbalance_time:
            last_send=datetime.combine(cl.date,cl.last_lowbalance_time)
        else:
            last_send=cl.now - timedelta(hours = 24)
        LOG.info('times:last %s now %s a %s b %s' % (str(last_send),str(cl.now),str(sendtime_a),str(sendtime_b) ) )
        if cl.now-last_send > timedelta(seconds = sleep_time*2) and cl.now > sendtime_a  and cl.now < sendtime_b:
            LOG.info('Time to send notification!')
        else:
            continue
        cl.company_name=cl.company
        cl.allow_credit=cl.allowed_credit
        cl.balance='%20.2f' % float(cl.balance)
        cl.notify_balance=cl.notify_client_balance
        
        subj=process_template(templ.lowbalance_subject,cl)
        content=process_template(templ.lowbalance_content,cl)
        LOG.info("%s : %s subject: %s content: %s" % ( cl.client_id,cl.email ,subj, content ))
        try:
             if no_send_mail==False:
                 sendMail('fromemail', cl.email,subj,content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e) )
        #make things after send alert
        
        query("update client set last_lowbalance_time='%s' where client_id=%s" % (str(cl.now)+'+00',cl.client_id) )
    
def do_notify_zero_balance(sleep_time,no_send_mail):
     LOG.info("start notify Zero client balance")    
     clients1=query("select * from client c,client_balance b where c.client_id::text=b.client_id and balance::numeric <= 0 and status=true and mode=1")
     clients2=query("select * from client c,client_balance b where c.client_id::text=b.client_id and balance::numeric <= -credit and status=true and mode=2")
     clients=clients1+clients2
     try:
          templ=query('select * from mail_tmplate')[0]
     except Exception as e:
          LOG.error('no template table:'+str(e) )
     for cl in clients:
        LOG.warning('NOTIFY ZERO BALANCE ALERT! client_id:%s, name:%s' % (cl.client_id,cl.name) )
        if cl.payment_term_id:
            try:
                cl.payment_terms=query( "select * from payment_term where payment_term_id=%s" % cl.payment_term_id)[0].name 
            except:
                LOG.error('no payment_term table:'+str(e) )
        else:
            cl.payment_terms='(default)'
        #prepare in template fields mapping
        cl.date=date.today()
        cl.time=datetime.now().time()
        cl.now=datetime.now()
        sendtime_a=datetime.combine(cl.date,cl.daily_balance_send_time) - timedelta(seconds=sleep_time*2)
        sendtime_b=datetime.combine(cl.date,cl.daily_balance_send_time) + timedelta(seconds=sleep_time*2)
        if cl.last_lowbalance_time:
            last_send=datetime.combine(cl.date,cl.last_lowbalance_time)
        else:
            last_send=cl.now - timedelta(hours = 24)
        LOG.info('times:last %s now %s a %s b %s' % (str(last_send),str(cl.now),str(sendtime_a),str(sendtime_b) ) )
        if cl.now-last_send > timedelta(seconds = sleep_time*2) and cl.now > sendtime_a  and cl.now < sendtime_b:
            LOG.info('Time to send notification!')
        else:
            continue
        cl.company_name=cl.company
        cl.allow_credit=cl.allowed_credit
        cl.balance='%20.2f' % float(cl.balance)
        cl.notify_balance=cl.notify_client_balance
        
        subj=process_template(templ.lowbalance_subject,cl)
        content=process_template(templ.lowbalance_content,cl)
        LOG.info("%s : %s subject: %s content: %s" % ( cl.client_id,cl.email ,subj, content ))
        try:
             if no_send_mail==False:
                 sendMail('fromemail', cl.email,subj,content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e) )
        #make things after send alert
        query("update client set last_lowbalance_time='%s' where client_id=%s" % (str(cl.time)+'00:00',cl.client_id) )




class App():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  PIDFILE
        self.pidfile_timeout = 5
        
    def run(self):
        sleep_time=300
        no_send_mail=False #True
        while True:
            try:
                do_notify_client_balance(sleep_time,no_send_mail)
                #do_notify_zero_balance(sleep_time,no_send_mail)
            except Exception as e:
                LOG.error('Unexpected:'+str(e) )
            finally:
                sleep(sleep_time)
            
app=App()

if __name__ == '__main__':
    print 'This is a Dnl Alert Daemon (novvvster@gmail.com)'
    if sys.argv[1]=='debug':
       app.run()
    else:
       dr=runner.DaemonRunner(app)
       for h in LOG.handlers:
          if hasattr(h,'stream'):
            if dr.daemon_context.files_preserve is None:
              dr.daemon_context.files_preserve=[h.stream]
            else:
              dr.daemon_context.files_preserve.append(h.stream)
       dr.do_action()
    LOG.info('dnl_ad terminated!')
