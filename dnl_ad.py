#!/usr/bin/python
# -*- coding: UTF-8 -*-
import logging

#configuration
CONNECTION_STRING = "host='localhost' dbname='class4_pr' user='postgres'"
CDR_DOWNLOAD_URL ="http://192.99.10.113:8888"
PIDFILE = '/var/tmp/dnl_ad.pid'
LOGFILE = '/var/tmp/dnl_ad.log'
LOGLEVEL = logging.WARN
#/configuration

from daemon import runner
import psycopg2
import psycopg2.extras
import smtplib
import sys
import os
import gzip

import logging.handlers
from logging import config
import traceback
from time import sleep, gmtime, mktime
from datetime import date, datetime, timedelta, time
from pytz import UTC
from collections import defaultdict
import pytz
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib2
import json
#local imports
import schedule
from templates import *

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
    sign=-1 if off[1]=='-' else 1
    return sign*hdelta 
    
def tz_align(d, off):
    """Return datetime, converted by given offset.Time zone info from""" \
        """string -12:00 ."""
    return d+tz_to_delta(off)

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
            'formatter': 'verbose',
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

def get_mail_params(fr):
    """Get parameters for sending mail from system configuration table."""
    try:
        p = query("select * from system_parameter")[0]
    except Exception as e:
        LOG.error("system_parameters not ready: %s", str(e)+traceback.format_exc())
        raise e
    if  p.__dict__.has_key(fr):
       frm=p.__dict__[fr]
    else:
        frm=fr
    return (
        (p.smtphost, p.smtpport, p.emailusername, \
         p.emailpassword, frm)
    )

def cleanhtml(raw_html):
  cleanr = re.compile('<.*?>')
  cleantext = re.sub(cleanr, '', raw_html)
  return cleantext

  
def send_mail(from_field, to, subject, text, cc=None):
    """sending email."""
    (host, port, user, passw, mfrom) = get_mail_params(from_field)
    if mfrom == 'novvvster@gmail.com': #'SEND_MAIL == 2:
        subject = 'DEBUG: mail for %s %s' % (to, subject)
        to = 'novvvster@gmail.com'
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = mfrom
    msg['To'] = to
    msg['CC'] = cc
    txt = MIMEText(text, 'html')
    msg.attach(txt)
    #LOG.info(msg.as_string())
        
    if SEND_MAIL:
        try:
            server = smtplib.SMTP(host+':'+port)
            server.ehlo()
            if port == '587':
                server.starttls()
            server.login(user, passw)
            for t in to.split(';'):
                try:
                    server.sendmail(mfrom, t, msg.as_string())
                except:
                    LOG.error('MAIL ERR: to: %t' % t)
            server.quit()
            LOG.warning('MAIL SENT: from: %s to: subj: %s %s body:%s' % (mfrom, to, subject,  cleanhtml(text)))
        except Exception as e:
            LOG.error("sending mail: %s", str(e))

def query(sql, all=True):
    """Call postgresql query, return record array."""
    def _res(row, descr):
        "Make one record as class Rec"
        class Rec:
            pass
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
            if hasattr(env, 'has_key') and env.has_key(f):
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
            select = data[0].__dict__.keys()
        for row in data:
            text += '<tr>'
            for f in select:
                text += '<td>%s</td>' % row.__dict__[f]
            text += '</tr>'
        text += '</table>'
        return text
    else:
        return '<p>-------</p>'


def do_notify_client_balance():
    u"""
Check every 5 minute for each “active” clients’ current balance and “low
balance” trigger.  If the “current balance” is below the “low balance”
trigger, then send out an alert.Also, there is a “number of time” that we should send in total before payment
or credit is added. Each day, the low balance should be sent once.  The
subsequent notification should be sent on 00:00:00 of the client’s GMT timezone
( default is gmt+0) Notification Setting of client: select
notify_client_balance, low_balance_notice from client; To check if client is
active: Select status from client ;"""

    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
#Check if payd ws made and clear las_lowbalance_time
    query(""" update client set last_lowbalance_time=Null where client_id in
    (  select c.client_id
        from client c,c4_client_balance b,client_low_balance_config con where
    c.client_id::text=b.client_id 
	and c.client_id=con.client_id
	and ( (value_type=0 and balance::numeric > notify_client_balance)  
    or (value_type=1 and balance::numeric > percentage_notify_balance*allowed_credit/100 ) )  
	and status=true ) """)
    #query bad clients
    clients = query("""
        select b.client_id,name,payment_term_id,company,allowed_credit,
	balance,notify_client_balance,billing_email,finance_email_cc,percentage_notify_balance,value_type
        from client c,c4_client_balance b,client_low_balance_config con where
        c.client_id::text=b.client_id 
	and c.client_id=con.client_id
	and ( (value_type=0 and balance::numeric <= notify_client_balance)  
or (value_type=1 and balance::numeric < percentage_notify_balance*allowed_credit/100 ) )  
	and status and  (last_lowbalance_time is Null or last_lowbalance_time < now()
        - interval '24 hour') """)
    try:
        templ = query(
            """select lowbalance_subject as subject, lowbalance_content as content
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
            cl.payment_terms = '(default)'
        #prepare in template fields mapping
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        cl.company_name = cl.company
        cl.allow_credit = '%.2f' % float(-cl.allowed_credit)
        cl.balance = '%.2f' % float(cl.balance)
	if cl.value_type == 0:
        	cl.notify_balance = '$%.2f' % float(cl.notify_client_balance)
	else:
		nb = cl.percentage_notify_balance  #-float(cl.percentage_notify_balance)*float(cl.allowed_credit)/100.0
		cl.notify_balance = '%.2f%%' % nb
        subj = process_template(templ.subject, cl)
        cont = process_template(templ.content, cl)
        LOG.debug("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.billing_email, subj, cont))
        try:
            if cl.billing_email and '@' in cl.billing_email :
                send_mail('fromemail', cl.billing_email, subj, cont, cl.finance_email_cc)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
        #make things after send alert
        #times = int(cl.lowbalance_notication_time)+1
        if cl.notify_client_balance:
		query(
            "update client set last_lowbalance_time=now() where client_id=%s" %
               cl.client_id)
	else:
		query(
            "update client_low_balance_config set last_alert_time=now() where client_id=%s" %
               cl.client_id)
		


def do_notify_zero_balance():
    u"""
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

    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
    #clear if paid
    query(""" update client c set zero_balance_notice_last_sent = Null where client_id in
( select  c.client_id from client c,c4_client_balance b
  where c.client_id::text=b.client_id and not unlimited_credit 
    and status and zero_balance_notice and
    ( (balance::numeric <= 0  and mode=1 )
    or
      (balance::numeric < allowed_credit and mode=2)
    )
)"""     )
      
    clients1=query("""select  b.client_id,name,payment_term_id,company,allowed_credit,balance,
        notify_client_balance,billing_email, zero_balance_notice_time
        from client c,c4_client_balance b
         where c.client_id::text=b.client_id and balance::numeric <= 0
         and status=true and mode=1 and zero_balance_notice and not unlimited_credit
         and zero_balance_notice_last_sent < now() - interval '24 hour' """)
    clients2=query("""select  b.client_id,name,payment_term_id,company,allowed_credit,balance,
        notify_client_balance,billing_email,zero_balance_notice_time
        from client c,c4_client_balance b
         where c.client_id::text=b.client_id and balance::numeric < allowed_credit
         and status=true and mode=2 and zero_balance_notice and not unlimited_credit
         and zero_balance_notice_last_sent < now() - interval '24 hour' """)
    clients = clients1+clients2
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
            cl.payment_terms = '(default)'
        #prepare in template fields mapping
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        cl.company_name = cl.company
        cl.allow_credit = '%.2f' % float(-cl.allowed_credit)
        cl.balance = '%.2f' % float(cl.balance)
	if not cl.notify_client_balance:
		cl.notify_balance=''
	else:
        	cl.notify_balance = cl.notify_client_balance
        subj = process_template(templ.subject, cl)
        cont = process_template(templ.content, cl)
        LOG.info("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.billing_email, subj, cont))
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail(templ.zerobalance_from, cl.billing_email,subj, cont)
                #make things after send alert
                times = int(cl.zero_balance_notice_time)+1
                query("""update client set
                zero_balance_notice_time=%d,
                zero_balance_notice_last_sent='%s'
                where client_id=%s""" %  ( times, str(cl.now), cl.client_id) )
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
            
def do_daily_usage_summary():
    u"""For each client who has “daily usage summary” selected, at the client’s GMT
time zone, we need to send out a daily usage summary mail. """
    
    LOG.info("START: %s" % sys._getframe().f_code.co_name)
    try:
        templ = query(
            """select auto_summary_subject as subject , auto_summary_content as content
            from
        mail_tmplate""")[0] 
        if templ.subject == ''  or  templ.content == '':
            raise 'Template auto_summary empty!'
    except Exception as e:
        LOG.error('No template:'+str(e))
        raise
    reportdate=date.today()
    reporttime=datetime.now(UTC).timetz()
    #if reporttime.hour==0:
    reportnow=datetime.combine(reportdate, reporttime)
    reportstart=reportnow-timedelta(hours=24)
    clients=query("""
select ingress_client_id, 
daily_balance_send_time_zone,billing_email,client.name,
--alias as switch_alias,
max(balance) as balance,max(allowed_credit) as allowed_credit,
sum(ingress_total_calls) as total_call_buy,
sum(not_zero_calls) as total_not_zero_calls_buy,
sum(ingress_success_calls) as ingress_success_calls,
sum(ingress_success_calls) as total_success_call_buy,
sum(egress_success_calls) as total_success_call_sell,
sum(ingress_bill_time) as total_billed_min_buy,
sum(ingress_call_cost_ij) as total_billed_amount_buy,
sum(egress_total_calls) as total_call_sell,
sum(not_zero_calls) as total_not_zero_calls_sell,
sum(egress_bill_time) as total_billed_min_sell,
sum(egress_call_cost_ij) as total_billed_amount_sell,
sum(duration) as buy_total_duration,
sum(intra_duration) as sell_total_duration,
client.*
from cdr_report_detail%s , client, c4_client_balance
--,resource
where
client.client_id::text=c4_client_balance.client_id and 
client.client_id=ingress_client_id
--and product_rout_id=resource_id
and client.status and is_auto_summary
group by client.client_id,ingress_client_id,daily_balance_send_time_zone,billing_email,client.name
--,alias
order by ingress_client_id;""" % \
                      reportstart.strftime("%Y%m%d") )
    for cl in clients:
        LOG.warning('DAILY USAGE ! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        sw=query("select alias from resource where client_id =%s" % cl.client_id)
        cl.switch_alias = ",".join([ x.alias for x in sw])
        cl.company_name = cl.company
        cl.credit_limit = '%.2f' % float(-cl.allowed_credit)
        cl.remaining_credit='%.2' % -cl.allowed_credit if cl.balance   > 0 else -cl.allowed_credit+cl.balance
        cl.balance = '%.2f' % float(cl.balance)
        cl.client_name=cl.name
        cl.begin_time='00:00'
        cl.end_time='23:59'
        cl.customer_gmt='UTC'
        tz=cl.daily_balance_send_time_zone
        #tz=cl.daily_cdr_generation_zone
        nowh=datetime.now(UTC).hour
        if ((nowh-tz_to_hdelta(tz))  % 24) != 0:
                continue
        tz=tz if tz else '+00:00'
        cl.start_date=str(tz_align(reportstart, tz))[0:19]
        cl.end_date=str(tz_align(reportnow, tz))[0:19]
        cl.customer_gmt=tz
        cont=process_template(templ.content, cl)
        subj=process_template(templ.subject, cl)
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('fromemail', cl.billing_email, subj, cont)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))


def do_daily_balance_summary():
    u"""
    For each client who has “daily balance summary” selected, at the client’s
    GMT time zone, we need to send out a daily balance summary mail.
    """
    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
    try:
        templ = query(
            """select  auto_balance_content as
    content, auto_balance_subject as subject  from mail_tmplate""")[0]
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
        """select c.client_id,name,company,daily_cdr_generation_zone,balance,allowed_credit,billing_email
 from client c,c4_client_balance b  where status=true and
        c.client_id::text=b.client_id and
        is_daily_balance_notification
	group by c.client_id,name,company,daily_cdr_generation_zone,balance,allowed_credit,billing_email
""")
    for cl in clients:
        LOG.warning('NOTIFY DAILY BALANCE SUMMARY! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        sw=query("select alias from resource where client_id =%s" % cl.client_id)
        cl.switch_alias = ",".join([ x.alias for x in sw])
	cl.company_name=cl.company

        cl.date=date.today()
        cl.time=datetime.now(UTC).timetz()
        cl.now=datetime.now(UTC)
        tz=cl.daily_cdr_generation_zone
        nowh=datetime.now(UTC).hour
        if ((nowh-tz_to_hdelta(tz))  % 24) != 0:
                continue
        cl.start_time=str(tz_align(report_start, tz))[0:19]
        cl.beginning_of_day=cl.start_time
        cl.end_time=str(tz_align(report_end, tz))[0:19]
        cl.customer_gmt=tz
	cl.balance = '%.2f' % float(cl.balance)
        
        b0=query(
            "SELECT * FROM balance_history_actual  WHERE  date = '%s'::date- interval '1 day'\
            AND client_id = %s" % ( report_start.strftime("%Y%m%d"), cl.client_id ) )
	if len(b0)<1:
		continue
        b1=query(
            "SELECT * FROM balance_history_actual  WHERE  date = '%s'\
            AND client_id = %s" % ( report_start.strftime("%Y%m%d"), cl.client_id ) )
        if len(b1)<1:
             LOG.error('No balanse records for id:%s name:%s' % (cl.client_id,cl.name) )
             continue
		#raise
        bl=b1[0]
	cl.beginning_balance='%.2f' % b0[0].actual_balance
	cl.ending_balance='%.2f' % b1[0].actual_balance
	cl.buy_amount=bl.unbilled_incoming_traffic
	cl.sell_amount=bl.unbilled_outgoing_traffic
        cl.client_name=cl.name
        cl.credit_limit = '%.2f' % -float(cl.allowed_credit)
        
	if bl.actual_balance   > 0 :
		rem=cl.allowed_credit
	else:
		rem= cl.allowed_credit-bl.actual_balance

        cl.remaining_credit = '%.2f' % rem
        cl.beginning_of_day_balance='%.2f' % bl.actual_balance
        cl.allowed_credit = '%.2f' % -float(cl.allowed_credit)
        cont=process_template(templ.content, cl)
        subj=process_template(templ.subject, cl)
        #cont=process_template(fake_daily_balance_summary_template, cl)
        #subj=process_template("<p>Daily balance summary for {client_name}</p>", cl)
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('fromemail', cl.billing_email, subj, cont)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))

def do_daily_cdr_delivery():
    u"""
    For each client who has “daily CDR delivery” selected, at the client’s GMT
    time zone, we need to send out a daily CDR mail. Instead of including a
    large attachment, it should be a CDR link.

    request POST   with header json
    http://192.99.10.113:8000/api/v1.0/show_query_cdr
{
  "switch_ip" :  "192.99.10.113",
  "query_key":
"33ZvPfHH0ukPpMCl6NZZ4oWQsiySJWtLVvedsPBBGGiUwzuBPjerOXSS6shfzXNzw5ajvlMZHAUu0bozyc776mN0YLAyQZHnVupa" }
    """
    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
    try:
        templ=query('select download_cdr_subject as subject,download_cdr_content as content from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise 'Template send_cdr!'
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise
    reportdate=date.today()
    reporttime = time(datetime.now(UTC).hour, 0, 0)
    #reporttime=time(0, 0, 0, 0, UTC)
    #if reporttime.hour==0:
    reportdate_start=reportdate-timedelta(hours=24)
    report_start=datetime.combine(reportdate_start, reporttime)
    report_end=report_start+timedelta(hours=24)
    unix_start = mktime(report_start.timetuple())
    unix_end = mktime(report_end.timetuple())
    cdr_tab0=query("""select ingress_client_id as id,ingress_id  as rid,'i' as dir from cdr_report_detail  
    where not ingress_client_id is NULL and
    report_time between '%s' and '%s' group by ingress_client_id,ingress_id ;"""  % (report_start, report_end))
    cdr_tab1=query("""select egress_client_id as id,egress_id as rid,'e' as dir from cdr_report_detail  
    where not egress_client_id is NULL and
    report_time between '%s' and '%s' group by egress_client_id,egress_id ;"""  % (report_start, report_end))
    for cli in cdr_tab0+cdr_tab1:
        cdr_clients=query(""" select * from client 
        where client_id=%d""" % cli.id)
        for cl in cdr_clients:
            #todo make header
            tz=cl.daily_cdr_generation_zone
            nowh=datetime.now(UTC).hour
            if ((nowh-tz_to_hdelta(tz))  % 24) != 0:
                continue
            cl.client_name=cl.company
            cl.begin_time=str(tz_align(report_start, tz))[0:19]
            cl.end_time=str(tz_align(report_end, tz))[0:19]
            cl.customer_gmt=tz
            cl.download_link=CDR_DOWNLOAD_URL+'/?start=%d&end=%d&%s=%d' % (unix_start, unix_end, cli.dir,  cli.rid )
            LOG.warning('DAILY CDR DELIVERY: %s,RID:%s,url=%s' %
                     (cl.client_id, cli.rid, cl.download_link) )
            cl.cdr_count=0 # TODO ?? where is it
            cl.site_name='THE SITE NAME'
            cl.file_name='None'
            # file_name,cdr_countcontent = process_template(templ.auto_cdr_content,
            # cl)
            #cont=process_template(fake_daily_cdr_usage_template, cl)
            #subj=process_template('DAILY CDR DELIVERY: {client_name},IP:{ip}', cl)
            cont=process_template(templ.content, cl)
            subj=process_template(templ.subject, cl)
            cl.date=date.today()
            cl.time=datetime.now(UTC).timetz()
            cl.now=datetime.now(UTC)
            try:
                if cl.billing_email and '@' in cl.billing_email:
                    send_mail('fromemail', cl.billing_email, subj, cont)
            except Exception as e:
                LOG.error('cannot sendmail:'+str(e))

def do_trunk_pending_suspension_notice():
    u"""
    For each client, at the client’s timezone 00:00:00, we need to check if
    there is any pending rate download and the deadline is to be reached within
    24 hours.

    If so, pls send this email.
Select download_deadline from rate_send_log;
Select client_id , resource_id from rate_send_log_detail
, resource where resource.resource_id = rate_send_log_detail.resource_id
Select * from rate_download_log where client_id = xx and log_detail_id = xx
    """
    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
    try:
        templ=query('select download_rate_notice_subject as subject,download_rate_notice_content as content from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise 'Template send_cdr!'
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise
    tm=datetime.now(UTC)
    clients=query("""
select l.id,l.download_deadline as rate_download_deadline,l.file as rate_update_file_name,
r.alias as trunk_name,c.company as company_name,c.billing_email,daily_cdr_generation_zone
from rate_send_log_detail d, resource r , client c,rate_send_log l
where r.resource_id = d.resource_id and c.client_id=r.client_id
and d.log_id= l.id and download_deadline - interval '24 hour' < now()
and l.is_email_alert
group by
l.id,l.download_deadline,l.file,r.alias,r.resource_id,c.company,c.billing_email,daily_cdr_generation_zone
""" )
    for cl in clients:
        LOG.warning('TRUNK NOTICE! trunk:%s, company:%s' %
                    (cl.trunk_name, cl.company_name))

        cl.date=date.today()
        cl.time=datetime.now(UTC).timetz()
        cl.now=datetime.now(UTC)
        
        tz=cl.daily_cdr_generation_zone
        nowh=datetime.now(UTC).hour
        if ((nowh-tz_to_hdelta(tz))  % 24) != 0:
                continue
        
        try:
            cont=process_template(templ.content, cl)
        except:
            cont=process_template(fake_trunk_pending_suspension_notice_template, cl)
            cont.replace('is suspecded', 'will suspecded')
        try:
            subj=process_template(templ.subject, cl)
        except:       
            subj=process_template('TRUNK NOTICE! trunk:{trunk_name}, company:{company_name}', cl)        
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('fromemail', cl.billing_email, subj, cont)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))


def do_trunk_is_suspended_notice():
    """
    For each client, at the client’s timezone 00:00:00, we need to check if
    there is any pending rate download and the deadline is passed. If so, pls
send this email AND “disable this relevant trunk.” Select download_deadline
from rate_send_log; Select client_id , resource_id from rate_send_log_detail
, resource where resource.resource_id = rate_send_log_detail.resource_id
Select * from rate_download_log where client_id = xx and log_detail_id = xx
    """
    LOG.debug("START: %s" % sys._getframe().f_code.co_name)
    clients=query("""
select l.id,l.download_deadline as rate_download_deadline,l.file as rate_update_file_name,
r.alias as trunk_name,r.resource_id,c.company as company_name,c.billing_email,daily_cdr_generation_zone
from rate_send_log_detail d, resource r , client c,rate_send_log l
where 
r.resource_id = d.resource_id and c.client_id=r.client_id 
and r.active
and d.log_id= l.id and download_deadline < now()
and l.is_email_alert
group by 
l.id,l.download_deadline,l.file,r.alias,r.resource_id,c.company,c.billing_email,daily_cdr_generation_zone
""")
    try:
        templ=query('select no_download_rate_subject as subject,no_download_rate_content as content from mail_tmplate')[0]
        if templ.subject == '' or templ.content == '':
            raise 'Template send_cdr!'
    except Exception as e:
        LOG.error('no template table:'+str(e))
        raise
    for cl in clients:
        LOG.warning('TRUNK SUSPENDED! trunk:%s, company:%s' %
                    (cl.trunk_name, cl.company_name))
                    
        cl.date=date.today()
        cl.time=datetime.now(UTC).timetz()
        cl.now=datetime.now(UTC)
        
        tz=cl.daily_cdr_generation_zone
        nowh=datetime.now(UTC).hour
        if ((nowh-tz_to_hdelta(tz))  % 24) != 0:
                continue
        
        try:
          cont=process_template(templ.content, cl)
        except:
            cont=process_template(
            fake_trunk_pending_suspension_notice_template, cl)
        try:
            subj=process_template(templ.subject, cl)
        except: 
            subj=process_template('TRUNK SUSPENDED! trunk:{trunk_name}, company:{company_name}', cl)        
        try:
            if cl.billing_email and '@' in cl.billing_email:
                send_mail('fromemail', cl.billing_email, subj, cont)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
        #do trunk blocking
        query(
            "update resource set active=false,disable_by_alert=true,update_at='%s',update_by='dnl_ad' where resource_id=%s" %
              (cl.now, cl.resource_id))

def fifteen_minute_job():
    "call this each 15 minutes"
    do_notify_client_balance()
    do_notify_zero_balance()

def daily_job():
    "processing all daily report"
    do_daily_usage_summary()
    do_daily_balance_summary()
    do_daily_cdr_delivery()
    do_trunk_pending_suspension_notice()
    do_trunk_is_suspended_notice()

class App():
    
    "Establish application instance"
    
    def __init__(self):
        self.stdin_path='/dev/null'
        self.stdout_path='/dev/tty'
        self.stderr_path='/dev/tty'
        self.pidfile_path=PIDFILE
        self.pidfile_timeout=5

    def run(self):
        "main cycle"
        if LOGLEVEL == logging.DEBUG:
            schedule.every(1).minutes.do(fifteen_minute_job)
            schedule.every(1).minutes.do(daily_job)
        else:
            schedule.every(60).minutes.do(fifteen_minute_job)
            schedule.every().hours.at(':00').do(daily_job)
        #initial one run;
        while True:
            try:
                schedule.run_pending()
            except Exception as e:
                LOG.error('Unexpected:'+str(e))
            finally:
                sleep(1)

#app instance
app=App()

if __name__ == '__main__':
    "main cli routine"
    print 'This is a Dnl Alert Daemon (novvvster@gmail.com)'
    if sys.argv[1] == 'debug':
        app.run()
    else:
        dr=runner.DaemonRunner(app)
        for h in LOG.handlers:
            if hasattr(h, 'stream'):
                if dr.daemon_context.files_preserve is None:
                    dr.daemon_context.files_preserve=[h.stream]
            else:
                    dr.daemon_context.files_preserve.append(h.stream)
        dr.do_action()
    LOG.info('dnl_ad terminated!')
