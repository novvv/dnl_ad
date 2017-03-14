from dnl_ad import *
import sys

"""
How to create test conditions:

1. do_notify_client_balance

update client set status=true,last_lowbalance_time='2017-03-08 11:18:29.306494+00' where client_id=62;

2. do_notify_zero_balance
update c4_client_balance set balance=-345.0 where client_id='62'
update client set allowed_credit=-300,status=true,zero_balance_notice_last_sent='2017-03-08 11:18:29.306494+00' where client_id=62;

3. do_daily_usage_summary
insert into cdr_report_detail20170310 
select report_time +substring(justify_days(age(report_time))::varchar from 1 for 7)::interval,
duration,ingress_bill_time,ingress_call_cost,lnp_cost,ingress_total_calls,not_zero_calls,ingress_success_calls,ingress_busy_calls,lrn_calls,pdd,ingress_cancel_calls,ingress_client_id,ingress_id,ingress_country,ingress_code_name,egress_client_id,egress_id,egress_country,egress_code_name,egress_code,ingress_prefix,egress_bill_time,egress_call_cost,egress_total_calls,egress_success_calls,egress_busy_calls,egress_cancel_calls,not_zero_calls_30,duration_30,not_zero_calls_6,duration_6,call_18s,call_24s,call_2h,call_3h,call_4h,call_12s,ingress_rate,egress_rate,product_rout_id,ingress_rate_date,egress_rate_date,incoming_bandwidth,outgoing_bandwidth,ingress_call_cost_intra,ingress_call_cost_inter,egress_call_cost_intra,egress_call_cost_inter,ingress_bill_time_intra,ingress_bill_time_inter,egress_bill_time_intra,egress_bill_time_inter,agent_id,agent_rate,agent_cost,ingress_rate_table_id,route_plan_id,orig_jur_type,term_jur_type,par_id,origination_destination_host_name,termination_source_host_name,binary_value_of_release_cause_from_protocol_stack,release_cause,release_cause_from_protocol_stack,inter_ingress_total_calls,intra_ingress_total_calls,inter_duration,intra_duration,inter_not_zero_calls,intra_not_zero_calls,q850_cause_count,npr_count,ingress_call_cost_local,ingress_call_cost_ij,egress_call_cost_local,egress_call_cost_ij,cdr_date,ingress_code,ring_pdd 
from cdr_report_detail20170303;

4. do_daily_balance_summary
update client set status=true,is_daily_balance_notification=true where client_id=62;

5.do_daily_cdr_delivery


update client set is_auto_summary=True, ahere client_id=62;

6.do_trunk_pending_suspension_notice
update rate_send_log set download_deadline = now() + interval '4 hour' where id = 2;

7.do_trunk_is_suspended_notice


"""
def notify_client_balance():
    print '--> Prepare data...'
#    query("update client set allowed_credit=-300,status=true,zero_balance_notice_last_sent='2017-03-08 11:18:29.306494+00' where client_id=62;")
#    query("update c4_client_balance set balance=-200.0 where client_id='62'")
#    query("update client set billing_email='akash@denovolab.com' where client_id='62'")
#    query("update client set status=true,last_lowbalance_time='2017-03-08 11:18:29.306494+00' where client_id=62;")
    do_notify_client_balance()
    print '--> Test passed...'
def notify_zero_balance():
    print '--> Prepare data...'
#    query("update client set allowed_credit=-300,status=true,zero_balance_notice_last_sent='2017-03-08 11:18:29.306494+00' where client_id=62;")
#    query("update c4_client_balance set balance=-345.0 where client_id='62'")
#    query("update client set status=true,last_lowbalance_time='2017-03-08 11:18:29.306494+00' where client_id=62;")
    do_notify_zero_balance()
    print '--> Test passed...'

def daily_usage_summary():
    print '--> Prepare data...'
    """insert into cdr_report_detail20170312 
select report_time +substring(justify_days(age(report_time))::varchar from 1 for 7)::interval,
duration,ingress_bill_time,ingress_call_cost,lnp_cost,ingress_total_calls,not_zero_calls,ingress_success_calls,ingress_busy_calls,lrn_calls,pdd,ingress_cancel_calls,ingress_client_id,ingress_id,ingress_country,ingress_code_name,egress_client_id,egress_id,egress_country,egress_code_name,egress_code,ingress_prefix,egress_bill_time,egress_call_cost,egress_total_calls,egress_success_calls,egress_busy_calls,egress_cancel_calls,not_zero_calls_30,duration_30,not_zero_calls_6,duration_6,call_18s,call_24s,call_2h,call_3h,call_4h,call_12s,ingress_rate,egress_rate,product_rout_id,ingress_rate_date,egress_rate_date,incoming_bandwidth,outgoing_bandwidth,ingress_call_cost_intra,ingress_call_cost_inter,egress_call_cost_intra,egress_call_cost_inter,ingress_bill_time_intra,ingress_bill_time_inter,egress_bill_time_intra,egress_bill_time_inter,agent_id,agent_rate,agent_cost,ingress_rate_table_id,route_plan_id,orig_jur_type,term_jur_type,par_id,origination_destination_host_name,termination_source_host_name,binary_value_of_release_cause_from_protocol_stack,release_cause,release_cause_from_protocol_stack,inter_ingress_total_calls,intra_ingress_total_calls,inter_duration,intra_duration,inter_not_zero_calls,intra_not_zero_calls,q850_cause_count,npr_count,ingress_call_cost_local,ingress_call_cost_ij,egress_call_cost_local,egress_call_cost_ij,cdr_date,ingress_code,ring_pdd 
from cdr_report_detail20170303 where client_id=62;
    """
    print '--> test...'
    do_daily_usage_summary()
    print '--> Test passed...'
def daily_balance_summary():
    print '--> Prepare data...'
    query("update client set status=true,is_daily_balance_notification=true where client_id=62;")
    print '--> test...'
    do_daily_balance_summary()
    print '--> Test passed...'
def daily_cdr_delivery():
    do_daily_cdr_delivery()
    print '--> Test passed...'
def trunk_pending_suspension_notice():
    print '--> Prepare data...'
    query("update client set company='Acme ltd.',  billing_email='akash@denovolab.com'  where client_id =2")
    query("update rate_send_log set download_deadline = now() + interval '4 hour' where id = 2; ")
    query("insert into rate_send_log_detail(log_id,resource_id) values(2,2)")
    print '--> test...'
    do_trunk_pending_suspension_notice()
    print '--> Test passed...'
def trunk_is_suspended_notice():
    print '--> prepare...'
    query("update resource set active=True where resource_id=2")
    query("update rate_send_log set download_deadline = now() - interval '4 hour' where id = 2;")
    print '--> test...'
    do_trunk_is_suspended_notice()
    print '--> Test passed...'


funmap={
    '1':notify_client_balance,
    '2':notify_zero_balance,
    '3':daily_usage_summary, 
    '4':daily_balance_summary, 
    '5':daily_cdr_delivery, 
    '6':trunk_pending_suspension_notice,
    '7':trunk_is_suspended_notice
    }


if __name__ == '__main__':
    print """dnl_ad interactive tester
press digits from 1 to 7 to fire test
q - exit
"""
    LOGLEVEL = logging.DEBUG

    while True:
        choice = raw_input("> ")
        if choice in ['q','Q', '0']:
            print 'bye'
            sys.exit(0)
        elif choice in funmap.keys():
            print "You press "+choice
            funmap[choice]()
        else:
            print 'nothing to do.'
        
