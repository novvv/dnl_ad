#/usr/bin/python
# -*- coding: UTF-8 -*-
import json, base64, urllib.request, urllib.error, urllib.parse, json
import re,sys,time
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mimetypes import MimeTypes


base="http://192.99.10.113:8000/api/v1.0/"

def cdr(q,data=None,method='GET'):
    url=base+q
    print(url)
    #User=username
    #Pass=password
    #base64string = base64.encodestring('%s:%s' % (User, Pass)).replace('\n', '')
    hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       #'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept':'application/json',
       'Accept-Charset': 'utf-8',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive',
       'Content-Type': 'application/json',
       #"Authorization": "Basic %s" % base64string
       }    
    request=urllib.request.Request(url,headers=hdr)
    if data and method=='GET':
        method='POST'
    request.get_method = lambda: method
    try:
        if data:
            response=urllib.request.urlopen(request, json.JSONEncoder().encode(data))
            text=response.read()
            return text #json.JSONDecoder().decode(text)
        else:
            response=urllib.request.urlopen(request)
            text=response.read()
            return json.JSONDecoder().decode(text)
    #try:
     #   pass
    except Exception as e: #urllib2.HTTPError, e:
        text=e.fp.read()
        print(text)
        return json.JSONDecoder().decode(text)
    return None
   
if __name__=='__main__':
    data={
  "switch_ip" : "192.99.10.113",
  "start" : "2016-12-15 00:55:00",
  "end" : "2016-12-15 19:55:00",
  "search_filter" : "",
#"origination_call_id=80DF2626-13C1-E611-AEFA-C79B2B8A31F1@149.56.44.190,origination_destination_number<>12345650601",
  "result_filter" : "trunk_id_termination,answer_time_of_date,call_duration,termination_call_id,release_cause,origination_source_number,origination_source_host_name,origination_destination_number,pdd,ingress_client_rate,egress_rate,orig_code,term_code" ,
  "email_to":"sourav27091992@gmail.com",
  "cdr_subject":"CDR parsing testing",
  "cdr_body":"CDR parsing {from_time} {to_time} {search_parameter} completed with status {status} . URL is {url}."
   }
    print('Call API')
    print('DATA:\n',data)
    print(cdr('create_query', data))
