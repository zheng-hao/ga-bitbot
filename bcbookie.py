
"""
bcbookie v0.01 

Copyright 2011 Brian Monkaba

This file is part of ga-bitbot.

    ga-bitbot is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ga-bitbot is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with ga-bitbot.  If not, see <http://www.gnu.org/licenses/>.
"""


import pdb
import pickle
from operator import itemgetter
from time import *
import MtGoxHMAC

# connect to the xml server
#

import xmlrpclib
#import json
import simplejson as json	#needed for python 2.4

import gene_server_config
import pdb

__server__ = gene_server_config.__server__
__port__ = str(gene_server_config.__port__)

#make sure the port number matches the server.
server = xmlrpclib.Server('http://' + __server__ + ":" + __port__)  

print "Connected to",__server__,":",__port__

class bookie:
    def __init__(self):
	self.client = MtGoxHMAC.Client()
	self.orders = []
	self.records = []
	self.balance = 0
	self.usds = 0
	self.btcs = 0
	self.btc_price = 0
	self.load_records()
    
    def report(self):
	#dump the records into a html file
	if len(self.records) > 0:
	    export = sorted(self.records, key=itemgetter('localtime'),reverse=True)
	    f = open('./report/book.html','w')
	    f.write('<table border="1">\n')
	    keys = export[0].keys()

	    #write the header
	    f.write('\t<tr>\n')
	    for key in keys:
		f.write('\t\t<th>\n')
		f.write('\t\t\t'+key + '\n')
		f.write('\t\t</th>\n')
	    f.write('\t</tr>\n')
	    
	    #write the records
	    for r in export:
		if (r['book'].find('buy_cancel') < 0) or 1:
			f.write('\t<tr>\n')
			for key in keys:
			    s = ""
			    if key == 'localtime':
				s = str(ctime(r[key]))
			    try:
			    	if s == "" and type(1.0) == type(r[key]):
			    		s = "%.3f"%r[key]
			    except:
			    	s = '-'
			    else:
			    	if s == "":
			    		s = str(r[key])

			    f.write('\t\t<td>\n')
			    f.write('\t\t\t'+ s + '\n')
			    f.write('\t\t</td>\n')
			f.write('\t</tr>\n')
	    f.write('</table>\n')
	    f.close()
	else:
	    f = open('./report/book.html','w')
	    f.write("No records to report.")
	    f.close()
	    
	return
    
    def get_price(self):
	#print "get_price: downloading last price"
	while 1:
	    try:
		self.btc_price = self.client.get_ticker()['last']
		return self.btc_price
	    except:
		print "get_price: client error..retrying @ " + ctime()
	
    def load_orders(self):
	#load orders from mt.gox
	while 1:
	    try:
		self.orders = self.client.get_orders()['orders']
		return
	    except:
		print "load_orders: client error..retrying @ " + ctime()
	
    def load_records(self):
	#load records from local file
	try:
	    f = open("./report/bookie_records.pkl",'r')
	    pd = f.read()
	    f.close()
	    self.records = pickle.loads(pd)
	except:
	    print "load_config: no records to load"
	self.record_synch()
    
    def save_records(self):
	#save records to local file
	f = open("./report/bookie_records.pkl",'w')
	f.write(pickle.dumps(self.records))
	f.close()
    
    def add_record(self,record):
	self.records.append(record)
	self.save_records()
    
    def get_last_order(self):
	#the last order will be the one with the largest date stamp
	self.load_orders()
	max_date = 0
	last_order = self.orders[0]
	for o in self.orders:
	    if o['date'] > last_order['date']:
		last_order = o
	return last_order

    def find_order(self,qty,price):
	self.load_orders()
	for o in self.orders:
		if str(o['amount']) == str(qty):
			if str(o['price']) == str(price):
				return o
	return None

    def find_buy_order_by_price(self,price):
	self.load_orders()
	for o in self.orders:
		if str(o['type']) == 2:
			if str(o['price']) == str(price):
				return o
	return None
	    
    def funds(self):
	while 1:
	    try:
		self.balance = self.client.get_balance()
		self.usds = self.balance['usds']
		self.btcs = self.balance['btcs']
		return self.usds
	    except:
		print "funds: client error..retrying @ " + ctime()

    def sell(self, amount, price,parent_oid = "none"):
	price = float("%.3f"%price)
	print "sell: selling position: qty,price: ",amount,price
	if price < self.btc_price:
	    price = self.btc_price - 0.01
	    print "sell: price adjustment: qty,price: ",amount,price

	while 1:
	    try:
		order = self.client.sell_btc(amount, price)
		order.update({'parent_oid':parent_oid,'localtime':time(),'pending_counter':10,'book':'open','commit':price,'target':price,'stop':price,'max_wait':999999,'max_hold':999999})
		self.add_record(order)		
		self.save_records()
		return
	    except:
		print "sell: client error..retrying @ " + ctime()
   
    def validate_buy(self,buy_price,target_price):
	if (buy_price * 1.00013) >= target_price:
	    print "validate_buy: target too low %.2f, order (%.2f) not submitted",target_price,buy_price
	    return False
	for r in self.records:
	    if r.has_key('book'):
		    if r['book'] == 'open':
			if str(r['price']) == str(buy_price):
				return False
	return True

    def buy(self,qty,buy_price,commit_price,target_price,stop_loss,max_wait,max_hold):
	buy_price = float("%.2f"%buy_price)
	target_price = float("%.2f"%target_price)
	commit_price = float("%.2f"%commit_price)

	if commit_price > target_price:
		print "buy: order validation failed, commit price higher than target"
		return False

	#verify that the order doesn't already exist at the price point
	if self.validate_buy(buy_price,target_price) == False:
	    dupe_order = self.find_buy_order_by_price(buy_price)
	    if dupe_order == None:
	    	print "buy: order validation failed @ $%.2f , target ($%.2f) too low)"%(buy_price,target_price)
	    else:
	    	print "buy: order validation failed @ $%.2f , target ($%.2f) duplicate order)"%(buy_price,target_price)
	    return False
	else:
	    print "buy: order validated"

	#check available funds
	cost = qty * buy_price
	if self.funds() > cost and qty >= 0.01:
	    last_btc_balance = self.btcs #used for verifying off book orders
	    #make sure the order is lower than the current price
	    if buy_price > self.btc_price:
		buy_price = self.btc_price - 0.02

	    while 1:
		try:
		    order = self.client.buy_btc(qty,buy_price)
		    break
		except:
		    print "buy: client error..retrying @ " + ctime()

	    if order == None:
		print 'buy: first level order verification failed'
	    	order = self.find_order(qty,buy_price)
		
	    if order == None:
		print 'buy: second level order verification failed'
		self.funds()
		if self.btcs > last_btc_balance:
			print 'buy: instant order verified'
			order = {'parent_oid':'none','price':buy_price,'oid':'none','localtime':time(),'pending_counter':10,'book':'held','commit':commit_price,'target':target_price,'stop':stop_loss,'max_wait':max_wait,'max_hold':max_hold}
		else:
			print 'buy: third level order verification failed'
			order = {'parent_oid':'none','price':buy_price,'oid':'none','localtime':time(),'pending_counter':10,'book':'closed: order not acknowledged','commit':commit_price,'target':target_price,'stop':stop_loss,'max_wait':max_wait,'max_hold':max_hold}
		self.add_record(order)
		#print 'buy: posting instant order for sale @ target (off book)'
		#self.sell(qty, target_price)
		

	    elif order['status'] == 2 and order['real_status'] != 'pending':
		self.cancel_buy_order(order['oid'])
		print 'buy: insuf funds'
		order.update({'parent_oid':'none','localtime':time(),'pending_counter':10,'book':'closed:insuf','commit':commit_price,'target':target_price,'stop':stop_loss,'max_wait':max_wait,'max_hold':max_hold})
		self.add_record(order)
		return False
	    else:
		order.update({'parent_oid':'none','localtime':time(),'pending_counter':10,'book':'open','commit':commit_price,'target':target_price,'stop':stop_loss,'max_wait':max_wait,'max_hold':max_hold})
		self.add_record(order)
		
		print "buy: order confirmed"
		return True
		
	else:
	    print "buy: lack of funds or min qty not met, order not submitted:"
	    print "\tqty",qty
	    print "\tcost",cost
	    print "\tfunds",self.usds
	    return 0
	
    def cancel_buy_order(self,oid):
	print "cancel_buy_order: canceling"
	while 1:
	    try:	
		self.client.cancel_buy_order(oid)
		self.save_records()
		return
	    except:
		print "cancel_buy_order: client error..retrying @ " + ctime()
	
    
    def record_synch(self):
	#find out which orders have been filled
	#tag buy orders as held
	#tag sell orders as sold
	self.load_orders()
	print "-"*80
	#print "record_synch: synching records:"
	for r in self.records:
	    if r['book'] == "open":
		found = 0
		#print "record_synch: searching for OID:",r['oid']
		for o in self.orders:
		    if o['oid'] == r['oid']:
			found = 1
			print "\trecord_synch: OID:",r['oid'], " active"
			#update with the current order status
			r['status'] = o['status']
			r.update({'amount_remaining':o['amount']})				

		if found == 0:
		    print "\trecord_synch: OID:",r['oid'], " not active"
		    #the order was filled
		    if r['type'] == 1:
			r['book'] = "sold"
			print "\t\trecord_synch: OID:",r['oid'], " tag as sold"
		    if r['type'] == 2:
			if r['status'] == 1:
			    r['book'] = "held"
			    print "\t\trecord_synch: OID:",r['oid'], " tag as held"
			elif r['status'] == 2 and r['real_status'] == "pending":
			    print "\t\trecord_synch: OID:",r['oid'], " remaining open (real_status:pending)"
			else:
			    r['book'] = "error: insuf funds"
			    print "\t\trecord_synch: OID:",r['oid'], " tag as error: insuf funds"

	#print "record_synch: error check:"
	error_found = 0
	for o in self.orders:
	    order_found = 0
	    for r in self.records:
		if o['oid'] == r['oid']:
		    order_found = 1
		    if r['book'] != "open":
			error_found = 1
			print "\trecord_synch: record error found, canceling order"
			self.cancel_buy_order(r['oid'])
			r['book'] += ": error"
	    if order_found == 0:		
	    	print "!!!!!!! record_synch: orphaned or manual order found:","TYPE:",o['type'],"AMOUNT:",o['amount'],"PRICE:",o['price']
		
	if error_found > 0:
	    print "record_synch: order error(s) found and canceled"
	else:
	    #print "record_synch: no order errors found"
	    pass
   
	self.save_records()
	self.report()
	
	
    def update(self):
	#periodicaly call this function to process open orders
	# -automates sells,stop loss, etc...
	#print "update: checking positions"
	current_price = self.get_price()
	print "\tupdate: current price %.3f @ %s"%(current_price,ctime())
	#first synch the local records...
	self.record_synch()
	
	print "-" * 80
	print "checking open orders"
	print "-" * 80
	for r in self.records:
	    #check open orders first...
	    if r['book'] == "open":		
		if r['type'] == 1: #sell
		    print "\tupdate: OID:",r['oid'], " sell order active"
		    pass	#sell orders stand until completed.
		elif r['type'] == 2: #buy
		    dt = time() - r['localtime']
		    print "\tupdate: OID:",r['oid'], " buy order active -- time left (seconds):",r['max_wait'] - dt
		    #kill any buy orders where there are not enough funds
		    if r['status'] == 2 and r['real_status'] == "pending":
			r['pending_counter'] -= 1
			if r['pending_counter'] == 0:
			    	print "\t\tupdate: canceling pending order (insuf funds?) (OID):",r['oid']
				self.cancel_buy_order(r['oid'])
				r['book'] = "buy_cancel: pending state (insuf funds?)"
		    elif r['status'] == 1 and r['real_status'] == "pending":
				#update the 'real status' - pending order has gone active
				r['real_status'] = "open"
		    elif r['status'] == 2:
			print "\t\tupdate: canceling order due to a lack of funds (OID):",r['oid']
			self.cancel_buy_order(r['oid'])
			r['book'] = "buy_cancel:insuf funds"
		    elif dt > r['max_wait']:
			print "\t\tupdate: canceling order due to timeout (OID):",r['oid']
			self.cancel_buy_order(r['oid'])
			r['book'] = "buy_cancel:max_wait"
	
	print "-" * 80
	print "checking held positions"
	print "-" * 80
	for r in self.records:	    
	    #check held positions
	    put_for_sale = 0
	    if r['book'] == "held":
		dt = time() - r['localtime']
		#check commit price
		if current_price >= r['commit']:
		    print "\t+++ update: selling position: price commit target met: (OID):",r['oid']
		    self.sell(r['amount'],r['target'],parent_oid = r['oid'])
		    r['book'] = "closed:commit"
		    put_for_sale = 1
		#check max age  
		elif dt > r['max_hold'] and put_for_sale == 0:
		    #dump the position
		    print "\t-+- update: selling position: target timeout: (OID):",r['oid']
		    self.sell(r['amount'],current_price - 0.001,parent_oid = r['oid'])
		    r['book'] = "closed:max_hold"
		    put_for_sale = 1
		#chek stop loss
		elif current_price <= r['stop'] and  put_for_sale == 0:
		    #dump the position
		    print "\t--- update: selling position: stop loss: (OID):",r['oid']
		    self.sell(r['amount'],current_price - 0.001,parent_oid = r['oid'])
		    r['book'] = "closed:stop"
		    put_for_sale = 1
		elif put_for_sale == 0:
		    oid = r['oid']
		    time_left = str(int((r['max_hold'] - dt)/60.0))
		    stop_delta = "%.2f"%(current_price - r['stop'])
		    delta_target = "%.2f"%(r['target'] - current_price)
		    print "update: OID:%s time left: %s stop_delta: %s delta_target: %s"%(oid,time_left,stop_delta,delta_target)
	
	#save the updated records
	self.save_records()
	#generate the report
	self.report()
	#return the account balance
	self.funds()
	return self.usds,self.btcs
		
	        
	
	
if __name__ == "__main__":
    monitor_mode = False

    b = bookie()

    bid_counter = 3
    
    print "main: generating inital report"
    b.report()
    
    print "main: entering main loop"
    while 1:
	if True:
	    print "_"*80
	    print "main: Availble Funds (USDS,BTCS) :" + str(b.update())
	    #always maintain a short term buy order
	    #buy(qty,buy_price,target_price,stop_loss,max_wait,max_hold)

	    bid_counter += 1
	    if bid_counter == 5:
		bid_counter = 0
		"main: Submitting GA Order: "

		t = json.loads(server.get_target())
		if monitor_mode == False:
			commit = ((t['target'] - t['buy']) * 0.8) + t['buy'] #commit sell order at 80% to target
			if t['buy'] > 1 and t['buy'] < 20:
			    b.buy(0.5,t['buy'],commit,t['target'],t['stop'],60 * 5,t['stop_age'])
			    #maintain underbid orders
			    u_bids = 10
			    for u_bid in range(2,u_bids,2):
				bid_modifier = 1 - (u_bid/300.0)
			    	b.buy(0.25 * u_bid,t['buy'] * bid_modifier,commit,t['target'],t['stop'],60 * (u_bids + 5),t['stop_age'])
			    pass
			else:
			    print "main: No GA order available."

	print "_"*80
	print "sleeping..."
	print "_"*80
	print "\n\n"  
	sleep(60)
