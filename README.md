# dnl_ad is denovolab alert daemon.

dnl_ad is a deamon for send mail to providers clients.

# Purpose
It's constanly run a foreground mode and regularly check some conditions in provider's database.
If conditions for some client gone true, a dnl_ad send email to  that client.

# Features
* Simplicity.  The code take small number of python libraries
* Configurability. Very simple configure this daemon.
* Small resources. In foregroun daemon will chek schedule event every second and on event query database for only needed clients.
That is why it will need small of processor time

# Functions
Now, the daemon will fire 7 types of alerts:
1. Notify client balance
when client balance go lower than limits.
2. Notify zero balance
when client balance below zero or below credit limit.
3. Daily usage summary
Notification for client od daily usage.
This notification send every day at scheduled time.
4. Daily balance summary
Information for clients about his balance.
5.Daily cdr delivery
Send link to download detailed information about resorce usage
6.Trunk pending suspension notice
Send notice about near future deadline of download rate limits file. 
7.Trunk is suspended notice
If file (item 6) not download, daemon wil send email to client and set in database block on selected resource.

User story you can read in AlertScriptRequriement.odt  document.

# System requerements
The dnl_ad requre for properly work installed python 2.7.
Also must be installed listed python libraries:

daemon
psycopg2
pytz
json

The bundle include library "schedule" for event processing


# Downloading

You can download it from git:
git clone http://stash.denovolab.com/scm/ta/class4-alert---valentin.git   

# Configuration

On top in file dnl_ad.py you can check and edit basic configuration parameters:
\#configuration
CONNECTION_STRING = "host='localhost' dbname='class4_pr' user='postgres'"
PIDFILE = '/var/tmp/dnl_ad.pid'
LOGFILE = '/var/tmp/dnl_ad.log'
LOGLEVEL = logging.WARN
\#/configuration
Other parameters for properly run set in provider database.

# Command line
You can start dnl_ad  by following command in the product directory:
$./dnl_ad.py start
The daemon will start and write all messages to logfile, listed on configuration

If you need stop the daemon:
$./dnl_ad.py start

Quickly restart very simple:
./dnl_ad.py restart

# Testing and debugging
There is utility in bundle for manual testing:
$./test.py
After start it waits user input.
You can press digits from 1 to 7
test.py wil create conditions for fire related events and then call function from dnl_ad.py.
*WARNING!!! Do not do this on production  database, or it can input fake information on it.

For debug purpose you can set in configuration section 
LOGLEVEL=logging.DEBUG 
Also, will be helpfull setting debus output in console, uncomment string 112
\#'handlers': ['stdout'] and comment next line
And, for run in foreground mode you can do:
./dnl_ad.py debug
 
# Release notes
version 1.0  need to preproduction  testing

# Contributors
dnl_ad was originaly written by Valentin Novikov (novvvster@gmail.com) for denovolab.
Very thanks Anne Kwong, Sourav (sourav@denovolab.com) and Akash (akash@denovolab.com) for requerements, testing and help.

