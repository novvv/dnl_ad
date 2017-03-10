#!/usr/bin/python

#import daemon
from daemon import runner
import psycopg2
import psycopg2.extras
import smtplib
import sys
import os
import gzip
import logging
import logging.handlers
from logging import config
from time import sleep, gmtime
from datetime import date, datetime, timedelta, time
from pytz import UTC
from collections import defaultdict
import pytz  # $ pip install pytz
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib2
import json

CONNECTION_STRING = "host='localhost' dbname='class4_pr' user='postgres'"
PIDFILE = '/var/tmp/dnl_ad.pid'
LOGFILE = '/var/tmp/dnl_ad.log'
LOGLEVEL = 'DEBUG'

dt = datetime.now(UTC)  # current time in UTC
zone_names = defaultdict(list)

for tz in pytz.common_timezones:
    zone_names[dt.astimezone(pytz.timezone(tz)).utcoffset()].append(tz)


def tz_from_string(off):
    """Return tzinfo.Time zone info from string -12:00 ."""
    hm = off[1:].split(':')
    pre = off[0]
    m = {'+': 0, '-': -1}
    return zone_names[timedelta(m[pre], int(hm[0])*3600+int(hm[1])*60)][0]


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
    log = logging.handlers.RotatingFileHandler(
              filename, maxBytes=int(maxBytes), backupCount=int(backupCount))
    log.rotator = GZipRotator()
    return log


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(module)s P%(process)d \
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
            'maxBytes': 20000,
            'backupCount': 50,
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
#Establish logger
LOG = logging.getLogger("my-logger")


def get_mail_params(fr):
    """Get parameters for sending mail from system configuration table."""
    try:
        p = query("select * from system_parameter")[0]
    except Exception as e:
        LOG.error("system_parameters not ready: %s", str(e))
        raise e
    return (
        (p.smtphost, p.smtpport, p.emailusername, \
         p.emailpassword, p.__dict__[fr])
    )


def send_mail(from_field, to, subject, text):
    """sending email."""
    (host, port, user, passw, mfrom) = get_mail_params(from_field)
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = mfrom
    msg['To'] = to
    txt = MIMEText(text, 'html')
    msg.attach(txt)
    LOG.info(msg.as_string())
    try:
        server = smtplib.SMTP(host+':'+port)
        server.ehlo()
        if port == '587':
            server.starttls()
        server.login(user, passw)
        server.sendmail(mfrom, to, msg.as_string())
        server.quit()
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
        LOG.info('rendered:'+out)
        return out
    except Exception as e:
        LOG.error('template error:'+str(e))
        return templ


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


def do_notify_client_balance(sleep_time, no_send_mail):
    u"""
     Check every 5 minute for each “active” clients’ current balance and “low
     balance” trigger.  If the “current balance” is below the “low balance”
     trigger, then send out an alert.

Also, there is a “number of time” that we should send in total before payment
or credit is added. Each day, the low balance should be sent once.  The
subsequent notification should be sent on 00:00:00 of the client’s GMT timezone
( default is gmt+0) Notification Setting of client: select 
notify_client_balance, low_balance_notice from client; To check if client is
active: Select status from client ;

    """
    LOG.info("start notify low client balance")
    clients = query(
        "select * from client c,c4_client_balance b where\
        c.client_id::text=b.client_id and balance::numeric <=\
        notify_client_balance and status=true")
    try:
        templ = query('select * from mail_tmplate')[0]
    except Exception as e:
        LOG.error('no template table:'+str(e))
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

        if cl.daily_balance_send_time is None:
            LOG.error('Sending time not set!')
            cl.daily_balance_send_time = time(0, 0, 0, 0, UTC)
        else:
            cl.daily_balance_send_time = datetime.combine(
                cl.date,
cl.daily_balance_send_time).replace(tzinfo=UTC).timetz()
        sendtime_a = datetime.combine(
            cl.date, cl.daily_balance_send_time) - \
            timedelta(seconds=sleep_time*2)
        sendtime_b = datetime.combine(
            cl.date, cl.daily_balance_send_time) + \
            timedelta(seconds=sleep_time*2)
        if cl.last_lowbalance_time:
            last_send = cl.last_lowbalance_time
        else:
            last_send = cl.now - timedelta(hours=24)
        LOG.info('times:last %s now %s a %s b %s' %
                 (str(last_send), str(cl.now), str(sendtime_a),
                 str(sendtime_b)))
        if cl.now-last_send > timedelta(seconds=sleep_time*2) and cl.now > sendtime_a and cl.now < sendtime_b:
            LOG.info('Time to send notification!')
        else:
            continue
        cl.company_name = cl.company
        cl.allow_credit = cl.allowed_credit
        cl.balance = '%20.2f' % float(cl.balance)
        cl.notify_balance = cl.notify_client_balance

        subj = process_template(templ.lowbalance_subject, cl)
        content = process_template(templ.lowbalance_content, cl)
        LOG.info("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.email, subj, content))
        try:
            if '@' in cl.billing_email and no_send_mail is False:
                send_mail('fromemail', cl.email, subj, content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
        #make things after send alert
        times = int(cl.lowbalance_notication_time)+1
        query(
            "update client set last_lowbalance_time='%s' where client_id=%s" %
              (str(cl.now), cl.client_id))


def do_notify_zero_balance(sleep_time, no_send_mail):
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
Select credit from client;

     """
    LOG.info("start notify Zero client balance")
    clients1=query("""select * from client c,c4_client_balance b
         where c.client_id::text=b.client_id and balance::numeric <= 0
         and status=true and mode=1 and zero_balance_notice""")
    clients2=query("""select * from client c,c4_client_balance b
         where c.client_id::text=b.client_id and balance::numeric <= -allowed_credit
         and status=true and mode=2 and zero_balance_notice""")
    clients = clients1+clients2
    try:
        templ = query('select * from mail_tmplate')[0]
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
        send_time = time(0, 0, 0, tz_from_string(cl.auto_send_zone)) 

        sendtime_a = datetime.combine(
            cl.date, send_time) - timedelta(seconds=sleep_time*2)
        sendtime_b = datetime.combine(
            cl.date, send_time) + timedelta(seconds=sleep_time*2)
        if cl.zero_balance_notice_last_send:
            last_send = datetime.combine(
                cl.date, cl.zero_balance_notice_last_send)
        else:
            last_send = cl.now - timedelta(hours=24)
        LOG.info('times:last %s now %s a %s b %s' %
                 (str(last_send), str(cl.now), str(sendtime_a),
                 str(sendtime_b)))
        if cl.now-last_send > timedelta(seconds=sleep_time*2) and cl.now > sendtime_a and cl.now < sendtime_b:
            LOG.info('Time to send notification!')
        else:
            continue
        cl.company_name = cl.company
        cl.allow_credit = cl.allowed_credit
        cl.balance = '%20.2f' % float(cl.balance)
        cl.notify_balance = cl.notify_client_balance

        subj = process_template(templ.low_balance_alert_email_subject, cl)
        content = process_template(templ.low_balance_alert_email_content, cl)
        LOG.info("%s : %s subject: %s content: %s" %
                 (cl.client_id, cl.billing_email, subj, content))
        try:
            if '@' in cl.billing_email and no_send_mail is False:
                send_mail('fromemail', cl.email, subj, content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))
        #make things after send alert
        times = int(cl.zero_balance_notice_time)+1
        query(
            "update client set zero_balance_notice_time='%s' zero_balance_notice_last_send='%s'  where client_id=%s" %
              (times, str(cl.now), cl.client_id))


def do_daily_usage_summary(sleep_time, no_send_mail):
    u"""
    For each client who has “daily usage summary” selected, at the client’s GMT
    time zone, we need to send out a daily usage summary mail. """
    LOG.info("start notify daily usage summary")
    clients = query(
        "select * from client  where status and daily_cdr_generation=TRUE")
    #templ = query('select * from mail_tmplate')[0]
    for cl in clients:
        LOG.warning('DAILY USAGE! client_id:%s, name:%s' %
                    (cl.client_id, cl.name))
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        usage = query(
            "select * from cdr_report_detail%s where ingress_client_id=%s" %
                      (cl.date.strftime("%Y%m%d"), cl.client_id))
        content = process_table(usage)
        subj = 'Daily usage summary'
        try:
            if '@' in cl.billing_email and no_send_mail is False:
                send_mail('fromemail', cl.email, subj, content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))


def do_daily_balance_summary(sleep_time, no_send_mail):
    u"""
    For each client who has “daily balance summary” selected, at the client’s
    GMT time zone, we need to send out a daily balance summary mail.

    """
    LOG.info("start Daily Balance Summary")
    clients = query(
        "select * from client  where status=true and\
        daily_balance_notification=1")
    for cl in clients:
        cl.date = date.today()
        cl.time = datetime.now(UTC).timetz()
        cl.now = datetime.now(UTC)
        balance = query(
            "SELECT * FROM balance_history_actual  WHERE  date = '2017-03-06'\
            AND client_id = %d" % cl.client_id)
        content = process_table(balance)
        subj = 'Daily usage summary'
        try:
            if '@' in cl.billing_email and no_send_mail is False:
                send_mail('fromemail', cl.email, subj, content)
        except Exception as e:
            LOG.error('cannot sendmail:'+str(e))


def do_daily_cdr_delivery(sleep_time, no_send_mail):
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
    LOG.info('Daily CDR Delivery')
    data = {
        "switch_ip":  "192.99.10.113",
        "query_key":
            "33ZvPfHH0ukPpMCl6NZZ4oWQsiySJWtLVvedsPBBGGiUwzuBPjerOXSS6shfzXN" \
                "zw5ajvlMZHAUu0bozyc776mN0YLAyQZHnVupa"
                }
    req = urllib2.Request("http://192.99.10.113:8000/api/v1.0/show_query_cdr")
    req.add_header('Content-Type', 'application/json')

    resp = urllib2.urlopen(req, json.JSONEncoder().encode(data))
    dt = resp.read()
    return dt


def do_trunk_pending_suspension_notice(sleep_time, no_send_mail):
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
    LOG.info('Trunk Pending Suspension Notice')


def do_trunk_is_suspended_notice(sleep_time, no_send_mail):
    LOG.info('Trunk is Suspended Notice')
    """
    For each client, at the client’s timezone 00:00:00, we need to check if there is any pending rate download and the deadline is passed.  If so, pls send this email AND “disable this relevant trunk.”
Select download_deadline from rate_send_log;
Select client_id , resource_id from rate_send_log_detail
, resource where resource.resource_id = rate_send_log_detail.resource_id
Select * from rate_download_log where client_id = xx and log_detail_id = xx
    """


class App():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path = PIDFILE
        self.pidfile_timeout = 5

    def run(self):
        sleep_time = 300
        no_send_mail = True
        while True:
            try:
                do_notify_client_balance(sleep_time, no_send_mail)
                do_notify_zero_balance(sleep_time, no_send_mail)
                do_daily_usage_summary(sleep_time, no_send_mail)
                do_daily_balance_summary(sleep_time, no_send_mail)
                do_daily_cdr_delivery(sleep_time, no_send_mail)
                do_trunk_pending_suspension_notice(sleep_time, no_send_mail)
                do_trunk_is_suspended_notice(sleep_time, no_send_mail)
            except Exception as e:
                LOG.error('Unexpected:'+str(e))
            finally:
                sleep(sleep_time)

app = App()

if __name__ == '__main__':
    print 'This is a Dnl Alert Daemon (novvvster@gmail.com)'
    if sys.argv[1] == 'debug':
        app.run()
    else:
        dr = runner.DaemonRunner(app)
        for h in LOG.handlers:
            if hasattr(h, 'stream'):
                if dr.daemon_context.files_preserve is None:
                    dr.daemon_context.files_preserve = [h.stream]
            else:
                    dr.daemon_context.files_preserve.append(h.stream)
        dr.do_action()
    LOG.info('dnl_ad terminated!')
