#!/usr/bin/python
# -*- coding: UTF-8 -*-
import logging,sys
try:
    import ConfigParser as configparser
except:
    import configparser

from __version__ import __version__

config = configparser.ConfigParser()
config.read('dnl_ad.ini')

#configuration
CONNECTION_STRING = config.get('dnl_ad','CONNECTION_STRING')
CDR_DOWNLOAD_URL =config.get('dnl_ad','CDR_DOWNLOAD_URL')
PIDFILE = config.get('dnl_ad','PIDFILE')
LOGFILE = config.get('dnl_ad','LOGFILE')
LOGLEVEL = config.getint('dnl_ad','LOGLEVEL')
#/configuration


#from daemon import runner
import psycopg2
import psycopg2.extras
import smtplib
#import signal
from signal import SIGTERM

import sys, os, time, atexit
import gzip

import logging.handlers
from logging import config
import traceback
from time import sleep,  mktime
from datetime import date, datetime, timedelta, time
from pytz import UTC
from collections import defaultdict
import pytz
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
#local imports
import schedule
from templates import *
try:
    # For Python 3.0 and later
    from urllib.request import urlopen,Request
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen,Request


SLEEP_TIME = 30
SEND_MAIL = 1




dt = datetime.now(UTC)  # current time in UTC
zone_names = defaultdict(list)

for tz in pytz.common_timezones:
    zone_names[dt.astimezone(pytz.timezone(tz)).utcoffset()].append(tz)

def tz_to_delta(off):
    if off in[None, '', '+00:00']:
        return timedelta(hours=0)
    else:
        hdelta=int(off[1:].split(':')[0])
        mdelta=int(off[1:].split(':')[1])
        sign=-1 if off[1]=='-' else 1
        if hdelta > 24 or mdelta >60:
            raise Exception('Bad timezone offset!')
        return sign*timedelta(hours=hdelta,minutes=mdelta)
    return timedelta(hours=0)

def tz_to_hdelta(off):
    if off in[None, '', '+00:00']:
        return 0
    else:
        hdelta=int(off[1:].split(':')[0])
    sign=-1  if  off[0] == '-'  else 1
    return sign*hdelta 
    
def tz_align(d, off):
    """Return datetime, converted by given offset.Time zone info from""" \
        """string -12:00 ."""
    return d+tz_to_delta(off)

def get_systz():
    systz=query('select sys_timezone from system_parameter offset 0 limit 1')[0].sys_timezone
    if systz:
        systz=systz[0:3]+':'+systz[3:]
    else:
        systz='+00:00'
    return systz

def _f(balance):
    if not balance:
        return '0'
    balance=float(balance)
    if balance<0:
        return '(%.2f)' % -balance
    else:
        return '%.2f' % balance

class GZipRotator:


    """Rotate and gzip log files."""

    def __call__(self, source, dest):
        os.rename(source, dest)
        f_in = open(dest, 'rb')
        f_out = gzip.open("%s.gz" % dest, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        os.remove(dest)

def rotating_file_handler(filename, maxBytes, backupCount):
    "logger hook"
    log = logging.handlers.RotatingFileHandler(
              filename, maxBytes=int(maxBytes), backupCount=int(backupCount))
    log.rotator = GZipRotator()
    return log

#Confuguration for loggin system
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)-15s %(levelname)s %(module)s P%(process)d \
            T%(thread)d %(message)s'
            },
        'compact':{
             'format': '%(asctime)-15s %(levelname)s %(message)s'
           }, 
        },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
            'formatter': 'verbose',
            },
        'rotated': {
            '()': rotating_file_handler,
            'level': LOGLEVEL,
            'formatter': 'compact',
            'filename': LOGFILE,
            'maxBytes': 160000,
            'backupCount': 32,
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
            #            'handlers': ['stdout'],
            'handlers': ['rotated'],
            'level': LOGLEVEL,
            'propagate': True,
            },
        'debug-logger': {
            'handlers': ['stdout'],
            'level': logging.DEBUG,
            'propagate': True,
            },
        
        }
    }


config.dictConfig(LOGGING)
#Establish logger
LOG = logging.getLogger("my-logger")

def _one(func):
    def one_call(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            LOG.error('UNEXPECTED!\n'+traceback.format_exc() )
    return one_call


def get_mail_params(fr):
    """Get parameters for sending mail from system configuration table."""
    try:
        m = query("select * from system_parameter")[0]
        efrom = m.fromemail
        try:
            p = query("select * from mail_tmplate")[0]
            if  fr in p.__dict__:
                frm_id=p.__dict__[fr]
                if frm_id and frm_id != 'default':
                    fe=query("select id,email from mail_sender where id = %d" % int(frm_id))
                    if fe and fe[0].email:
                        efrom=fe[0].email
        except:
            LOG.warning("Email parameters  not good: %s", str(e)+traceback.format_exc())
        return (
        (m.smtphost, m.smtpport, m.emailusername, \
         m.emailpassword, efrom))
    except Exception as e:
        LOG.error("Email parameters  not ready: %s", str(e)+traceback.format_exc())
        raise e


def cleanhtml(raw_html):
  cleanr = re.compile('<.*?>')
  raw_html=raw_html.replace('\r', '').replace('\n', '').replace('\t', '')
  cleantext = re.sub(cleanr, '', raw_html)
  return cleantext

  
def send_mail(from_field, to, subject, text, cc='', type=0, alert_rule='', client_id=0):
    """sending email."""
    (host, port, user, passw, mfrom) = get_mail_params(from_field)
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = mfrom
    msg['To'] = to
    msg['CC'] = cc
    txt = MIMEText(text, 'html')
    msg.attach(txt)
    #LOG.info(msg.as_string())
        
    if SEND_MAIL:
        errors=''
        status=0
        lastto=''
        try:
            cc = '' if not cc else cc
            to_set=set([x for x in to.split(';')+cc.split(';') if x !='' and '@' in x])
            for t in to_set:
                    lastto=t
                    #print(t)
                    if port=='465':
                        server = smtplib.SMTP_SSL(host+':'+port)
                    else:
                        server = smtplib.SMTP(host+':'+port)
                    #server.connect()
                    #print 'connect'
                    server.ehlo_or_helo_if_needed()
                    #print 'ehlo'
                    if port == '587':
                        server.starttls()
                    server.login(user, passw)
                    #print 'login'
                    server.sendmail(mfrom, t, msg.as_string())
                    #print 'sent'
                    server.quit()
                    #print 'quit'
                    sleep(1)
        except Exception as e:
            #server.quit()
            LOG.error("MAIL EROR: from:%s to:%s err: %s" % (mfrom, lastto , str(e) ) )
            errors = errors+str(e)
            status=1
        LOG.warning('MAIL SENT: from: %s to: %s status: %d subj: %s body:%s ' % (mfrom, to, status, subject,  cleanhtml(text)[0:1024]))
        """
  id integer NOT NULL DEFAULT nextval('daily_email_log_id_seq'::regclass),
  send_time timestamp with time zone,
  client_id integer,
  email_addresses character varying(500),
  files character varying(500),
  type smallint, -- 1,low balance...
  email_res text,
  alert_block_egress_id integer,
  alert_block_code_name text,
  status smallint, -- 0，null-success；1-fail
  error text, -- email error
  resend_email text,
  subject character varying(100),
  content text,
  is_view integer NOT NULL DEFAULT 0, -- 是否在自助页面查看
  alert_rule character varying(500),
  CONSTRAINT daily_email_log_id PRIMARY KEY (id)
        """
        try:
            email_addresses=json.dumps(to+';'+cc)
            text=json.dumps(text)
            subject=json.dumps(subject)
            errors=json.dumps(errors).replace("'", '"')
            query("""insert into email_log(send_time,client_id,email_addresses,type,status,error,subject,content,alert_rule )
                values(date_trunc('second',now()),%d,'%s',%d,%d,'%s','%s','%s','%s')  """ %  (int(client_id), email_addresses[0:500], type, status, errors, subject[0:100], text, alert_rule[0:500]) )
        except:
            LOG.warning('MAIL SENT: cannot write in email_log table')
        #if status!=0:
        #   raise 
def query(sql, all=True):
    """Call postgresql query, return record array."""
    def _res(row, descr):
        "Make one record as class Rec"
        class Rec:
            def __repr__(self):
                return str(self.__dict__)
        r = Rec()
        i = 0
        for ds in descr:
            r.__dict__[ds.name] = row[i]
            i += 1
        return r
    conn_string = CONNECTION_STRING
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    #cursor = conn.cursor()
    LOG.info('query:'+sql)
    cursor.execute(sql)
    conn.commit()
    result = []
    #LOG.info('cursor desc:'+str(cursor.description))
    #return result
    if cursor.description is not None:
        desc = cursor.description
        for row in cursor:
            #print row
            result.append(_res(row, desc))
    return result


def process_template(templ, env):
    """Render template on environment dictionary."""
    if templ=='' or templ is None:
        raise Exception('Empty template')
    if env is None:
        raise Exception('No object in template to render!')
    try:
        r = re.compile('{ (?P<name> [^}]* ) }', re.VERBOSE)
        fields = r.findall(templ)
        LOG.info('template fields:'+str(fields))
        out = templ
        for f in fields:
            if hasattr(env, f):
                r = re.compile('{%s}' % f, re.VERBOSE)
                out = r.sub(str(env.__dict__[f]), out)
            if hasattr(env, 'has_key') and f in env:
                r = re.compile('{%s}' % f, re.VERBOSE)
                out = r.sub(str(env[f]), out)
        LOG.debug('RENDERED TEMPLATE:\n'+out)
        return out
    except Exception as e:
        LOG.error('Template error:'+str(e)+traceback.format_exc())
        return 'Notice to staff: the template for this letter is emty or damaged'

def process_table(data, select=None, style={'table': 'dttable'}):
    """Render html table from record set."""
    if len(data) > 0:
        text = '<table class="%s">' % style['table']
        if not select:
            select = list(data[0].__dict__.keys())
        for row in data:
            text += '<tr>'
            for f in select:
                text += '<td>%s</td>' % row.__dict__[f]
            text += '</tr>'
        text += '</table>'
        return text
    else:
        return '<p>-------</p>'

#--- Api request ---

def create_download_link(start_time=1495429200,end_time=1495515600,id=36,ingress=True,keep_longer=1, non_zero=1):
    #To retrieve authentication token send POST request on http://localhost:8887/
    #Authorization service is available from localhost only. If you don't have access to .113, you can use static token 'Yuza2L2rlGkdemBeYzL0SVncFafTjYNFSMpShsJT614inGMLDf
    token = 'Yuza2L2rlGkdemBeYzL0SVncFafTjYNFSMpShsJT614inGMLDf'
    try:
        #stage 1: get token
        req = Request('http://localhost:8887/')
        req.get_method = lambda: 'POST'
        text=urlopen(req).read().decode('utf-8')
        resp=json.JSONDecoder().decode(text)
        token = resp['token']
    except:
        pass
    
    if ingress:
        field = '31,46,43,45,41,59,60,11,9,0'
        trunk = 'ingress_id=%d'% id
    else:
        field='31,37,50,49,48,62,60,21,19,0'
        trunk='egress_id=%d'% id
    try:
        #data = 'start_time=%d&end_time=&d&%s&field=%s&keep_longer=%d&non_zero=%d' % (start_time,end_time,trunk,keep_longer, non_zero)
        data = 'start_time=%d&end_time=%d&%s&field=%s&keep_longer=%d' % (start_time,end_time,trunk,field,keep_longer)
        #return data
        hdr = { 'Accept':'application/json','Authorization': 'Token %s' % token ,'Content-Type': 'application/x-www-form-urlencoded'}
        #stage 2: get request id
        resp=None
        req = Request('http://localhost:8889', headers=hdr,data=data.encode('ascii'))
        req.get_method = lambda: 'POST'
        LOG.info("CREATE_DOWNLOAD_LINK: %s" % data)
        text=urlopen(req).read().decode('utf-8')
        resp = json.JSONDecoder().decode(text)
        if resp['code'] != 200:
            LOG.error("CREATE_DOWNLOAD_LINK: %s" % str(resp) )
        req_id = resp['request_id']
        #stage 3: get download_link
        retr=20
        while retr:
            resp=None
            req = Request('http://localhost:8889/%s' % req_id, headers=hdr )
            req.get_method = lambda: 'GET'
            text=urlopen(req).read().decode('utf-8')
            resp = json.JSONDecoder().decode(text)
            if resp['code'] != 200:
                LOG.error("CREATE_DOWNLOAD_LINK: %s" % str(resp) )
            if resp['status'] in ["Processing","Uploading"]:
                sleep(3)
                continue
            else:
                print(resp)
                return resp['download_link']
    except Exception as e:
        LOG.error("CREATE_DOWNLOAD_LINK: %s" % str(e) )
        return None
@_one
def do_clear_last_lowbalance_send_time():
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.info("START: %s" % alert_rule)
    #Check if payd ws made and clear las_lowbalance_time
    query(""" update client set last_lowbalance_time=Null where client_id in
    (  select c.client_id
    from client c,c4_client_balance b,client_low_balance_config con where
    c.client_id::text=b.client_id 
    and c.client_id=con.client_id
    and not last_lowbalance_time is null
    and ( 
       (value_type=0 and ((mode=1 and balance::numeric > actual_notify_balance) or 
          (mode=2 and balance::numeric > notify_client_balance)) )   or 
       (value_type=1 and balance::numeric > percentage_notify_balance*allowed_credit/100 ) )  
    and status=true ) """)
    #zero balance too clear if paid
    query(""" update client c set zero_balance_notice_last_sent = Null,zero_balance_notice_time=0 where client_id in
( select  c.client_id from client c,c4_client_balance b,client_low_balance_config l
         where c.client_id::text=b.client_id and c.client_id =l.client_id
    and status and zero_balance_notice 
    and not zero_balance_notice_last_sent is null and
    ( (mode=1 and balance::numeric > 0)
    or
      (mode=2 and balance::numeric > allowed_credit)
    )
)"""     )    

@_one
def do_notify_client_balance():
    """
Check every 5 minute for each “active” clients’ current balance and “low
balance” trigger.  If the “current balance” is below the “low balance”
trigger, then send out an alert.Also, there is a “number of time” that we should send in total before payment
or credit is added. Each day, the low balance should be sent once.  The
subsequent notification should be sent on 00:00:00 of the client’s GMT timezone
( default is gmt+0) Notification Setting of client: select
notify_client_balance, low_balance_notice from client; To check if client is
active: Select status from client ;"""
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)

    #query bad clients
    clients = query("""
    select b.client_id,name,payment_term_id,company,allowed_credit,
    balance,notify_client_balance,actual_notify_balance,billing_email,
    finance_email_cc,percentage_notify_balance,value_type,mode
    from client c,c4_client_balance b,client_low_balance_config con where
    c.client_id::text=b.client_id 
    and c.client_id=con.client_id
    and ( (value_type=0 and ((mode=1 and balance::numeric <= actual_notify_balance) or (mode=2 and balance::numeric <= notify_client_balance)))  
    or (value_type=1 and balance::numeric <= percentage_notify_balance*allowed_credit/100 ) )  
    and status and  (last_lowbalance_time is Null or ( last_lowbalance_time < now()
    - interval '24 hour'  and   extract(day from now()- last_lowbalance_time)  < duplicate_days ) )""")
    try:
        templ = query(
            """select lowbalance_subject as subject, lowbalance_content as content,*
    from mail_tmplate""")[0]
    except Exception as e:
        LOG.error('Template table:'+str(e))
    for cl in clients:
        LOG.warning('NOTIFY LOW BALANCE ALERT! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        if cl.payment_term_id:
            try:
                cl.payment_terms = query(
                    "select * from payment_term where payment_term_id=%s" %
                 cl.payment_term_id)[0].name
            except:
                LOG.error('no payment_term table:'+str(e))
        else:
            cl.payment_terms = '{payment_terms}'
        #prepare in template fields mapping
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        cl.company_name = cl.company
        cl.client_name = cl.name
        cl.allow_credit = '%.2f' % float(-cl.allowed_credit)
        cl.credit_limit = cl.allow_credit
        cl.balance =  _f(cl.balance)
        if cl.value_type == 0:
            if cl.mode==1:
                cl.notify_balance =  _f(cl.actual_notify_balance)
            else:
                cl.notify_balance = _f(cl.notify_client_balance)
        else:
            nb = cl.percentage_notify_balance  #-float(cl.percentage_notify_balance)*float(cl.allowed_credit)/100.0
            cl.notify_balance = '%.2f%%' % nb
        subj = process_template(templ.subject, cl)
        cont = process_template(templ.content, cl)
        LOG.debug("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.billing_email, subj, cont))
        if cl.billing_email and '@' in cl.billing_email :
            send_mail('lowbalance_from', cl.billing_email, subj, cont, templ.lowbalance_cc,  1, alert_rule, cl.client_id)
        #make things after send alert
        #times = int(cl.lowbalance_notication_time)+1
        #if cl.notify_client_balance:
        query(
            "update client set last_lowbalance_time=now() where client_id=%s" %
               cl.client_id)
        #else:
        query(
            "update client_low_balance_config set last_alert_time=now() where client_id=%s" %
               cl.client_id)

@_one
def do_notify_zero_balance():
    """
Check every 5 minute for each “active” clients’ current balance and “low
balance” trigger.  If the “current balance” is below 0 for prepay client type
or below  ( negative value of credit ) for postpay client type.

Also, there is a “number of time” that we should send in total before payment
or credit is added. Each day, the low balance should be sent once.  The
subsequent notification should be sent on 00:00:00 of the client’s GMT timezone
( default is gmt+0) Notification Setting of client: select
notify_client_balance, low_balance_notice from client; To check if client is
active: Select status from client ;
Select mode from client ;
Mode = 1 (prepay)
Mode = 2 (postpay)
Select credit from client;"""

    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
      
    clients=query("""select  b.client_id,name,payment_term_id,company,allowed_credit,balance,
    notify_client_balance,actual_notify_balance,billing_email, zero_balance_notice_time,
    percentage_notify_balance,value_type,mode
    from client c,c4_client_balance b,client_low_balance_config l
    where c.client_id::text=b.client_id and c.client_id =l.client_id
    and status and zero_balance_notice and not unlimited_credit and
    ( (mode=1 and balance::numeric <= 0) or
      (mode=2 and balance::numeric <= allowed_credit)
    )
    and (zero_balance_notice_last_sent is null or 
        zero_balance_notice_last_sent < now() - interval '24 hour') """)
    try:
        templ = query(
            """select  zerobalance_content as content, zerobalance_subject as subject,*  
            from mail_tmplate
            """)[0]
    except Exception as e: 
        LOG.error('no template table:'+str(e))
    for cl in clients:
        LOG.warning('NOTIFY ZERO BALANCE ALERT! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        if cl.payment_term_id:
            try:
                cl.payment_terms = query(
                    "select * from payment_term where payment_term_id=%s" %
                    cl.payment_term_id)[0].name
            except:
                LOG.error('no payment_term table:'+str(e))
        else:
            cl.payment_terms = '{payment_terms}'
        #prepare in template fields mapping
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        cl.company_name = cl.company
        cl.client_name = cl.name
        if cl.mode == 2:
            cl.allow_credit = '%.2f' % float(-cl.allowed_credit)
        else:
            cl.allow_credit = '0'
        cl.credit_limit = cl.allow_credit
        cl.balance = _f(cl.balance)
        if cl.mode==1:
            cl.notify_balance=_f(cl.actual_notify_balance)
        else:
            if cl.value_type==0:
                if cl.notify_client_balance:
                    cl.notify_balance = _f(cl.notify_client_balance)
                else:
                    cl.notify_balance = '0'
            else:
                nb = cl.percentage_notify_balance  #-float(cl.percentage_notify_balance)*float(cl.allowed_credit)/100.0
                cl.notify_balance = '%.2f%%' % nb
        subj = process_template(templ.subject, cl)
        cont = process_template(templ.content, cl)
        LOG.info("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.billing_email, subj, cont))
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('zerobalance_from', cl.billing_email,subj, cont, templ.lowbalance_cc,  1, alert_rule, cl.client_id)
                #make things after send alert
                times = int(cl.zero_balance_notice_time)+1
                query("""update client set
                zero_balance_notice_time=%d,
                zero_balance_notice_last_sent='%s'
                where client_id=%s""" %  ( times, str(cl.now), cl.client_id) )
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
@_one
def do_daily_usage_summary():
    """For each client who has “daily usage summary” selected, at the client’s GMT
time zone, we need to send out a daily usage summary mail. """
    # auto_summary_not_zero
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
    tz=get_systz()
    nowh=datetime.now(UTC).hour
    if ((nowh+tz_to_hdelta(tz))  % 24) != 0:
        LOG.info('Skipped time nowh %d tz %s delta %d tz+delta %d' % (nowh, tz, tz_to_hdelta(tz),  ( (nowh+tz_to_hdelta(tz))  % 24 )  ) )
        return
    try:
        templ = query(
            """select auto_summary_subject as subject , auto_summary_content as content,*
            from
        mail_tmplate""")[0] 
        if templ.subject == ''  or  templ.content == '':
            raise Exception('Template auto_summary empty!')
    except Exception as e:
        LOG.error('No template:'+str(e))
        raise
    reportdate=date.today()
    #reporttime=datetime.now(UTC).timetz()
    reporttime=time(0, 0, 0, 0,UTC)
    #if reporttime.hour==0:
    report_end=datetime.combine(reportdate, reporttime)
    report_start=report_end-timedelta(hours=24)
    clients_buy=query("""
select client.client_id, 
daily_balance_send_time_zone,billing_email,client.name,auto_summary_not_zero,mode,
max(balance) as balance,max(allowed_credit) as allowed_credit,
sum(ingress_total_calls) as total_call_buy,
sum(not_zero_calls) as total_not_zero_calls_buy,
sum(ingress_success_calls) as total_success_call_buy,
sum(ingress_bill_time)/60 as total_billed_min_buy,
round(sum(ingress_call_cost),2) as total_billed_amount_buy,
sum(duration) as buy_total_duration,
--sum(egress_success_calls) 
0  as total_success_call_sell,
--sum(egress_total_calls) 
0 as total_call_sell,
--sum(not_zero_calls) as 
0 as total_not_zero_calls_sell,
--sum(egress_bill_time) 
0 as total_billed_min_sell,
-- sum(egress_call_cost_ij) 
0 as total_billed_amount_sell,
-- sum(duration) 
0 as sell_total_duration,
client.*
from cdr_report_detail%s , client, c4_client_balance
where
client.client_id::text=c4_client_balance.client_id and 
client.client_id=ingress_client_id
and client.status and is_auto_summary
group by client.client_id,ingress_client_id,daily_balance_send_time_zone,billing_email,
client.name,auto_summary_not_zero,mode
order by client.client_id;""" % \
                      report_start.strftime("%Y%m%d") )
    clients_sell=query("""
select client.client_id , 
daily_balance_send_time_zone,billing_email,client.name,auto_summary_not_zero,mode,
max(balance) as balance,max(allowed_credit) as allowed_credit,
--sum(ingress_total_calls) 
0 as total_call_buy,
-- sum(not_zero_calls) 
0 as total_not_zero_calls_buy,
-- sum(ingress_success_calls) 
0 as total_success_call_buy,
-- sum(ingress_bill_time) 
0 as  total_billed_min_buy,
-- sum(ingress_call_cost_ij) 
0 as total_billed_amount_buy,
--sum(duration) 
0 as buy_total_duration,
sum(egress_success_calls) as total_success_call_sell,
sum(egress_total_calls) as total_call_sell,
sum(not_zero_calls) as total_not_zero_calls_sell,
sum(egress_bill_time)/60 as total_billed_min_sell,
round(sum(egress_call_cost),2) as total_billed_amount_sell,
sum(duration) as sell_total_duration,
client.*
from cdr_report_detail%s , client, c4_client_balance
where
client.client_id::text=c4_client_balance.client_id and 
client.client_id=egress_client_id
and client.status and is_auto_summary
group by client.client_id,egress_client_id,daily_balance_send_time_zone,billing_email,
client.name,auto_summary_not_zero,mode
order by client.client_id;""" % \
                      report_start.strftime("%Y%m%d") )
    for clb in clients_buy:
        for cls in clients_sell:
            if clb.cient_id == cls.client_id:
                clb.total_success_call_sell = cls.total_success_call_sell
                clb.total_call_sell = cls.total_call_sell
                clb.total_not_zero_calls_sell = cls.total_not_zero_calls_sell
                clb.total_billed_min_sell = cls.total_billed_min_sell
                clb.total_billed_amount_sell = cls.total_billed_amount_sell
                clb.sell_total_duration = cls.sell_total_duration
                cls.client_id = None
                
    clients=clients_buy+clients_sell
    for cl in clients:
        if not cl.client_id:
            continue
        LOG.warning('DAILY USAGE ! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        if not cl.auto_summary_not_zero and cl.total_not_zero_calls_buy == 0  and cl.total_not_zero_calls_sell == 0:
            LOG.warning('Skip auto_summary_not_zero for %s' % cl.client_id)
            continue
        sw=query("select alias from resource where client_id =%s" % cl.client_id)
        cl.switch_alias = ",".join([ x.alias for x in sw])
        cl.company_name = cl.company
        
        b0=query(
            "SELECT * FROM balance_history_actual  WHERE  date = '%s'::date- interval '1 day'\
            AND client_id = %s" % ( report_start.strftime("%Y%m%d"), cl.client_id ) )
        if len(b0)<1:
            LOG.warning('No incoming balanse records for id:%s name:%s' % (cl.client_id,cl.name) )
            continue
        b1=query("SELECT *,balance as actual_balance FROM c4_client_balance \
            WHERE client_id = '%s'" %  cl.client_id  )
        if len(b1)<1:
            LOG.warning('No current balanse records for id:%s name:%s' % (cl.client_id,cl.name) )
            continue
        #raise
        if len(b0)+len(b1) == 0:
            LOG.error('No balanse records for id:%s name:%s' % (cl.client_id,cl.name) )
            continue
        bl=b1[0]
        cl.beginning_balance=_f( b0[0].actual_balance )
        cl.ending_balance=_f( b1[0].actual_balance )
        cl.credit_limit = '%.2f' % float(-cl.allowed_credit)
        rem=float(-cl.allowed_credit) - abs( float( b1[0].actual_balance) )
        if cl.mode == 2 :
            cl.remaining_credit=_f( rem )
        else:
            cl.remaining_credit='0' #'N/A'
        cl.balance = _f(cl.balance)
        cl.client_name=cl.name
        cl.begin_time=report_start.strftime("%Y-%m-%d 00:00:00")
        cl.end_time=report_start.strftime("%Y-%m-%d 23:59:59")
        cl.customer_gmt='+00:00'
        cl.customer_gmt=tz
        #tz=cl.daily_balance_send_time_zone
        #tz=cl.daily_cdr_generation_zone
        #tz=tz if tz else '+00:00'
        #cl.start_date=str(tz_align(reportstart, tz))[0:19]
        #cl.end_date=str(tz_align(reportnow, tz))[0:19]
        cont=process_template(templ.content, cl)
        subj=process_template(templ.subject, cl)
        try:
            if len(b0) and len(b1) and cl.billing_email and '@' in cl.billing_email:
                send_mail('auto_summary_from', cl.billing_email, subj, cont, templ.auto_summary_cc,  2, alert_rule, cl.client_id)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))

@_one
def do_daily_balance_summary():
    """
    For each client who has “daily balance summary” selected, at the client’s
    GMT time zone, we need to send out a daily balance summary mail.
    """
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
    tz=get_systz()
    nowh=datetime.now(UTC).hour
    if ((nowh+tz_to_hdelta(tz))  % 24) != 0:
        LOG.info('Skipped time nowh %d tz %s delta %d tz+delta %d' % (nowh, tz, tz_to_hdelta(tz),  ( (nowh+tz_to_hdelta(tz))  % 24 )  ) )
        return
    try:
        templ = query(
            """select  auto_balance_content as
    content, auto_balance_subject as subject,*  from mail_tmplate""")[0]
    except Exception as e: 
        LOG.error('no template table:'+str(e))
    reportdate=date.today()
    #reporttime = datetime.now(UTC).timetz()
    reporttime=time(0, 0, 0, 0,UTC)
    #if reporttime.hour==0:
    reportdate_start=reportdate-timedelta(hours=24)
    report_start=datetime.combine(reportdate_start, reporttime)
    report_end=report_start+timedelta(hours=23, minutes=59)

    clients=query(
        """select c.client_id,name,company,daily_cdr_generation_zone,balance,allowed_credit,billing_email,mode
 from client c,c4_client_balance b  where status=true and
        c.client_id::text=b.client_id and
        --is_daily_balance_notification--
        is_auto_summary
        group by c.client_id,name,company,daily_cdr_generation_zone,balance,allowed_credit,billing_email,mode
""")
    for cl in clients:
        LOG.warning('NOTIFY DAILY BALANCE SUMMARY! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        
        sw=query("select alias from resource where client_id =%s" % cl.client_id)
        cl.switch_alias = ",".join([ x.alias for x in sw])
        cl.company_name=cl.company
        cl.client_name=cl.name
        cl.current_day=datetime.now(UTC).date()
        cl.current_time=datetime.now(UTC).timetz()
        cl.now=datetime.now(UTC)
        #tz=cl.daily_cdr_generation_zone
        #cl.start_time=str(tz_align(report_start, tz))[0:19]
        cl.start_time=str(report_start)[0:19]
        cl.beginning_of_day=cl.start_time
        cl.end_time=str(report_end)[0:19]
        cl.customer_gmt=tz
        cl.balance = '%.2f' % float(cl.balance)
        b0=query(
            "SELECT * FROM balance_history_actual  WHERE  date = '%s'::date- interval '1 day'\
            AND client_id = %s" % ( report_start.strftime("%Y%m%d"), cl.client_id ) )
        if len(b0)<1:
            continue
        b1=query("SELECT *,balance as actual_balance FROM c4_client_balance \
            WHERE client_id = '%s'" %  cl.client_id  )
        if len(b1)<1:
             LOG.error('No balance records for id:%s name:%s' % (cl.client_id,cl.name) )
             continue
        #raise
        bl=b1[0]
        cl.beginning_balance=_f( b0[0].actual_balance )
        cl.begining_of_day = report_start ##-timedelta(hours=24)
        cl.beginning_of_day_balance=cl.beginning_balance
        cl.ending_balance=_f( b1[0].actual_balance )
        cl.current_balance=cl.ending_balance
        incoming=b0[0].unbilled_incoming_traffic
        outcoming=b0[0].unbilled_outgoing_traffic
        cl.buy_amount=incoming
        cl.sell_amount=outcoming
        cl.client_name=cl.name
        cl.credit_limit = '%.2f' % -float(cl.allowed_credit)
        rem= float(-cl.allowed_credit)-abs( float( b1[0].actual_balance ) )
        if cl.mode == 2 :
            cl.remaining_credit=_f( rem )
        else:
            cl.remaining_credit='0' #'N/A'
        #cl.beginning_of_day_balance='%.2f' % bl.actual_balance
        cl.allowed_credit = '%.2f' % -float(cl.allowed_credit)
        cont=process_template(templ.content, cl)
        subj=process_template(templ.subject, cl)
        #cont=process_template(fake_daily_balance_summary_template, cl)
        #subj=process_template("<p>Daily balance summary for {client_name}</p>", cl)
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('auto_summary_from', cl.billing_email, subj, cont, templ.auto_balance_cc,  8, alert_rule, cl.client_id)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
@_one
def do_daily_cdr_delivery():
    """
    For each client who has “daily CDR delivery” selected, at the client’s GMT
    time zone, we need to send out a daily CDR mail. Instead of including a
    large attachment, it should be a CDR link.

    request POST   with header json
    """
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
    try:
        templ=query('select auto_cdr_subject as subject, auto_cdr_content as content,* from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise Exception('Template send_cdr!')
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise 
    text=''
    fields=query("SELECT field, label FROM daily_cdr_fields WHERE type = 0 ORDER BY id ASC")
    fmap={'Orig Codecs': '18', 'Egress Bill Result': '56', 'Answer Time': '3', 'Time': '0', 'Call Duration': '31', 'Term Code': '70', 'Orig Code Name': '68', 'PDD(ms)': '32', 'Translation ANI': '64', 'Egress Rate ID': '66', 'Egress Rate Type': '62', 'Term DST Number': '21', 'Egress Cost': '49', 'Ingress Client Currency': '42', 'Ring Time(ms)': '33', 'LRN Number': '60', 'Ingress Client Name': '38', 'Term Delay Second': '86', 'Egress DNIS Type': '61', 'Ingress Rate Type': '59', 'Orig Code': '67', 'Term SRC Number': '19', 'Final Route': '78', 'Start Time': '2', 'Ingress Client Bill Time': '43', 'Response To Ingress': '7', 'Ingress Client Rate': '41', 'Ingress Bill Minutes': '57', 'Dynamic Route Name': '82', 'Ingress Client Cost': '45', 'Term Codecs': '28', 'Q850 Cause Code': '107', 'Response From Egress': '6', 'Ingress Rate ID': '39', 'Term IP': '22', 'Term Country': '72', 'Routing Plan Name': '83', 'Orig Delay Second': '85', 'Orig SRC Number': '9', 'Egress Bill Time': '50', 'Orig Country': '69', 'Egress Six Seconds': '54', 'Egress Name': '51', 'Ingress ID': '37', 'Ingress Client Rate Table Name': '39', 'Orig Call Duration': '87', 'Ingress Client Bill Result': '44', 'Static Route Name': '81', 'Egress Bill Minutes': '55', 'Term Call Id': '23', 'Orig DST Number': '11', 'Term Code Name': '71', 'Egress Client Currency': '53', 'Egress Rate': '48', 'Egress Trunk Trace': '75', 'Release Cause': '1', 'Orig Call Id': '13', 'Orig IP': '10', 'Ingress DNIS Type': '58'} ###, 'Orig/Term Release': ''}
    fm=[]
    for f in fields:
        lab=f.label.strip()
        if  lab in fmap:
            fm.append(str( fmap[lab] ) )
        else:
            LOG.warning('CDR field for label "%s" not found' % lab)
    fm.sort()
    flds='0,9,11,41,45'#['Time' , Orig SRC Number, origination_destinatino_number, ingress_billed_duration, ingress_rate, ingress_cost
    if fm and len(fm) > 0:
        flds = ','.join(fm) ###"31,10,37,11,6,67" #",31,82,107,55,48,61,51,86,22,3,"
    reportdate=date.today()
    reporttime = time(datetime.now(UTC).hour, 0, 0)
    #reporttime=time(0, 0, 0, 0, UTC)
    #if reporttime.hour==0:
    reportdate_start=reportdate-timedelta(hours=24)
    report_start=datetime.combine(reportdate_start, reporttime)
    report_end=report_start+timedelta(hours=24)
    unix_start = mktime(report_start.timetuple())
    unix_end = mktime(report_end.timetuple())
    cdr_tab0=query("""select ingress_client_id as id
    from cdr_report_detail  
    where not ingress_client_id is NULL 
    and report_time between '%s'::date - interval '2 day' and '%s' 
    group by ingress_client_id;"""  % (report_start, report_end))
    #cdr_tab1=query("""select egress_client_id as id
    #from cdr_report_detail  
    #where not egress_client_id is NULL 
    #and report_time between '%s'::date - interval '2 day' and '%s' 
    #group by egress_client_id ;"""  % (report_start, report_end))
    for cli in cdr_tab0: #+cdr_tab1:
        cdr_clients=query(""" select * from client 
        where daily_cdr_generation and client_id=%d""" % cli.id)
        for cl in cdr_clients:
            #todo make header
            #tz=cl.daily_cdr_generation_zone
            tz=cl.auto_send_zone
            hr=cl.auto_summary_hour
            nowh=datetime.now(UTC).hour
            LOG.info('now %s tz %s' % (nowh, tz))
            if ((nowh+tz_to_hdelta(tz)-hr)  % 24) != 0:
                continue
            cl.client_name=cl.name
            cl.company_name=cl.company
            cl.begin_time=str(tz_align(report_start, tz))[0:19]
            cl.end_time=str(tz_align(report_end, tz))[0:19]
            cl.current_day=date.today()
            cl.customer_gmt=tz
            cli_tab0=query("""select ingress_client_id as id,ingress_id  as rid,'i' as dir,r.alias from cdr_report_detail d,resource r  
                where not ingress_client_id is NULL and not ingress_id is NULL  and not_zero_calls >0 and d.ingress_id=r.resource_id and r.active and
                report_time between '%s'::date - interval '2 day' and '%s' and ingress_client_id=%d 
                group by alias,ingress_client_id,ingress_id ;"""  % (report_start, report_end, cl.client_id))
            #cli_tab1=query("""select egress_client_id as id,egress_id as rid,'e' as dir ,r.alias from cdr_report_detail  
            #    where not egress_client_id is NULL and
            #    report_time between '%s'::date - interval '2 day' and '%s' and egress_client_id=%d 
            #    group by alias,egress_client_id,egress_id ;"""  % (report_start, report_end, cl.client_id))
            cli_tab=cli_tab0#+cli_tab1
            link=''
            cl.file_name=''
            cl.site_name=''
            cl.trunk_name=''
            for clii in cli_tab:#for all trunks
                if not clii.rid : 
                    continue
                LOG.warning("TRUNK CDR: %d:%s " % (clii.rid,clii.alias) )
                url=create_download_link(unix_start, unix_end, clii.rid)
                if url:
                    cl.file_name = url.split('/')[-1]
                    cl.site_name = url.split('/')[2]
                if not url:#try old style link
                    cl.file_name = 'Send direct link on api error'
                    url=CDR_DOWNLOAD_URL+'/?start=%d&end=%d&%s=%d&field=%s&format=plain' % (unix_start, unix_end, clii.dir,  clii.rid , flds)
                link += '<p><a href="%s">Trunk name %s</a></p>' % (url, clii.alias)
                cl.trunk_name += clii.alias + ' '
            
            if not url:
                LOG.warning('DAILY CDR DELIVERY (EMPTY LINK - NO SEND): %s' % cl.client_id )
                continue
            cl.download_link=link
            LOG.warning('DAILY CDR DELIVERY: %s,url=%s' %
                    (cl.client_id,  cl.download_link) )
            cl.cdr_count=len(cli_tab) # TODO ?? where is it
            
            # file_name,cdr_countcontent = process_template(templ.auto_cdr_content,
            # cl)
            #
            #subj=process_template('DAILY CDR DELIVERY: {client_name},IP:{ip}', cl)
            cont=process_template(templ.content, cl)
            if not cont or cont=='':
                cont=process_template("</p>No template<p><p>{download_link}</p>"+text, cl)
            subj=process_template(templ.subject, cl)
            if not subj or subj=='':
                subj='DAILY CDR DELIVERY (no template)'
            cl.date=date.today()
            cl.time=datetime.now(UTC).timetz()
            cl.now=datetime.now(UTC)
            finance_email=query("select * from system_parameter")[0].finance_email
            to=''
            if cl.billing_email : to = cl.billing_email
            if finance_email : to   += ';'+finance_email
            send_mail('auto_cdr_from', to, subj, cont, templ.auto_cdr_cc,  5, alert_rule, cl.client_id)

@_one
def do_trunk_pending_suspension_notice():
    """
    For each client, at the client’s timezone 00:00:00, we need to check if
    there is any pending rate download and the deadline is to be reached within
    24 hours.

    If so, pls send this email.
Select download_deadline from rate_send_log;
Select client_id , resource_id from rate_send_log_detail
, resource where resource.resource_id = rate_send_log_detail.resource_id
Select * from rate_download_log where client_id = xx and log_detail_id = xx
    """
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
    tz=get_systz()
    nowh=datetime.now(UTC).hour
    if ((nowh+tz_to_hdelta(tz))  % 24) != 0:
        LOG.info('Skipped time nowh %d tz %s delta %d tz+delta %d' % (nowh, tz, tz_to_hdelta(tz),  ( (nowh+tz_to_hdelta(tz))  % 24 )  ) )
        return
    try:
        templ=query('select download_rate_notice_subject as subject,download_rate_notice_content as content,* from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise ('Template send_cdr!')
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise
    #tm=datetime.now(UTC)
    clients=query("""
select d.id,d.log_id,l.download_deadline,l.file as rate_update_file_name,
r.alias as trunk_name,r.resource_id,c.company as company_name,c.billing_email,daily_cdr_generation_zone,
c.client_id
from rate_send_log_detail d, resource r , client c,rate_send_log l
where 
r.resource_id = d.resource_id and c.client_id=r.client_id
and r.active
and d.log_id= l.id
and d.status
and d.download_date is null
and not l.download_deadline is null
and download_deadline - interval '24 hour' < now()
and download_deadline = (select max(download_deadline) from rate_send_log l1,rate_send_log_detail d1 
         where l1.id=d1.log_id and d1.resource_id=r.resource_id 
                 group by d1.resource_id)
and l.is_email_alert
--and c.client_id=75
--group by l.id,d.id,d.log_id,l.download_deadline,l.file,r.alias,r.resource_id,c.company,c.billing_email,daily_cdr_generation_zone,c.client_id
""" )
    for cl in clients:
        LOG.warning('TRUNK NOTICE! trunk:%s, company:%s' %
                    (cl.trunk_name, cl.company_name))

        cl.date=date.today()
        cl.time=datetime.now(UTC).timetz()
        cl.now=datetime.now(UTC)
        cl.download_time=cl.download_deadline
        cl.rate_download_link=cl.rate_update_file_name
        try:
            cont=process_template(templ.content, cl)
        except:
            cont=process_template("""no template download_rate_notice_content!
company_name:{company_name}
trunk_name:{trunk_name}
rate_download_deadline:{rate_download_deadline}
rate_update_file_name:{rate_update_file_name}
""", cl)
            #cont.replace('is suspecded', 'will suspecded')
        try:
            subj=process_template(templ.subject, cl)
        except:       
            subj=process_template('TRUNK {trunk_name}, company {company_name}', cl)        
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('rate_watch_alert_email_from', cl.billing_email, subj, cont, '',  35, alert_rule, cl.client_id)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))

@_one
def do_trunk_is_suspended_notice():
    """
    For each client, at the client’s timezone 00:00:00, we need to check if
    there is any pending rate download and the deadline is passed. If so, pls
send this email AND “disable this relevant trunk.” Select download_deadline
from rate_send_log; Select client_id , resource_id from rate_send_log_detail
, resource where resource.resource_id = rate_send_log_detail.resource_id
Select * from rate_download_log where client_id = xx and log_detail_id = xx
    """
    alert_rule=sys._getframe().f_code.co_name ; 
    LOG.warning("START: %s" % alert_rule)
    tz=get_systz()
    nowh=datetime.now(UTC).hour
    if ((nowh+tz_to_hdelta(tz))  % 24) != 0:
        LOG.info('Skipped time nowh %d tz %s delta %d tz+delta %d' % (nowh, tz, tz_to_hdelta(tz),  ( (nowh+tz_to_hdelta(tz))  % 24 )  ) )
        return
    clients=query("""
select d.id,d.log_id,l.download_deadline,l.file as rate_update_file_name,
r.alias as trunk_name,r.resource_id,c.company as company_name,c.billing_email,daily_cdr_generation_zone,
c.client_id
from rate_send_log_detail d, resource r , client c,rate_send_log l
where 
r.resource_id = d.resource_id and c.client_id=r.client_id
and r.active
and d.log_id= l.id
and d.download_date is null
and d.status
and not l.download_deadline is null
and l.download_deadline < now() - interval '1 day'
and download_deadline = (select max(download_deadline) from rate_send_log l1,rate_send_log_detail d1 
         where l1.id=d1.log_id and d1.resource_id=r.resource_id 
                 group by d1.resource_id)
and l.is_email_alert
--and c.client_id=75
--group by l.id,d.id,d.log_id,l.download_deadline,l.file,r.alias,r.resource_id,c.company,c.billing_email,daily_cdr_generation_zone,c.client_id
""")
    try:
        templ=query('select no_download_rate_subject as subject,no_download_rate_content as content from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise ('Template send_cdr!')
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise
    for cl in clients:
        LOG.warning('TRUNK SUSPENDED! %s, company %s' %
                    (cl.trunk_name, cl.company_name))
        cl.date=date.today()
        cl.time=datetime.now(UTC).timetz()
        cl.effective_date=datetime.now(UTC)
        cl.download_time=cl.download_deadline
        cl.rate_download_link=cl.rate_update_file_name
        try:
          cont=process_template(templ.content, cl)
        except:
            #cont=process_template(fake_trunk_pending_suspension_notice_template, cl)
            cont=process_template("""no template download_rate_notice_content!
nano
""", cl)
        try:
            subj=process_template(templ.subject, cl)
        except: 
            subj=process_template('TRUNK SUSPENDED {trunk_name}, company {company_name}', cl)        
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('no_download_rate_from', cl.billing_email, subj, cont, '',  35, alert_rule, cl.client_id)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
        #do trunk blocking
        cl.now = datetime.now(UTC)
        try:
            query(
            "update rate_send_log_detail set status=false and error='trunk was blocked by dnl_ad daemon' where id=%s" % cl.id )
            query(
            "update resource set active=false,disable_by_alert=true,update_at='%s',update_by='dnl_ad' where resource_id=%s" %
              (cl.now, cl.resource_id))
            try:
                rollback="update resource set active=true,disable_by_alert=false,update_at='%s',update_by='dnl_ad' where resource_id=%s" % (cl.now, cl.resource_id )
                query(""" insert into modif_log( time ,module,type,name ,detail,rollback,rollback_msg,rollback_flg,rollback_extra_info )
                values(now(),'Trunk',2,'dnl_ad','Trunk Name:%s',$$%s$$,'Modify Trunk [%s] operation have been rolled back!',Null,'{"type":2}')
                """ % (cl.trunk_name, rollback, cl.trunk_name)
                )
            except Exception as e:
                LOG.error('cannot insert modif_log:'+str(e))
        except Exception as e:
            LOG.error('cannot update resource table:'+str(e))
            

def fifteen_minute_job():
    "call this each 15 minutes"
    LOG.warning('5 MINUTES JOB AWAKEN!')
    do_notify_client_balance()
    do_notify_zero_balance()

def daily_job():
    "processing all daily report"
    LOG.warning('DAILY JOB AWAKEN!')
    do_daily_usage_summary()
    do_daily_balance_summary()
    do_daily_cdr_delivery()
    do_trunk_pending_suspension_notice()
    do_trunk_is_suspended_notice()
    
class Daemon(object):
    """
    Subclass Daemon class and override the run() method.
    """
    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
 
    def daemonize(self):
        """
        Deamonize, do double-fork magic.
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent.
                sys.exit(0)
        except OSError as e:
            message = "Fork #1 failed: {}\n".format(e)
            sys.stderr.write(message)
            sys.exit(1)
 
        # Decouple from parent environment.
        os.chdir("/")
        os.setsid()
        os.umask(0)
 
        # Do second fork.
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent.
                sys.exit(0)
        except OSError as e:
            message = "Fork #2 failed: {}\n".format(e)
            sys.stderr.write(message)
            sys.exit(1)
 
        LOG.info('deamon going to background, PID: {}'.format(os.getpid()))
 
        # Redirect standard file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(self.stdin, 'r')
        so = open(self.stdout, 'a+')
        se = open(self.stderr, 'a+')
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
 
        # Write pidfile.
        pid = str(os.getpid())
        open(self.pidfile,'w+').write("{}\n".format(pid))
 
        # Register a function to clean up.
        atexit.register(self.delpid)
 
    def delpid(self):
        os.remove(self.pidfile)
 
    def start(self):
        """
        Start daemon.
        """
        # Check pidfile to see if the daemon already runs.
        try:
            minor=open('.git/ORIG_HEAD','rt').read().strip()
        except:
            minor=''
        build = datetime.fromtimestamp(os.path.getmtime('dnl_ad.py')).date()
        start = datetime.now()
        ver = query("select id, program_name from version_information where program_name='dnl_ad'")
        if len (ver):
            query("""update version_information set major_ver='V%s', minor_ver='%s',
                   build_date = '%s', start_time='%s'
                   where program_name='dnl_ad' """ % (__version__,minor,str(build),str(start)))
        else:
            query("""insert into version_information(program_name,major_ver,minor_ver,build_date,start_time)
                values('dnl_ad','V%s', '%s','%s', '%s') """ % (__version__,minor,str(build),str(start)))
        
        try:
            pf = open(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
 
        if pid:
            message = "Pidfile {} already exist. Daemon already running?\n".format(self.pidfile)
            sys.stderr.write(message)
            sys.exit(1)
 
        # Start daemon.
        self.daemonize()
        self.run()
 
    def status(self):
        """
        Get status of daemon.
        """
        try:
            pf = open(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            message = "There is not PID file. Daemon already running?\n"
            sys.stderr.write(message)
            sys.exit(1)
 
        try:
            procfile = open("/proc/{}/status".format(pid), 'r')
            procfile.close()
            message = "There is a process with the PID {}\n".format(pid)
            sys.stdout.write(message)
        except IOError:
            message = "There is not a process with the PID {}\n".format(self.pidfile)
            sys.stdout.write(message)
 
    def stop(self):
        """
        Stop the daemon.
        """
        # Get the pid from pidfile.
        try:
            pf = open(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError as e:
            message = str(e) + "\nDaemon not running?\n"
            sys.stderr.write(message)
            sys.exit(1)
 
        # Try killing daemon process.
        try:
            os.kill(pid, SIGTERM)
            sleep(1)
        except OSError as e:
            print(str(e))
            sys.exit(1)
 
        try:
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)
        except IOError as e:
            message = str(e) + "\nCan not remove pid file {}".format(self.pidfile)
            sys.stderr.write(message)
            sys.exit(1)
 
    def restart(self):
        """
        Restart daemon.
        """
        self.stop()
        sleep(1)
        self.start()
 
    def run(self):
        """
        You should override this method when you subclass Daemon.
        It will be called after the process has been daemonized by start() or restart().
 
        Example:
 
        class MyDaemon(Daemon):
            def run(self):
                while True:
                    time.sleep(1)
        """
                
 
class MyDaemon(Daemon):
    def run(self):
        "main cycle"
        
        LOG.warning('DNL AD started!')
        if LOGLEVEL == logging.DEBUG:
            schedule.every(1).minutes.do(fifteen_minute_job)
            schedule.every(1).minutes.do(daily_job)
        else:
            schedule.every(1).minutes.do(do_clear_last_lowbalance_send_time)
            
            schedule.every(5).minutes.do(do_notify_client_balance)
            schedule.every(5).minutes.do(do_notify_zero_balance)
            
            schedule.every().hours.at(':00').do(do_daily_usage_summary)
            schedule.every().hours.at(':00').do(do_daily_balance_summary)
            schedule.every().hours.at(':00').do(do_daily_cdr_delivery)
            schedule.every().hours.at(':00').do(do_trunk_pending_suspension_notice)
            schedule.every().hours.at(':00').do(do_trunk_is_suspended_notice)
            
        #initial one run;
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                LOG.error('Unexpected: %s! \n Will wait 2 min...' % str(e))
                sleep(120)
            finally:
                sleep(1)

if __name__ == "__main__":
    daemon = MyDaemon(PIDFILE)
    if len(sys.argv) == 2:
        LOG.info('{} {}'.format(sys.argv[0],sys.argv[1]))
        print ('start')
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif 'status' == sys.argv[1]:
            daemon.status()
        elif 'zap' == sys.argv[1]:
            daemon.delpid()
        else:
            print ("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        LOG.warning('show cmd deamon usage')
        print ("Usage: {} start|stop|restart".format(sys.argv[0]))
        sys.exit(2)
        
        
        

