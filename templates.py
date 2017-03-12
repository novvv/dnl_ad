#!/usr/bin/python
# -*- coding: UTF-8 -*-


fake_daily_balance_summary_template=""""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title></title>
        <meta name="generator" content="LibreOffice 5.2.3.3 (Linux)"/>
        <meta name="created" content="2017-03-10T23:25:04.463028870"/>
        <meta name="changed" content="2017-03-10T23:27:40.858763822"/>
        <style type="text/css">
                h2 { margin-top: 0.64cm; direction: ltr; line-height: 100%; text-align: left; page-break-inside: avoid; orphans: 2; widows: 2 }
                h2.western { font-family: "Liberation Serif", serif; font-size: 16pt; font-weight: normal }
                h2.cjk { font-family: "DejaVu Sans"; font-size: 16pt; font-weight: normal }
                h2.ctl { font-family: "Noto Sans Devanagari"; font-size: 16pt; font-weight: normal }
        </style>
</head>
<body lang="ru-RU" dir="ltr">
<h2 class="western" align="center" style="margin-bottom: 0.14cm; line-height: 100%; page-break-inside: auto; page-break-after: auto">
<font size="5" style="font-size: 16pt"><b><span style="background:
#51a351">Daily
Balance Summary</span></b></font></h2>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Hi {client_name}</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><font size="2" style="font-size: 9pt">Your
blance in ICX is {beginning_of_day_balance} USD as of
{beginning_of_day}. </font>
</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Your credit
summary is as follows:</p>
<table width="294" cellpadding="7" cellspacing="0">
        <col width="126">
        <col width="137">
        <tr valign="top">
                <td width="126" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">Credit Limit</p>
                </td>
                <td width="137" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{credit_limit}</p>
                </td>
        </tr>
        <tr valign="top">
                <td width="126" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">Remaining Credit</p>
                </td>
                <td width="137" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{remaining_credit}</p>
                </td>
        </tr>
        <tr valign="top">
                <td width="126" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">Current Balance</p>
                </td>
                <td width="137" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{balance}</p>
                </td>
        </tr>
</table>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><br/>

</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><br/>

</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
International Carrier Exchange Limited</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">Rooms
05-15, 13A/F, South Tower, World Finance Centre, Harbour City,</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">17
Canton Road, Tsim Sha Tsui, Kowloon, Hong Kong</p>
<p style="margin-bottom: 0cm"><br/>

</p>
</body>
</html>
"""

fake_daily_usage_summary_template="""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
	<meta http-equiv="content-type" content="text/html; charset=utf-8"/>
	<title></title>
	<meta name="generator" content="LibreOffice 5.2.3.3 (Linux)"/>
	<meta name="author" content="Валентин Владимирович Новиков"/>
	<meta name="created" content="2017-03-12T13:34:07.973570009"/>
	<meta name="changedby" content="Валентин Владимирович Новиков"/>
	<meta name="changed" content="2017-03-12T13:34:42.566223502"/>
	<style type="text/css">
		h2 { margin-top: 0.64cm; direction: ltr; line-height: 100%; text-align: left; page-break-inside: avoid; orphans: 2; widows: 2 }
		h2.western { font-family: "Liberation Serif", serif; font-size: 16pt; font-weight: normal }
		h2.cjk { font-family: "DejaVu Sans"; font-size: 16pt; font-weight: normal }
		h2.ctl { font-family: "Noto Sans Devanagari"; font-size: 16pt; font-weight: normal }
	</style>
</head>
<body lang="ru-RU" dir="ltr">
<h2 class="western" align="center" style="margin-bottom: 0.14cm; line-height: 100%; page-break-inside: auto; page-break-after: auto">
<font size="5" style="font-size: 16pt"><b><span style="background: #51a351">Daily
Usage Summary</span></b></font></h2>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm"> 
</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Hi {client_name}</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><font size="2" style="font-size: 9pt">This
is a CDR for your traffic from {begin_time} to  {end_time}
{customer_gmt}.</font></p>
<table width="522" cellpadding="7" cellspacing="0">
	<col width="233">
	<col width="258">
	<tr valign="top">
		<td width="233" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">CDR count</p>
		</td>
		<td width="258" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">{cdr_count}</p>
		</td>
	</tr>
	<tr valign="top">
		<td width="233" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">Filename</p>
		</td>
		<td width="258" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">{file_name}</p>
		</td>
	</tr>
	<tr valign="top">
		<td width="233" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">Download Link</p>
		</td>
		<td width="258" style="border: 1px solid #000001; padding: 0.18cm">
			<p style="margin-left: 0.81cm">{download_link}</p>
		</td>
	</tr>
</table>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">You may send out
the public link to your staff or parter to access this CDR files
without having to login to your account.  Your public link for this
CDR is {share_link}.</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
International Carrier Exchange Limited</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">Rooms
05-15, 13A/F, South Tower, World Finance Centre, Harbour City,</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">17
Canton Road, Tsim Sha Tsui, Kowloon, Hong Kong</p>
<p style="margin-bottom: 0cm"><br/>

</p>
<p style="margin-bottom: 0cm"><br/>

</p>
<p style="margin-bottom: 0cm"><br/>

</p>
</body>
</html>
"""


fake_trunk_pending_suspension_notice_template="""
  <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title></title>
        <meta name="generator" content="LibreOffice 5.2.3.3 (Linux)"/>
        <meta name="created" content="2017-03-11T02:08:06.582818841"/>
        <meta name="changed" content="2017-03-11T02:08:56.531572963"/>
        <style type="text/css">
                h2 { margin-top: 0.64cm; direction: ltr; line-height: 100%; text-align: left; page-break-inside: avoid; orphans: 2; widows: 2 }
                h2.western { font-family: "Liberation Serif", serif; font-size: 16pt; font-weight: normal }
                h2.cjk { font-family: "DejaVu Sans"; font-size: 16pt; font-weight: normal }
                h2.ctl { font-family: "Noto Sans Devanagari"; font-size: 16pt; font-weight: normal }
        </style>
</head>
<body lang="ru-RU" dir="ltr">
<h2 class="western" align="center" style="margin-bottom: 0.14cm; line-height: 100%; page-break-inside: auto; page-break-after: auto">
<font size="5" style="font-size: 16pt"><b><span style="background:
#51a351">Trunk
Suspension Notice</span></b></font><font size="5" style="font-size: 17pt"><b><span style="background:
#51a351">
</span></b></font>
</h2>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Hi {company_name}</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Your trunk
{trunk_name} is suspecded because you have not download the rate
update {rate_update_file_name} before the {rate_download_deadline}.</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Please contact us
via noc@intlcx.com to have your trunk re-activated.</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><br/>

</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><br/>

</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
International Carrier Exchange Limited</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">Rooms
05-15, 13A/F, South Tower, World Finance Centre, Harbour City,</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">17
Canton Road, Tsim Sha Tsui, Kowloon, Hong Kong</p>
<p style="margin-bottom: 0cm"><br/>

</p>
<p style="margin-bottom: 0cm"><br/>

</p>
</body>
</html>
    """
    
fake_daily_cdr_usage_template="""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title></title>
        <meta name="generator" content="LibreOffice 5.2.3.3 (Linux)"/>
        <meta name="created" content="2017-03-11T11:45:07.047391640"/>
        <meta name="changedby" content="Валентин Владимирович Новиков"/>
        <meta name="changed" content="2017-03-11T11:46:05.290665278"/>
        <style type="text/css">
                h2 { margin-top: 0.64cm; direction: ltr; line-height: 100%; text-align: left; page-break-inside: avoid; orphans: 2; widows: 2 }
                h2.western { font-family: "Liberation Serif", serif; font-size: 16pt; font-weight: normal }
                h2.cjk { font-family: "DejaVu Sans"; font-size: 16pt; font-weight: normal }
                h2.ctl { font-family: "Noto Sans Devanagari"; font-size: 16pt; font-weight: normal }
        </style>
</head>
<body lang="ru-RU" dir="ltr">
<h2 class="western" align="center" style="margin-bottom: 0.14cm; line-height: 100%; page-break-inside: auto; page-break-after: auto">
<font size="5" style="font-size: 16pt"><b><span style="background:
#51a351">Daily
Usage Summary</span></b></font></h2>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">Hi {client_name}</p>
<p style="margin-left: 0.81cm; margin-bottom: 0cm"><font size="2" style="font-size: 9pt">This
is a CDR for your traffic from {begin_time} to  {end_time}
{customer_gmt}.</font></p>
<table width="522" cellpadding="7" cellspacing="0">
        <col width="233">
        <col width="258">
        <tr valign="top">
                <td width="233" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">CDR count</p>
                </td>
                <td width="258" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{cdr_count}</p>
                </td>
        </tr>
        <tr valign="top">
                <td width="233" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">Filename</p>
                </td>
                <td width="258" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{file_name}</p>
                </td>
        </tr>
        <tr valign="top">
                <td width="233" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">Download Link</p>
                </td>
                <td width="258" style="border: 1px solid
                #000001; padding: 0.18cm">
                        <p style="margin-left: 0.81cm">{download_link}</p>
                </td>
        </tr>
</table>
<p style="margin-left: 0.81cm; margin-bottom: 0cm">You may send out
the public link to your staff or parter to access this CDR files
without having to login to your account.  Your public link for this
CDR is {share_link}.</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">
International Carrier Exchange Limited</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">Rooms
05-15, 13A/F, South Tower, World Finance Centre, Harbour City,</p>
<p align="center" style="margin-left: 0.81cm; margin-bottom: 0cm">17
Canton Road, Tsim Sha Tsui, Kowloon, Hong Kong</p>
<p style="margin-bottom: 0cm"><br/>

</p>
</body>
</html>
"""
