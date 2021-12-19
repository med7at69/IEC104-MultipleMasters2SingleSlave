#!/usr/bin/env python3
#
# ******************************************************
# IEC 104 Multiple Masters to Single Slave (IEC104MM2SS)
#  	     By M. Medhat - 1 Nov 2021 - Ver 1.0
# ******************************************************
#
# Program is playing man in the middle role to connect
# multiple IEC 104 masters to single slave.
#
# Revision history:
# python:
#	iec104mm2ss.py
#
# File: iec104mm2ss.csv
#     Initial file as comma separated values (csv).
#
# This file: Read and write packets.
#			 Handle network sockets.
#			 Windows GUI
#			 Windows service
# *****************************************************
#                       Imports
# ------------------------------------------------------
from getopt import getopt
from ipaddress import ip_address,ip_network
import threading
from os import remove,stat,mkdir,system,name,devnull
from datetime import datetime
from socket import socket,AF_INET,SOCK_STREAM,SOL_SOCKET,SO_REUSEADDR,SHUT_RDWR,error,timeout,SOCK_DGRAM,gaierror,setdefaulttimeout
from binascii import hexlify
from signal import signal,SIGTERM
from struct import unpack,pack
from select import select
from sys import argv,byteorder,exit,stdout
from time import time,sleep
from os.path import isfile,getsize
from csv import reader
from atexit import register
if name == 'nt':
	from win32api import SetSystemTime
else:
	from os import WIFEXITED,WEXITSTATUS

# ******************************************************
#                       Variables
# ------------------------------------------------------
PYTHONUNBUFFERED='disable python buffer'
# program argument - see below
# define help message
help1="usage iec104mm2ss [[-h][--help]] [[-i][--ini] init-file] [[-t][--ntp_update_every_sec] sec] [[-s][--ntp_server] ntpserver]\n"
help2="example1: iec104mm2ss -i iec104mm2ss.csv\n"
help3="example2: iec104mm2ss --ntp_server pool.ntp.org --ntp_server time.windows.com\n"
help4="-s or --ntp_server could be included multiple times for multiple servers.\n"
help5="\t -h or --help\t\t\t\thelp message.\n"
help6="\t -i or --ini\t\t\t\tinit file (comma separated values), default iec104mm2ss.csv.\n"
help7="\t -t or --ntp_update_every_sec\t\tNTP update interval, default=900 seconds (requires admin privilege).\n"
help8="\t -s or --ntp_server\t\t\tNTP server, could be included multiple times (requires admin privilege).\n"
help9="\t -n or --nogui\t\t\t\tstart program without GUI interface.\n"
help10="\t -c or --service\t\t\tstart program as Windows service (without GUI interface).\n"
help11="\t To install the Windows service run 'iec104mm2ss --startup auto install'.\n"
help12="\t For more details please check the help file 'iec104mm2ss.pdf'.\n"
helpmess=help1+help2+help3+help4+help5+help6+help7+help8+help9+help10+help11+help12
if name == 'nt':
	dir='log\\'
	initfile='iec104mm2ss.csv'
else:
	dir='./log/'
	initfile='./iec104mm2ss.csv'

ntpserver=[]
timeupdated=''
updatetimegui=0
timeupdateevery=900		# in seconds

exitprogram=0

mainth=[]
th=[]
indexlist=[]
csvindexlist=[]
portnolist=[]
window=0
txtbx1thid=0
txtbx2thid=0
updatetoframe1=0
updatetoframe2=0
noofsys=0
programstarted=0

nogui=0
runasservice=0
logupdateperiod=10		# in case no GUI mode then update log files every 10 seconds.

# *****************************************************
#                       Functions
# -----------------------------------------------------
def signal_term_handler(signal, frame):
	exit()

def cleanup():
	global exitprogram,mainth,th,window,nogui
	exitprogram=1
	fh=[]
	for a in mainth:
		if a:
			a.dataactive=0
			fh.append(a.logfhw)
			fh.append(a.logfhr)
	for a in th:
		if a:
			a.join(0.1)
	for a in mainth:
		if a:
			if not nogui:
				deletertu(a)
			a.c_mmainth.acquire()
			tmpmmainth = a.mmainth.copy()
			a.c_mmainth.release()
			for i in tmpmmainth:
				if i:
					if i.readpacketth:
						i.readpacketth.join(0.1)
					i.join(0.1)
			a.join(0.1)
	for a in fh:
		if a:
			a.close()
	if not nogui and window:
		window.destroy()

def deletertu(self):
	global window
	tab_parent.select(0)
	canvas.yview_moveto('0.0')
	self.lbl_seqno.destroy()
	self.lbl_sys.destroy()
	self.lbl_status.destroy()
	self.lbl_portno.destroy()
	self.lbl_rtuno.destroy()
	self.lbl_connectedat.destroy()
	self.cbx_connectedmasters.destroy()
	#if self.logevents:
	self.cbx_action.destroy()
	self.btn_apply.destroy()
	window.update()

def opensocket(port):
	# open socket
	s=socket(AF_INET, SOCK_STREAM)
	s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
	s.bind(('', port))
	s.listen(1)
	return s
		
def closesocket(self):
	try:
		self.s.close()
		self.s = 0
	except (error, OSError, ValueError, AttributeError):
		self.s = 0
	return 0

def openconnClient(self):
	global exitprogram
	conn = 0
	self.srviprotate += 1
	if self.srviprotate >= len(self.srvip):
		self.srviprotate = 0
	for i in range(self.srviprotate,len(self.srvip)):
		if exitprogram:
			break
		# open connection for mm2ss client to real server
		conn = socket( AF_INET, SOCK_STREAM )
		try:
			# set timeout = 3 sec.
			conn.settimeout(3.0)
			self.logfhw.write(str(datetime.now()) + ' : Client - ' + self.name + '.\n')
			self.logfhw.write('\t\t\t     ' + 'trying to connect to ' + self.srvip[i] + ':' + self.srvport[i] + '.\n')
			self.logfilechanged=1
			conn.connect((self.srvip[i], int(self.srvport[i])))
			#self.conn.connect((address, int(self.srvport[i])))
			self.timeidle=time()
			self.t3timeidle=time()
		except (timeout, gaierror, ConnectionRefusedError,OSError):
			conn.close()
			conn=0
		if conn:
			self.connectedip=self.srvip[i]
			#tmpname = self.name.split(':')
			self.logname = 'Client ' + self.name + ': ' + self.connectedip + ':' + self.srvport[i] + ':\n'
			self.logfhw.write(str(datetime.now()) + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'connected to ' + self.srvip[i] + ':' + self.srvport[i] + '.\n')
			self.logfilechanged=1
			self.conn = conn
			break
	return conn

def openconn(self):					# self thread is for slave.
	# open connection
	conn = 0
	if self.s:
		try:
			conn, addr = self.s.accept()
		except (error, OSError, ValueError):
			conn = 0
			self.s=closesocket(self)
			self.s = opensocket(self.PORT)
		if conn:
			conn.setblocking(False)
			acceptedaddr=0
			for i in self.acceptnetsys:
				try:
					if ip_address(addr[0]) in ip_network(i):
						acceptedaddr=1
						break
				except (ValueError):
					pass
			self.c_connectedmasters.acquire()
			self.c_mmainth.acquire()
			tmpmmainth = self.mmainth.copy()
			tmpconnectedmasters = self.connectedmasters.copy()
			noofmasters = self.noofmasters
			self.c_mmainth.release()
			accepted = True
			if str(addr[0]) in tmpconnectedmasters:
				if self.keepsameipconn == 'old':
					accepted = False
				elif self.keepsameipconn == 'new':
					noofmasters -= 1
			if self.conn and accepted and noofmasters < self.maxconn and (acceptedaddr or not ''.join(self.acceptnetsys)) and self.connectedip and (self.connectedip != str(addr[0])):
				# insert new master connection
				if self.newmasterth in tmpmmainth and self.newmasterth.is_alive():		# valid newmasterth?
					if self.keepsameipconn == 'new' and str(addr[0]) in tmpconnectedmasters:		# already have connection from same ip
						for a in tmpmmainth:
							if a.connectedip == str(addr[0]):
								a.deletemaster = 1							# close and delete the old connection.
								break
					self.newmasterth.connectedip=str(addr[0])
					self.newmasterth.name = 'Master: ' + str(addr[0]) + ':' + str(addr[1])
					self.newmasterth.conn = conn
					self.logfhw.write(str(datetime.now()) + ' : ' + self.newmasterth.name + ' Connected to IP: ' + str(addr[0]) + ', Port: ' + str(addr[1]) + '\n')
					self.logfilechanged=1
				else:
					conn=closeconn(self,0,conn)
				self.newmasterth = 0
			else:
				conn=closeconn(self,0,conn)
				if self.newmasterth and not self.newmasterth.is_alive():
					self.newmasterth = 0
			self.c_connectedmasters.release()
	return conn
	
def closeconnClient(self,setdisconnect=1):
	if self.conn:
		self.connectedip=''
		try:
			self.conn.shutdown(SHUT_RDWR)    # 0 = done receiving, 1 = done sending, 2 = both
			self.conn.close()
			self.conn = 0
		except (error, OSError, ValueError, AttributeError):
			self.conn = 0
		incseqno(self,'I')
		if setdisconnect:
			self.logfhw.write(str(datetime.now()) + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'disconnected .. trying connection ..\n')
			if self.disconnectcause:
				self.logfhw.write('\t\t\t     ' + self.disconnectcause + '\n')
				self.disconnectcause = ''
			self.logfilechanged=1
			initiate(self)
			self.initialize=0
			closemm2ssservers(self)
	return 0

def closeconn(self,setdisconnect=1,conn=0):			# self is for master.
	if not setdisconnect:
		try:
			conn.shutdown(SHUT_RDWR)    # 0 = done receiving, 1 = done sending, 2 = both
			conn.close()
			conn = 0
		except (error, OSError, ValueError, AttributeError):
			conn = 0
		return 0
	elif self.conn:
		try:
			self.conn.shutdown(SHUT_RDWR)    # 0 = done receiving, 1 = done sending, 2 = both
			self.conn.close()
			self.conn = 0
		except (error, OSError, ValueError, AttributeError):
			self.conn = 0
		self.slaveth.logfhw.write(str(datetime.now()) + ' : ' + self.name + ':\n')
		self.slaveth.logfhw.write('\t\t\t     ' + 'Disconnected .. waiting for connection ..\n')
		if self.disconnectcause:
			self.slaveth.logfhw.write('\t\t\t     ' + self.disconnectcause + '\n')
			self.disconnectcause = ''
		self.slaveth.logfilechanged=1
	return 0

def closemm2ssservers(self):
	global exitprogram
	self.c_mmainth.acquire()
	tmpmmainth = self.mmainth.copy()
	self.c_mmainth.release()
	for a in tmpmmainth:
		if exitprogram:
			break
		a.disconnectcause = 'Disconnecting becasue server restarting.'
		a.deletemaster = 1

# read data
def readdata(self):
	if self.conn:
		if self.order:			# master?
			bufsize = self.slaveth.bufsize
		else:
			bufsize = self.bufsize
		if (self.wrpointer+1) != self.rdpointer:
			try:
				data = self.conn.recv(2)
				if data:
					dt = datetime.now()
					packetlen=b'\x00'		# b'\x00'
					if data[0] == 104:
						packetlen=data[1]
					elif data[1] == 104:
						packetlen=self.conn.recv(1)
					if packetlen != b'\x00':
						data = hexlify(self.conn.recv(packetlen))
						self.databuffer[self.wrpointer + 1] = [('68' + "{:02x}".format(packetlen) + data.decode()), str(dt)]
						# if I-Format or S-Format packets?
						i = int(self.databuffer[self.wrpointer + 1][0][4:4+2],16)
						if (i & 1) == 0 or (i & 3) == 1:
							self.sentnorec=0
							self.t1timeout=0
						# if I-Format
						if (i & 1) == 0:
							if not self.recnosend:
								self.t2timeidle=time()
							self.recnosend += 1
						self.timeidle=time()
						self.t3timeidle=time()
						if self.wrpointer == (bufsize - 1):
							self.wrpointer=-1
						else:
							self.wrpointer += 1
					return packetlen
			except (BlockingIOError, error, OSError, ValueError):
				return 0
		return True
	return 0

def senddata(self,data,addtime=0):
	dt = datetime.now()
	while (not len(self.ready_to_write)):
		if not self.conn:
			return str(dt)
	try:
		if self.order:
			kpackets = self.slaveth.k
		else:
			kpackets = self.k
		# if I-Format packet
		if (int.from_bytes(data[2:3], byteorder='little') & 1) == 0:
			# wait for t1 timeout if exceeded k packets send without receive.
			while self.sentnorec > kpackets:
				if not self.conn:
					return str(dt)
			dt = datetime.now()
			if addtime:
				# prepare CP56Time2a time
				ml = int((int(dt.second) * 1000) + (int(dt.microsecond) / 1000))
				min = int(dt.minute)
				hrs = int(dt.hour)
				day = int(((int(dt.weekday()) + 1) * 32) + int(dt.strftime("%d")))
				mon = int(dt.month)
				yr = int(dt.strftime("%y"))
				data = data + ml.to_bytes(2,'little') + min.to_bytes(1,'little') + hrs.to_bytes(1,'little') + day.to_bytes(1,'little') + mon.to_bytes(1,'little') + yr.to_bytes(1,'little')
			# add seq numbers to data packet if it is I format
			data1 = data[0:2] + (self.txlsb*2).to_bytes(1,'little') + self.txmsb.to_bytes(1,'little') + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') + data[6:]
			self.conn.sendall(data1)
			incseqno(self,'TX')
			if not self.sentnorec:
				self.t1timeout = time()
			self.sentnorec += 1
			self.recnosend = 0
			self.t3timeidle=time()
		else:
			self.conn.sendall(data)
			dt = datetime.now()
	except (error, OSError, ValueError, AttributeError):
		pass
	return str(dt)

def incseqno(self,txrx):
	if txrx == 'I':
		self.txlsb=0
		self.txmsb=0
		self.rxlsb=0
		self.rxmsb=0
	elif txrx == 'TX':
		self.txlsb += 1
		if self.txlsb == 128:
			self.txlsb=0
			self.txmsb += 1
			if self.txmsb == 256:
				self.txmsb=0
	elif txrx == 'RX':
		self.rxlsb += 1
		if self.rxlsb == 128:
			self.rxlsb=0
			self.rxmsb += 1
			if self.rxmsb == 256:
				self.rxmsb=0

def initiate(self):
	self.sentnorec=0
	self.t1timeout=0
	self.recnosend=0
	timeidle=time()
	if self.order:		# Master entry?
		self.slaveth.logfilechanged=1
		i = 0
		self.slaveth.c_masterdataactive.acquire()
		for a in self.slaveth.masterdataactive:
			if a == self.order:
				self.slaveth.masterdataactive[i] = 0
				break
			i += 1
		self.slaveth.c_masterdataactive.release()
	else:
		self.startdttime=0
		self.statusvalue="NO"
		self.statuscolor='red'
		self.connectedatvalue=' '
		self.updatestatusgui=1
		self.logfilechanged=1
	self.dataactive=0
	self.rcvtfperiodmin=1000000
	self.time1=0
	# set initialize flag
	self.initialize=1

# read packet from real server to mm2ss client.
def readpacketClient(self):
	global exitprogram
	# if no data for t3 seconds then send testfr packet.
	if ((time() - self.t3timeidle) > self.t3) and self.conn:
		# send testfr act packet
		sendpacket=b'\x68\x04\x43\x00\x00\x00'
		senddata(self,sendpacket)
		self.t3timeidle=time()
	# send S-Format packet if (received w packets and we have space in data buffer) or t2 expired.
	if (self.recnosend >= self.w and (self.wrpointer+1) != self.rdpointer) or (self.recnosend and ((time() - self.t2timeidle) > self.t2)):
		self.recnosend=0
		sendpacket=b'\x68\x04\x01\x00' + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') 
		dt=senddata(self,sendpacket)
	else:
		if (self.wrpointer+1) == self.rdpointer:
			self.logfhw.write(str(datetime.now()) + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'Receiving buffer is full, try to increase buffer or reduce allowed connections.\n')
			self.logfilechanged=1
	self.c_masterdataactive.acquire()
	summasterdataactive = sum(self.masterdataactive)
	self.c_masterdataactive.release()
	if self.conn and not self.startdttime and not self.dataactive and summasterdataactive:			# At least one master connected.
		# send startdt act
		sendpacket=b'\x68\x04\x07\x00\x00\x00'
		dt=senddata(self,sendpacket)
		self.startdttime=time()
		self.logfhw.write(dt + ' : ' + self.logname)
		self.logfhw.write('\t\t\t     ' + 'startdt transmitted.\n')
		self.logfilechanged=1
	elif self.conn and not self.startdttime and self.dataactive and not summasterdataactive:		# No master connected.
		# send stopdt act
		sendpacket=b'\x68\x04\x13\x00\x00\x00'
		dt=senddata(self,sendpacket)
		self.startdttime=time()
		self.logfhw.write(dt + ' : ' + self.logname)
		self.logfhw.write('\t\t\t     ' + 'All masters down, stopdt act transmitted.\n')
		self.logfilechanged=1
	# read from mm2ss servers and send to real server
	readmm2ssserver(self)
	packet=''
	# read the packet from buffer
	if self.rdpointer != self.wrpointer:
		packet, dt=self.databuffer[self.rdpointer+1]
		self.timeidle=time()
		self.t3timeidle=time()
		seqnotxlsb=int(packet[4:4+2],16)
		if self.rdpointer == (self.bufsize - 1):
			self.rdpointer=-1
		else:
			self.rdpointer += 1
		# decode U format packets
		if packet[4:4+2] == '0b':			# startdt con packet
			self.startdttime=0
			self.dataactive=1
			self.logfhw.write(dt + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'startdt con received.' + '\n')
			self.statusvalue="YES"
			self.statuscolor='green'
			self.connectedatvalue=dt
			self.updatestatusgui=1
		elif packet[4:4+2] == '07':			# startdt act packet should not come from slave
			self.startdttime=0
			# send startdt con
			sendpacket=b'\x68\x04\x0B\x00\x00\x00'
			senddata(self,sendpacket)
			self.logfhw.write(dt + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'startdt act received and con transmitted.' + '\n')
			self.statusvalue="YES"
			self.statuscolor='green'
			self.connectedatvalue=dt
			self.updatestatusgui=1
			self.dataactive=1
		elif  packet[4:4+2] == '43':		 	# testfr act packet
			rcvtf=time()
			rcvtfperiod=round(rcvtf - self.time1,1)
			# send testfr con packet
			sendpacket=b'\x68\x04\x83\x00\x00\x00'
			senddata(self,sendpacket)
			if rcvtfperiod < self.rcvtfperiodmin and self.time1 != 0:
				self.rcvtfperiodmin=rcvtfperiod
				self.logfhw.write(dt + ' : ' + self.logname)
				self.logfhw.write('\t\t\t     ' + 'Received testfr act minimum period: ' + "{:04.1f}".format(float(rcvtfperiod)) + ' seconds.' + '\n')
			self.time1=rcvtf
		elif  packet[4:4+2] == '13':		 	# stopdt act packet
			# send stopdt con
			sendpacket=b'\x68\x04\x23\x00\x00\x00'
			senddata(self,sendpacket)
			self.logfhw.write(dt + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'stopdt act received and con transmitted.' + '\n')
			# initialize
			initiate(self)
		elif  packet[4:4+2] == '23':		 	# stopdt con packet
			self.logfhw.write(dt + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'stopdt con received.' + '\n')
			# initialize
			initiate(self)
		elif (int(packet[4:4+2],16) & 0x03) == 1:	# S-format packet.
			pass
		# check if it is I format (bit 0=0 of 3rd byte or 4 and 5 digits of databuffer) then increase RX
		elif (seqnotxlsb & 1) == 0:
			incseqno(self,'RX')
			# end of initialization packet received.
			if packet[12:12+2] == '46':
				pass
			else:
				# forward the packet to mm2ss server
				self.c_mmainth.acquire()
				tmpmmainth = self.mmainth.copy()
				self.c_mmainth.release()
				for a in tmpmmainth:
					if exitprogram:
						break
					org=int(packet[18:18+2],16)
					# if spi, dpi or ami or org=0 then forward to all mm2ss clients.
					# forward control direction I-Frames to master with order = org address.
					if int(packet[12:12+2],16) <= 40 or not org or org == a.order:
						if not a.deletemaster and ((a.packet2server_wrp+1) != a.packet2server_rdp) and a.dataactive:
							a.packet2server[a.packet2server_wrp+1] = bytearray.fromhex(packet)
							if a.packet2server_wrp == (self.bufsize - 1):
								a.packet2server_wrp=-1
							else:
								a.packet2server_wrp += 1
		self.logfilechanged=1

# read packet from real client to mm2ss server.
def readpacket(self):
	global mainth
	# if no data for t3 seconds then send testfr packet.
	if ((time() - self.t3timeidle) > self.slaveth.t3) and self.slaveth.conn:
		# send testfr act packet
		sendpacket=b'\x68\x04\x43\x00\x00\x00'
		senddata(self,sendpacket)
		self.t3timeidle=time()
	# send S-Format packet if (received w packets and we have space in data buffer) or t2 expired.
	if (self.recnosend > self.slaveth.w and (self.wrpointer+1) != self.rdpointer) or (self.recnosend and ((time() - self.t2timeidle) > self.slaveth.t2)):
		self.recnosend=0
		sendpacket=b'\x68\x04\x01\x00' + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') 
		senddata(self,sendpacket)
	else:
		if (self.wrpointer+1) == self.rdpointer:
			self.slaveth.logfhw.write(str(datetime.now()) + ' : ' + self.name)
			self.slaveth.logfhw.write('\t\t\t     ' + 'Receiving buffer is full, try to increase buffer or reduce allowed connections.\n')
			self.slaveth.logfilechanged=1
	# read from mm2ss client and send to real client
	readmm2ssclient(self)
	packet=''
	# read the packet from buffer
	if self.rdpointer != self.wrpointer:
		packet, dt=self.databuffer[self.rdpointer+1]
		self.timeidle=time()
		self.t3timeidle=time()
		seqnotxlsb=int(packet[4:4+2],16)
		if self.rdpointer == (self.slaveth.bufsize - 1):
			self.rdpointer=-1
		else:
			self.rdpointer += 1
		# decode U format packets
		if packet[4:4+2] == '07':			# startdt act packet
			# if mm2ss client connected to real server? then we will reply for everything
			# send startdt con
			sendpacket=b'\x68\x04\x0B\x00\x00\x00'
			senddata(self,sendpacket)
			self.slaveth.logfhw.write(dt + ' : ' + self.name + ':\n')
			self.slaveth.logfhw.write('\t\t\t     ' + 'startdt act/con done.' + '\n')
			if not self.dataactive:
				self.dataactive=1
				self.slaveth.c_mmainth.acquire()
				tmpmmainth = self.slaveth.mmainth.copy()
				self.slaveth.c_mmainth.release()
				i = 0
				for a in tmpmmainth:
					if a == self:
						self.slaveth.c_masterdataactive.acquire()
						self.slaveth.masterdataactive[i] = self.order
						self.slaveth.c_masterdataactive.release()
						break
					i += 1
				# send end of initialization
				sendpacket=b'\x68\x0E\x00\x00\x00\x00\x46\x01\x04\x00' + int(self.slaveth.rtuno).to_bytes(2,'little') + b'\x00\x00\x00\x00'
				dt=senddata(self,sendpacket)
				self.slaveth.logfhw.write(dt + ' : ' + self.name + ':\n')
				self.slaveth.logfhw.write('\t\t\t     ' + 'End of initialization transmitted.' + '\n')
		elif  packet[4:4+2] == '43':		 	# testfr act packet
			rcvtf=time()
			rcvtfperiod=round(rcvtf - self.time1,1)
			# send testfr con packet
			sendpacket=b'\x68\x04\x83\x00\x00\x00'
			senddata(self,sendpacket)
			if rcvtfperiod < self.rcvtfperiodmin and self.time1 != 0:
				self.rcvtfperiodmin=rcvtfperiod
				self.slaveth.logfhw.write(dt + ' : ' + self.name + ':\n')
				self.slaveth.logfhw.write('\t\t\t     ' + 'Received testfr act minimum period: ' + "{:04.1f}".format(float(rcvtfperiod)) + ' seconds.' + '\n')
			self.time1=rcvtf
		elif  packet[4:4+2] == '13':		 	# stopdt act packet
			# send stopdt con
			sendpacket=b'\x68\x04\x23\x00\x00\x00'
			senddata(self,sendpacket)
			self.slaveth.logfhw.write(dt + ' : ' + self.name + ':\n')
			self.slaveth.logfhw.write('\t\t\t     ' + 'stopdt act/con done.' + '\n')
			# initialize
			initiate(self)
		elif (int(packet[4:4+2],16) & 0x03) == 1:	# received S-Format.
			pass
		# check if it is I format (bit 0=0 of 3rd byte or 4 and 5 digits of databuffer) then increase RX
		elif (seqnotxlsb & 1) == 0:
			incseqno(self,'RX')
			# forward the packet to mm2ss client
			if (self.packet2client_wrp+1) != self.packet2client_rdp:
				self.packet2client[self.packet2client_wrp+1] = bytearray.fromhex(packet)
				# set org address to self.order
				self.packet2client[self.packet2client_wrp+1][9:9+1]=self.order.to_bytes(1,'little')
				if self.packet2client_wrp == (self.slaveth.bufsize - 1):
					self.packet2client_wrp = -1
				else:
					self.packet2client_wrp += 1
		self.slaveth.logfilechanged=1

def readmm2ssclient(self):
	# read from mm2ss client and send to real client
	if self.packet2server_rdp != self.packet2server_wrp and self.dataactive:
		packet=self.packet2server[self.packet2server_rdp+1]
		if self.packet2server_rdp == (self.slaveth.bufsize - 1):
			self.packet2server_rdp = -1
		else:
			self.packet2server_rdp += 1
		packet[9:9+1]=b'\x00'	# set org back to 0
		senddata(self,packet)

def write2criticallists(self,op='',index=0,valuemm=0,valueconm=0,valuedatact=0):
	global exitprogram
	if op == 'clear':					# clear lists
		self.mmainth.clear()
		self.connectedmasters.clear()
		self.masterdataactive.clear()
	elif op == 'insert':					# insert new value in list
		self.mmainth.insert(index,valuemm)
		self.connectedmasters.insert(index,valueconm)
		self.masterdataactive.insert(index,valuedatact)
	elif op == 'pop':						# pop index
		self.mmainth.pop(index)
		self.connectedmasters.pop(index)
		self.masterdataactive.pop(index)
	elif op == 'remove':					# remove value
		self.mmainth.remove(valuemm)
		self.connectedmasters.remove(valueconm)
		self.masterdataactive.remove(valuedatact)
	elif op == 'write':					# write value
		self.mmainth[index] = value
		self.connectedmasters[index] = valueconm
		self.masterdataactive[index] = valuedatact
	
def readmm2ssserver(self):
	global exitprogram
	# read from mm2ss servers and send to real server
	self.c_mmainth.acquire()
	tmpmmainth = self.mmainth.copy()
	self.c_mmainth.release()
	for a in tmpmmainth:
		if exitprogram:
			break
		if not a.deletemaster and a.packet2client_rdp != a.packet2client_wrp:
			packet=a.packet2client[a.packet2client_rdp+1]
			if a.packet2client_rdp == (self.bufsize - 1):
				a.packet2client_rdp = -1
			else:
				a.packet2client_rdp += 1
			senddata(self,packet)			

def readpacketthreadClient (self):
	global exitprogram
	initiate(self)
	while True:
		if exitprogram:
			break
		if self.initialize:
			self.logfhw.write(str(datetime.now()) + ' : ' + self.logname)
			self.logfhw.write('\t\t\t     ' + 'Initialized ..\n')
			self.initialize=0
		if self.conn:
			readpacketClient(self)

def readpacketthread (self):
	global exitprogram
	initiate(self)
	while True:
		if exitprogram:
			break
		if self.deletemaster:
			break
		if self.initialize:
			self.slaveth.logfhw.write(str(datetime.now()) + ' : ' + self.name + ':\n')
			self.slaveth.logfhw.write('\t\t\t     ' + 'Initialized ..\n')
			self.initialize=0
		if self.conn:
			readpacket(self)

'''
Returns the epoch time fetched from the NTP server passed as argument.
Returns none if the request is timed out (5 seconds).
'''
def gettime_ntp(addr='time.nist.gov'):
    # http://code.activestate.com/recipes/117211-simple-very-sntp-client/
    TIME1970 = 2208988800      # Thanks to F.Lundh
    client = socket( AF_INET, SOCK_DGRAM )
    data = '\x1b' + 47 * '\0'
    try:
        # Timing out the connection after 5 seconds, if no response received
        client.settimeout(5.0)
        client.sendto( data.encode(), (addr, 123))
        data, address = client.recvfrom( 1024 )
        if data:
            epoch_time = unpack( '!12I', data )[10]
            epoch_time -= TIME1970
            return epoch_time
    except (timeout, gaierror, LookupError):
        return None

def ntpthread():
	global ntpserver,timeupdateevery,exitprogram,timeupdated,updatetimegui
    # Iterates over every server in the list until it finds time from any one.
	while True:
		if exitprogram:
			break
		for server in ntpserver:
			epoch_time = gettime_ntp(server)
			if epoch_time is not None:
				# Local time is obtained using fromtimestamp()
				localTime = datetime.fromtimestamp(epoch_time).strftime("%Y-%m-%d %H:%M:%S")
				timeupdated="Time updated at: " + localTime + " from " + server[0:0+50]
				try:
					if name == 'nt':			# windows
						# SetSystemTime takes time as argument in UTC time. UTC time is obtained using utcfromtimestamp()
						utcTime = datetime.utcfromtimestamp(epoch_time)
						SetSystemTime(utcTime.year, utcTime.month, utcTime.weekday(), utcTime.day, utcTime.hour, utcTime.minute, utcTime.second, 0)
					else:
						localTimetoset = datetime.fromtimestamp(epoch_time).strftime("%H:%M:%S")
						exitcode = system('date +%T -s ' + localTimetoset)
						if WIFEXITED(exitcode):
							if WEXITSTATUS(exitcode):
								timeupdated = "No root privilege, cannot update time."
				except (IOError, BaseException ) as e:
					if name == 'nt':
						if e.args[0] == 1314:
							timeupdated = "No admin privilege, cannot update time."
					else:
						if (e[0] == errno.EPERM):
							timeupdated = "No root privilege, cannot update time."
				break
		updatetimegui=1
		sleep(timeupdateevery)

def restartconnClient(self,message=''):
	if message:
		self.logfhw.write(str(datetime.now()) + ' : ' + message)
		self.logfilechanged=1
	self.conn=closeconnClient(self)
	self.conn=openconnClient(self)


# define iec104 thread for mm2ss client
class iec104threadClient (threading.Thread):
	global nogui
	def __init__(self, threadID, name,portno,rtuno,srvipport,srvport,srvip,csvindex,logevents,bufsize):
		threading.Thread.__init__(self)
		self.threadID = threadID
		self.mmainth=[]				# list of main masters threads
		self.order=0
		self.name = name
		self.logname = name
		self.PORT = portno
		self.connectedip=''
		self.logfilename=''
		self.logfhw=0
		self.logfhr=0
		self.logfilechanged=0
		self.rtunohex = "{:04x}".format(int(rtuno))
		self.rtunohex = self.rtunohex[2:2+2] + self.rtunohex[0:2]
		self.rtuno = rtuno
		self.dataactive=0
		self.masterdataactive=[]
		self.connectedmasters=[]
		self.noofmasters=-1
		self.logevents=logevents
		self.initialize=0
		self.rcvtfperiodmin=1000000
		self.sentnorec=0
		self.t1timeout=0
		self.recnosend=0
		self.srvip=srvip.copy()
		self.srvport=srvport.copy()
		self.acceptnetsys=''
		self.srviprotate = -1
		self.disconnectcause=''
		self.restartconn=0
		self.startdttime=0
		self.index=0
		self.csvindex=csvindex
		self.maxconn=5
		self.bufsize=bufsize
		# threads locks
		self.c_mmainth = threading.Condition()
		self.c_masterdataactive = threading.Condition()
		self.c_connectedmasters = threading.Condition()
		self.newmasterth=0
		self.keepsameipconn='all'			# accept multiple master connections from same ip address

		# py will write this variable when connection disconnected.
		self.txlsb=0
		self.txmsb=0
		self.rxlsb=0
		self.rxmsb=0
		self.conn=0
		self.s=0
		self.time1=0
		# timeidle > t3 (time of testfr packet). if not receiving data during timeidle then disconnect.
		self.timeidle=time()		# after nt3 * t3 disconnect and wait for new connection.
		self.t2timeidle=time()		# send S packet if t2 (10 sec) expired from last received I packet without sending I packet.
		self.t3timeidle=time()		# send testfr packet if t3 expired without send or receive data.
		# timeidle > t3 (time of testfr packet). if not receiving data during timeidle then disconnect.
		self.tdisconnect=60
		# IEC 104 constants
		self.t1=15					# Time-Out of send or test APDU after which we must disconnect if no ack of I-Format packets.
		self.t2=10					# send S-Format if no receive I-format without sending I format for t2 seconds.
		self.t3=20					# send testfr packet if no data for t3 seconds.
		self.w=8
		self.k=12
		# fifo buffer variables used between this mm2ss client and real server
		self.rdpointer=-1
		self.wrpointer=-1
		self.databuffer=[[0] * 2 for i in range(self.bufsize+1)]

		self.ready_to_write=[]

		if not nogui:
			# GUI variables
			self.slaveipportnet=srvipport
			self.filternet=''
			self.lbl_seqno=tk.Label(frame, text=self.csvindex, relief=tk.RIDGE, width=5,bg="white", fg="blue")
			self.lbl_seqno.grid(row=self.threadID-1, column=0)
			self.lbl_sys=tk.Label(frame, text=self.name, relief=tk.RIDGE, width=16,bg="white", fg="red")
			self.lbl_sys.grid(row=self.threadID-1, column=1)
			self.lbl_status=tk.Label(frame, text='NO', relief=tk.RIDGE, width=6, bg="white", fg="red")
			self.lbl_status.grid(row=self.threadID-1, column=2)
			self.statusvalue='NO'
			self.statuscolor='red'
			self.updatestatusgui=0
			self.lbl_portno=tk.Label(frame, text=self.PORT, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_portno.grid(row=self.threadID-1, column=3)
			self.lbl_rtuno=tk.Label(frame, text=self.rtuno, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_rtuno.grid(row=self.threadID-1, column=4)
			self.lbl_connectedat=tk.Label(frame, text=' ',bg="white", relief=tk.RIDGE, width=26, fg="green")
			self.lbl_connectedat.grid(row=self.threadID-1, column=5)
			self.connectedatvalue=' '
			self.cbx_connectedmasters=ttk.Combobox(frame, width=24,values=[""])
			self.cbx_connectedmasters.grid(row=self.threadID-1, column=6)
			CreateToolTip(self.cbx_connectedmasters,"Currently connected masters to this client.")
			#if self.logevents:
			self.cbx_action=ttk.Combobox(frame, width=21,
										values=[
												"Open log file", 
												"Show log in Tab2-Text1",
												"Show log in Tab2-Text2"])
			self.cbx_action.grid(row=self.threadID-1, column=7)
			CreateToolTip(self.cbx_action,"Select action to be applied/executed for Client.")
			self.btn_apply=tk.Button(master=frame, text="Apply", command=lambda: applyaction(self))
			self.btn_apply.grid(row=self.threadID-1, column=8)
			CreateToolTip(self.btn_apply,"Apply action selected in combo box to Client.")

	def run(self):
		global exitprogram,programstarted
		ready_to_read=[]
		message=''
		# wait until starting all threads.
		while not programstarted:
			pass
		cleanuptimeout = time()
		while True:
			if exitprogram:
				# close conn
				if self.conn:
					self.disconnectcause = 'Exiting program.'
					self.conn=closeconnClient(self)
				if self.s:
					self.s = closesocket(self)
				break
			# cleanup deleted masters every 1 second.
			if (time() - cleanuptimeout) > 1:
				tmpth = 0
				# create new thread
				if not self.newmasterth:
					tmpth = iec104thread('New master', self)
					tmpth.daemon = True
					# generate rest of the threads
					tmpth1 = threading.Thread(target=readpacketthread,args=(tmpth,), daemon=True)
					tmpth.readpacketth = tmpth1
				self.c_mmainth.acquire()
				self.c_connectedmasters.acquire()
				self.c_masterdataactive.acquire()
				tmpmmainth = self.mmainth.copy()
				i = 0;j = 0;tmpconnectedmasters = 0
				for a in tmpmmainth:
					if tmpth and not tmpth.order and (a.order - 1) != i:						# we can insert new master here.
						tmpth.order = (i - j) + 1
					if a.deletemaster:
						write2criticallists(self,op='pop',index=(i-j))
						j += 1
						a.readpacketth.join(0.1)
						a.join(0.1)
					elif 'New master' not in a.name:
						if self.connectedmasters[i-j] != a.connectedip:
							self.connectedmasters[i-j] = a.connectedip
							self.updatestatusgui = 1
						tmpconnectedmasters += 1
					i += 1
				if tmpth and not tmpth.order:
						tmpth.order = (i -j) + 1
				if tmpth and tmpth.order:
					# append entry in critical lists at once
					write2criticallists(self,op='insert',index=(tmpth.order-1),valuemm=tmpth,valueconm='0',valuedatact=0)
					tmpth.threadID = int(str(self.threadID) + str(tmpth.order))
				self.c_mmainth.release()
				self.c_masterdataactive.release()
				if self.noofmasters != tmpconnectedmasters:
					self.noofmasters = tmpconnectedmasters
					self.logfhw.write(str(datetime.now()) + ' : ' + self.name + '\n')
					self.logfhw.write('\t\t\t     ' + 'No. of connected masters: ' + str(tmpconnectedmasters) + '\n')
					self.logfilechanged=1
				if tmpth and tmpth.order:
					# allow to open new connection
					tmpth.start()
					tmpth1.start()
					self.newmasterth = tmpth
				self.c_connectedmasters.release()
				cleanuptimeout = time()
			# if I-frame timed out?
			if (self.t1timeout and (time() - self.t1timeout) > self.t1):
				self.disconnectcause = 'Client disconnecting becasue t1 expired before receiving I-Frame ack..'
				self.sentnorec = 0
				self.t1timeout = 0
				self.restartconn=1
			# if not received startdt con after t1 timeout then disconnect
			if self.conn and self.startdttime and ((time() - self.startdttime) > self.t1):
				if self.dataactive:
					message = 'Client - stopdt con not received for ' + str(self.t1) + ' seconds .. disconnecting ..\n'
				else:
					message = 'Client - startdt con not received for ' + str(self.t1) + ' seconds .. disconnecting ..\n'
				self.restartconn=1
				self.startdttime=0
			# timeidle > tdisconnect. if not receiving data during timeidle then disconnect.
			if ((time() - self.timeidle) > self.tdisconnect) and self.conn:
				message = 'Client - No received data for ' + str(self.tdisconnect) + ' seconds .. disconnecting ..\n'
				self.timeidle = time()
				self.restartconn=1
			if self.restartconn:
				self.restartconn=0
				restartconnClient(self,message)
				message=''
			if not self.conn:
				self.conn=openconnClient(self)
			else:
				try:
					ready_to_read, self.ready_to_write, in_error = \
						select([self.conn,], [self.conn,], [], 1)
				except (OSError, WindowsError, ValueError):
					self.disconnectcause = 'Client - Disconnected while trying to select socket.'
					self.restartconn=1
					# connection error event here, maybe reconnect
				if len(ready_to_read) > 0:
					recv=readdata(self)
					if not recv:
						self.disconnectcause = 'Client - Disconnected while reading socket data.'
						self.restartconn=1
		
# define iec104 thread for mm2ss server
class iec104thread (threading.Thread):
	def __init__(self, name, slaveth):
		threading.Thread.__init__(self)
		#self.threadID = threadID
		self.order=0
		self.name = name
		self.slaveth=slaveth		# store slave thread.
		self.readpacketth=0			# store readpacket thread.
		self.connectedip=''
		self.dataactive=0
		self.initialize=0
		self.rcvtfperiodmin=1000000
		self.sentnorec=0
		self.t1timeout=0
		self.recnosend=0
		self.disconnectcause=''
		self.restartconn=0
		self.index=self.slaveth.index
		self.deletemaster=0

		# py will write this variable when connection disconnected.
		self.txlsb=0
		self.txmsb=0
		self.rxlsb=0
		self.rxmsb=0
		self.conn=0
		self.time1=0
		# timeidle > t3 (time of testfr packet). if not receiving data during timeidle then disconnect.
		self.timeidle=time()		# after nt3 * t3 disconnect and wait for new connection.
		self.t2timeidle=time()		# send S packet if t2 (10 sec) expired from last received I packet without sending I packet.
		self.t3timeidle=time()		# send testfr packet if t3 expired without send or receive data.
		# fifo buffer variables used between this mm2ss server and real client
		self.rdpointer=-1
		self.wrpointer=-1
		self.databuffer=[[0] * 2 for i in range(self.slaveth.bufsize+1)]
		# fifo buffer variables used between this mm2ss server thread and mm2ss client thread
		self.packet2client=[0 for i in range(self.slaveth.bufsize+1)]	# fifo buffer where mm2ss server put packet to mm2ss client.
		self.packet2client_rdp=-1							# fifo buffer read pointer used by mm2ss client.
		self.packet2client_wrp=-1							# fifo buffer write pointer used by mm2ss server.
		self.packet2server=[0 for i in range(self.slaveth.bufsize+1)]	# fifo buffer where mm2ss client put packet to mm2ss server.
		self.packet2server_rdp=-1							# fifo buffer read pointer used by mm2ss server.
		self.packet2server_wrp=-1							# fifo buffer write pointer used by mm2ss client.

		self.ready_to_write=[]

	def run(self):
		global exitprogram,programstarted
		ready_to_read=[]
		# wait until starting all threads.
		while not programstarted:
			pass
		while True:
			if exitprogram:
				# close conn
				if self.conn:
					self.disconnectcause = 'Disconnecting to exit program.'
					self.conn=closeconn(self)
				break
			# open socket and connection
			# if I-frame timed out?
			if (self.t1timeout and (time() - self.t1timeout) > self.slaveth.t1) and self.dataactive:
				self.t1timeout = 0
				if self.conn:
					self.disconnectcause = 'Disconnecting becasue t1 expired before receiving I-Frame ack..'
					self.sentnorec = 0
					self.deletemaster=1
			# timeidle > tdisconnect. if not receiving data during timeidle then disconnect.
			if ((time() - self.timeidle) > (self.slaveth.tdisconnect)):
				self.timeidle = time()
				if self.conn:
					self.slaveth.logfhw.write(str(datetime.now()) + ' : ' + self.name + ':\n')
					self.slaveth.logfhw.write('\t\t\t     ' + 'No received data for ' + str(self.slaveth.tdisconnect) + ' seconds .. disconnecting ..\n')
					self.slaveth.logfilechanged=1
					self.deletemaster=1
			if self.deletemaster:
				self.conn=closeconn(self)
				break
			if self.conn:
				if not self.slaveth.conn:
					self.deletemaster=1
				try:
					ready_to_read, self.ready_to_write, in_error = \
						select([self.conn,], [self.conn,], [], 1)
				except (OSError, WindowsError, ValueError):
					self.disconnectcause = 'Disconnected while selecting socket.'
					self.deletemaster=1
					# connection error event here, maybe reconnect
				if len(ready_to_read) > 0:
					recv=readdata(self)
					if not recv:
						self.disconnectcause = 'Disconnected while reading socket data.'
						self.deletemaster=1

def managemastersthread(self):
	global exitprogram
	#socktimeout = 0
	while True:
		if exitprogram:
			break
		# open socket.
		if not self.s:
			self.s = opensocket(self.PORT)
		if self.conn and self.s and self.newmasterth:
			conn = openconn(self)

					
def restartaction(self,ind):
	global txtbx1thid,txtbx2thid,updatetoframe1,updatetoframe2,portnolist
	if ind == 1:
		# take sysname, rtuno, portno and filter from frame1
		sysname = ent_sys1.get()
		rtuno = ent_rtuno1.get()
		portno = ent_portno1.get()
		slaveipportnet = ent_slaveipport1.get()
		filternet = ent_filter1.get()
	else:
		# take sysname, rtuno, portno and filter from frame2
		sysname = ent_sys2.get()
		portno = ent_portno2.get()
		rtuno = ent_rtuno2.get()
		slaveipportnet = ent_slaveipport2.get()
		filternet = ent_filter2.get()
	tmplist=portnolist.copy()
	tmplist.remove(str(self.PORT))
	if not portno or not rtuno or not sysname:
		messagebox.showerror("Error", 'Port, RTU numbers and System name are required.')
	elif not int(rtuno) or not int(portno):
		messagebox.showerror("Error", 'Wrong port ' + portno + ' or rtu ' + rtuno +', must not equal zero.')
	elif portno in tmplist:
		messagebox.showerror("Error", 'Wrong port ' + portno +', already used for other masters.')
	# confirm from user
	elif messagebox.askokcancel("Restart sys", 'Do you want to restart "' + self.csvindex + '" with:\nName: ' + sysname + '\nPort: ' + portno + '\nRTU: ' + rtuno + '\nIPs:Ports: ' + slaveipportnet + '\nFilter: ' + filternet):
		# close connection and socket
		if not self.order:		# slave RTU entry
			tmpipportlist1=slaveipportnet.split(';')
			srvip=[]
			srvport=[]
			for a in tmpipportlist1:
				tmpipportlist=a.split(':')
				if len(tmpipportlist) >= 2 and tmpipportlist[0] and tmpipportlist[1].isdigit() and int(tmpipportlist[1]) in range(1,65535):	# port no. is ok?
					srvip.append(tmpipportlist[0])
					srvport.append(tmpipportlist[1])
			if not srvport or not ''.join(srvport) or not srvip or not ''.join(srvip):
				messagebox.showerror("Error", 'Wrong port number, must be in range (1,65535).')
			else:
				self.name=sysname
				portnolist.remove(str(self.PORT))
				portnolist.append(portno)
				self.PORT=int(portno)
				self.rtuno=int(rtuno)
				self.srvip.clear()
				self.srvip=srvip.copy()
				self.srvport.clear()
				self.srvport=srvport.copy()
				self.slaveipportnet=slaveipportnet
				self.acceptnetsys.clear()
				self.acceptnetsys=filternet.split(';')
				self.filternet=filternet
				if self.s:
					self.s = closesocket(self)
				self.restartconn=1
		self.logfhw.write(str(datetime.now()) + ' : Restarting as per user request.\n')
		self.logfilechanged=1
	if txtbx1thid == self:
		updatetoframe1=1
	if txtbx2thid == self:
		updatetoframe2=1

def applyaction(self):
	global updatetoframe1,updatetoframe2,txtbx1thid,txtbx2thid
	cursel=self.cbx_action.current()
	if cursel == 0:
		# open log file
		if self.logfilechanged:
			self.logfhw.flush()
		system('start notepad ' + self.logfilename)
	elif cursel == 1:
		# Show log in textbox 1
		txtbx1thid=self
		updatetoframe1=1
	elif cursel == 2:
		# Show log in textbox 2
		txtbx2thid=self
		updatetoframe2=1

def copytoframe1(self,fileonly=0):
	global txtbx1thid
	self.logfhw.flush()
	txtbx1thid=self
	if not fileonly:
		lbl_seqno1.configure(text=self.lbl_seqno["text"])
		self.lbl_portno.configure(text=str(self.PORT))
		ent_portno1.delete(0, 'end')
		ent_portno1.insert(tk.END, str(self.PORT))
		self.lbl_rtuno.configure(text=self.rtuno)
		ent_rtuno1.delete(0, 'end')
		ent_rtuno1.insert(tk.END, self.rtuno)
		#str_filter1.set(self.filternet)
		ent_slaveipport1.delete(0, 'end')
		ent_slaveipport1.insert(tk.END, self.slaveipportnet)
		ent_filter1.delete(0, 'end')
		ent_filter1.insert(tk.END, self.filternet)
		btn_restart1.configure(state='normal')
		btn_restart1.configure(command=lambda: restartaction(self,1))
		# update status
		self.lbl_sys.configure(text=self.name,fg=self.statuscolor)
		ent_sys1.delete(0, 'end')
		ent_sys1.insert(tk.END, self.name)
		ent_sys1.configure(fg=self.statuscolor)
		lbl_status1.configure(text=self.lbl_status["text"],fg=self.lbl_status["fg"])
		lbl_connectedat1.configure(text=self.lbl_connectedat["text"],fg=self.lbl_connectedat["fg"])
	self.logfhr.seek(0)
	datatotext = self.logfhr.read()
	text_box1.config(state=tk.NORMAL)
	text_box1.delete('1.0', tk.END)
	text_box1.insert(tk.END, datatotext)
	text_box1.see(tk.END)
	text_box1.config(state=tk.DISABLED)

def copytoframe2(self,fileonly=0):
	global txtbx2thid
	self.logfhw.flush()
	txtbx2thid=self
	if not fileonly:
		lbl_seqno2.configure(text=self.lbl_seqno["text"])
		self.lbl_portno.configure(text=str(self.PORT))
		ent_portno2.delete(0, 'end')
		ent_portno2.insert(tk.END, str(self.PORT))
		self.lbl_rtuno.configure(text=self.rtuno)
		ent_rtuno2.delete(0, 'end')
		ent_rtuno2.insert(tk.END, self.rtuno)
		#str_filter2.set(self.filternet)
		ent_slaveipport2.delete(0, 'end')
		ent_slaveipport2.insert(tk.END, self.slaveipportnet)
		ent_filter2.delete(0, 'end')
		ent_filter2.insert(tk.END, self.filternet)
		btn_restart2.configure(state='normal')
		btn_restart2.configure(command=lambda: restartaction(self,2))
		# update status
		self.lbl_sys.configure(text=self.name,fg=self.statuscolor)
		ent_sys2.delete(0, 'end')
		ent_sys2.insert(tk.END, self.name)
		ent_sys2.configure(fg=self.statuscolor)
		lbl_status2.configure(text=self.lbl_status["text"],fg=self.lbl_status["fg"])
		lbl_connectedat2.configure(text=self.lbl_connectedat["text"],fg=self.lbl_connectedat["fg"])
	self.logfhr.seek(0)
	datatotext = self.logfhr.read()
	text_box2.config(state=tk.NORMAL)
	text_box2.delete('1.0', tk.END)
	text_box2.insert(tk.END, datatotext)
	text_box2.config(state=tk.DISABLED)
	text_box2.see(tk.END)

def onFrameConfigure(canvas):
    #Reset the scroll region to encompass the inner frame
    canvas.configure(scrollregion=canvas.bbox("all"))

def digitvalidation(input,key,name):
	if 'index' in name:
		if len(input) < 13 and (input.isdigit() or input == ""):
			return True
		else:
			return False
	elif 'duration' in name:
		if len(input) < 8 and (input.isdigit() or input == ""):
			return True
		else:
			return False
	elif 'sysname' in name:
		if len(input) < 17 or input == "":
			return True
		else:
			return False
	elif 'slaveipport' in name or 'filter' in name:
		if all(c in "0123456789;/.:" for c in input):
			return True
		else:
			return False
	elif 'port' in name or 'rtu' in name:
		if input == "":
			return True
		elif input.isdigit():
			if int(input) <= 65535:
				return True
			else:
				return False
		else:
			return False

def on_closing():
	global exitprogram
	if messagebox.askokcancel("Quit", "Do you want to quit?"):
		exitprogram=1

class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        # "Display text in tooltip window"
        self.text = text
        if self.tipwindow or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except (TypeError):
            x = 1;y = 1;cx = 2;cy = 2
        x = x + self.widget.winfo_rootx() + 57
        y = y + cy + self.widget.winfo_rooty() +27
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                      background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                      font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

def CreateToolTip(widget, text):
    toolTip = ToolTip(widget)
    def enter(event):
        toolTip.showtip(text)
    def leave(event):
        toolTip.hidetip()
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)		
		
		
# *****************************************************
#                       Main code
# -----------------------------------------------------

signal(SIGTERM, signal_term_handler)

register(cleanup)

# get program arguments
# -h or --help							help message
# -i or --ini							init file
# -t or --ntp_update_every_sec			NTP update interval
# -s or --ntp_server					NTP server
# -c or --service						Run as Windows service
notourarg = 0
argvl = argv[1:]
try:
	options, args = getopt(argvl, "i:t:s:hcn",
						["ini=",
						"ntp_update_every_sec=",
						"ntp_server=",
						"help",
						"service",
						"nogui"])
except:
	if name == 'nt':
		notourarg = 1
	else:
		print(helpmess)
		exit()

# parse program aguments
if not notourarg:
	for argname, argvalue in options:
		if argname in ['-h', '--help']:
			print(helpmess)
			exit()
		elif argname in ['-n', '--nogui']:
			nogui = 1
		elif argname in ['-c', '--service']:
			runasservice = 1
			nogui = 1
		elif argname in ['-i', '--ini']:
			initfile = argvalue
		elif argname in ['-t','--ntp_update_every_sec']:
			if argvalue.isdigit():
				timeupdateevery=int(argvalue)
		elif argname in ['-s', '--ntp_server']:
			ntpserver.append(argvalue)

# under windows only, if run as service? or user provide one program argument not starting with '-' such as 'install'
if name == 'nt' and (runasservice or notourarg or (len(argv) > 1 and argv[1][0:1] != '-')):
	from win32serviceutil import ServiceFramework, HandleCommandLine
	from win32service import SERVICE_STOP_PENDING
	from win32event import CreateEvent, SetEvent, WaitForSingleObject, INFINITE
	from servicemanager	import LogMsg, EVENTLOG_INFORMATION_TYPE, PYS_SERVICE_STARTED, Initialize, PrepareToHostSingle, StartServiceCtrlDispatcher

	class iec104mm2ssService(ServiceFramework):
		global argv
		_svc_name_ = 'iec104mm2ss'
		_svc_display_name_ = 'IEC104-Multiple Masters to Single Slave'
		_svc_description_ = 'Connecting Multiple IEC 104 Masters to Single Slave'
		if '.exe' in argv[0]:
			_exe_name_ = argv[0]
		else:
			_exe_name_ = argv[0] + '.exe'
		_exe_args_ = '-c'
		
		def __init__(self, args):
			ServiceFramework.__init__(self, args)
			self.hWaitStop = CreateEvent(None, 0, 0, None)
			setdefaulttimeout(60)
			
		def SvcStop(self):
			global exitprogram
			exitprogram = 1				# exit program
			self.ReportServiceStatus(SERVICE_STOP_PENDING)
			SetEvent(self.hWaitStop)
			
		def SvcDoRun(self):
			global programstarted, initfile
			programstarted = 1
			LogMsg(EVENTLOG_INFORMATION_TYPE, 
								  PYS_SERVICE_STARTED, (self._svc_name_, initfile))
			WaitForSingleObject(self.hWaitStop, INFINITE)

	def servicethread():
		StartServiceCtrlDispatcher()		# will not return untill service stopped
	
	if notourarg or (len(argv) > 1 and argv[1][0:1] != '-'):
		HandleCommandLine(iec104mm2ssService)
		exit()
	else:
		dir = '\\'.join(argv[0].split('\\')[0:-1]) + '\\'
		initfile = dir + initfile
		dir += 'log\\'
		Initialize()
		PrepareToHostSingle(iec104mm2ssService)
		LogMsg(EVENTLOG_INFORMATION_TYPE, 
							  PYS_SERVICE_STARTED, ('iec104mm2ss', 'before starting thread'))
		tmpth1 = threading.Thread(target=servicethread,args=(), daemon=True)
		th.append(tmpth1)
		tmpth1.start()

# create log folder
try:
	mkdir(dir)
except FileExistsError:
	pass

# read init file
#ntpserver,10.1.1.15,,
#ntp_server,time.windows.com,,
#ntp_server,pool.ntp.org,,
#ntp_update_every_sec,900,,
# id,sys name,portno,rtuno,hosts
initialfileisok = False
if isfile(initfile):
	with open(initfile) as csv_file:
		#variable=value
		csv_reader = reader(csv_file, delimiter=',')
		for row in csv_reader:
			if not row:
				pass
			# if first character of first column in any row = '!' then break
			elif row[0][0:1] == '!' or exitprogram:
				break
			# check initial file version
			elif not initialfileisok and 'iec104MM2SS-1port-v1.0' not in row[0]:
				print('Error .. wrong initial file.\nPlease be sure to use correct file version .. Exiting.\n')
				exit()
			# general settings
			elif len(row) >= 2 and row[0] == 'ntp_update_every_sec' and row[1].isdigit():
				timeupdateevery=int(row[1])
			elif len(row) >= 1 and row[0] == 'nogui':
				nogui = 1
			elif len(row) >= 2 and row[0] == 'ntp_server' and row[1]:
				ntpserver.append(row[1])
			initialfileisok = True

nullfilew = open(devnull, 'w')
#nullfiler = open(devnull, 'r')

if not nogui:
	import tkinter as tk
	from tkinter import ttk
	from tkinter.font import Font
	from tkinter import messagebox
	# create GUI
	window = tk.Tk()
	#window.geometry("1270x670+0+0")
	window.geometry("1235x630+0+0")
	#window.state('zoomed')
	window.resizable(False, False)
	window.title("IEC-104 Many clients to one server")

	tab_parent = ttk.Notebook(window)

	tab_canvas = ttk.Frame(tab_parent)
	tab_textbox = ttk.Frame(tab_parent)

	tab_parent.add(tab_canvas, text="Tab1: Full Systems list")
	tab_parent.add(tab_textbox, text="Tab2: Log files and data edit")

	tab_parent.grid(row=3, column=1,columnspan=127,rowspan=64,sticky="nsew")

	for i in range(0,128):
		window.rowconfigure(i, minsize=10, weight=1)
		tab_canvas.rowconfigure(i, minsize=10, weight=1)
		tab_textbox.rowconfigure(i, minsize=10, weight=1)
	for i in range(0,72):
		window.columnconfigure(i, minsize=10, weight=1)
		tab_canvas.columnconfigure(i, minsize=10, weight=1)
		tab_textbox.columnconfigure(i, minsize=10, weight=1)
	
	myFont = Font(family="Courier New", size=10)

	dt=str(datetime.now())
	lbl_startedat = tk.Label(master=window,relief=tk.GROOVE, borderwidth=3, fg='blue', text='Started at: ' + dt)
	lbl_startedat.grid(row=1, column=1,columnspan=30,rowspan=2,sticky="nw")

	reg = window.register(digitvalidation)

	lbl_adminpriv = tk.Label(master=window,relief=tk.GROOVE, text=' ')
	lbl_adminpriv.grid(row=1, column=55,columnspan=60,rowspan=2,sticky="nw")

	#      System        Online    Port  RTU    Online(startdt) at       Connected masters           Select action           Apply
	# 1234567890123456    Yes     12345 12345  2021-04-22 06:27:47.462463  Open GI log file           Apply
	#																				      	   Open log file
	#																					 	   Show log in textbox 1
	#																					       Show log in textbox 2
	lbl_header = tk.Label(master=tab_canvas, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System      Online  Port RTU      Online(startdt) at        Connected masters           Select action       Apply')
	lbl_header.grid(row=1, column=1,columnspan=100,rowspan=2,sticky="nw")

	canvas = tk.Canvas(tab_canvas, borderwidth=0, background="#ffffff")
	frame = tk.Frame(canvas, background="#ffffff")
	frame.option_add("*Font", myFont)
	vsb = tk.Scrollbar(tab_canvas, orient="vertical", command=canvas.yview)
	canvas.configure(yscrollcommand=vsb.set)
	vsb.grid(column=100, row=3,rowspan=50,columnspan=2, sticky="nse")
	canvas.grid(row=3, column=1,columnspan=100,rowspan=50,sticky="nsew")
	canvas.create_window((4,4), window=frame, anchor="nw")
	frame.bind("<Configure>", lambda event, canvas=canvas: onFrameConfigure(canvas))

	# first frame and textbox1
	frame1 = tk.Frame(tab_textbox)
	frame1.option_add("*Font", myFont)
	frame1.grid(row=3, column=0,columnspan=130,rowspan=2,sticky="nsew")
	lbl_header1 = tk.Label(master=tab_textbox, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System     Online  Port RTU        Connected at               Slave IP:Port             Filter net/IP        Restart ')
	lbl_header1.grid(row=1, column=0,columnspan=130,rowspan=2,sticky="nw")
	row=0
	lbl_seqno1=tk.Label(frame1, text=' ', relief=tk.GROOVE, width=5,bg="white", fg="blue")
	lbl_seqno1.grid(row=row, column=1)
	ent_sys1=tk.Entry(frame1, name='sysname', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=16,bg="light yellow", fg="blue")
	ent_sys1.grid(row=row, column=2)
	CreateToolTip(ent_sys1,"Enter new System/RTU name (max. 14 char).")
	lbl_status1=tk.Label(frame1, text=' ', relief=tk.GROOVE, width=6, bg="white", fg="green")
	lbl_status1.grid(row=row, column=3)
	ent_portno1=tk.Entry(frame1, name='port', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=5, bg="light yellow", fg="blue")
	ent_portno1.grid(row=row, column=4)
	CreateToolTip(ent_portno1,"Enter new unique port number (1-65535).")
	ent_rtuno1=tk.Entry(frame1, name='rtu', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=5, bg="light yellow", fg="blue")
	ent_rtuno1.grid(row=row, column=5)
	CreateToolTip(ent_rtuno1,"Enter new RTU number (1-65535).")
	lbl_connectedat1=tk.Label(frame1, text=' ',bg="white", relief=tk.GROOVE, width=26, fg="green")
	lbl_connectedat1.grid(row=row, column=6)
	ent_slaveipport1 = tk.Entry(frame1, name='slaveipport', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_slaveipport1.grid(row=row, column=7, sticky="nsew")
	CreateToolTip(ent_slaveipport1,"Enter new ip:ports separated by ;\nnexample: 192.168.1.1:2404;10.1.1.100:2405")
	ent_filter1 = tk.Entry(frame1, name='filter', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_filter1.grid(row=row, column=8, sticky="nsew")
	CreateToolTip(ent_filter1,"Enter new filter hosts or networks separated by ;\nnexample: 192.168.1.0/24;10.1.1.100")
	btn_restart1 = tk.Button(master=frame1, text="Restart")
	btn_restart1.grid(row=row, column=9,rowspan=2,sticky="nw")
	CreateToolTip(btn_restart1,"Restart\nwith new\nsettings.")

	text_box1 = tk.Text(tab_textbox)
	text_box1.grid(row=5, column=0,columnspan=120,rowspan=21, sticky="nsew")
	sb1 = ttk.Scrollbar(tab_textbox, orient="vertical", command=text_box1.yview)
	sb1.grid(column=120, row=5,rowspan=21, columnspan=6, sticky="nse")
	text_box1['yscrollcommand'] = sb1.set
	text_box1.config(state=tk.DISABLED)
	CreateToolTip(text_box1,"Tab2-text1: Log file of the selected System/RTU is displayed here..")

	# second frame and textbox2
	frame2 = tk.Frame(tab_textbox)
	frame2.option_add("*Font", myFont)
	frame2.grid(row=29, column=0,columnspan=130,rowspan=2,sticky="nsew")
	lbl_header2 = tk.Label(master=tab_textbox, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System     Online  Port RTU        Connected at               Slave IP:Port             Filter net/IP        Restart ')
	lbl_header2.grid(row=27, column=0,columnspan=130,rowspan=2,sticky="nw")
	row=0
	lbl_seqno2=tk.Label(frame2, text=' ', relief=tk.GROOVE, width=5,bg="white", fg="blue")
	lbl_seqno2.grid(row=row, column=1)
	ent_sys2=tk.Entry(frame2, name='sysname', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=16,bg="light yellow", fg="blue")
	ent_sys2.grid(row=row, column=2)
	CreateToolTip(ent_sys2,"Enter new System/RTU name (max. 14 char).")
	lbl_status2=tk.Label(frame2, text=' ', relief=tk.GROOVE, width=6, bg="white", fg="green")
	lbl_status2.grid(row=row, column=3)
	ent_portno2=tk.Entry(frame2, name='port', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=5, bg="light yellow", fg="blue")
	ent_portno2.grid(row=row, column=4)
	CreateToolTip(ent_portno2,"Enter new unique port number (1-65535).")
	ent_rtuno2=tk.Entry(frame2, name='rtu', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=5, bg="light yellow", fg="blue")
	ent_rtuno2.grid(row=row, column=5)
	CreateToolTip(ent_rtuno2,"Enter new RTU number (1-65535).")
	lbl_connectedat2=tk.Label(frame2, text=' ',bg="white", relief=tk.GROOVE, width=26, fg="green")
	lbl_connectedat2.grid(row=row, column=6)
	ent_slaveipport2 = tk.Entry(frame2, name='slaveipport', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_slaveipport2.grid(row=row, column=7, sticky="nsew")
	CreateToolTip(ent_slaveipport2,"Enter new ip:port separated by ;\nexample: 192.168.1.1:2404;10.1.1.100:2405")
	ent_filter2 = tk.Entry(frame2, name='filter', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_filter2.grid(row=row, column=8, sticky="nsew")
	CreateToolTip(ent_filter2,"Enter new filter hosts or networks separated by ;\nnexample: 192.168.1.0/24;10.1.1.100")
	btn_restart2 = tk.Button(master=frame2, text="Restart")
	btn_restart2.grid(row=row, column=9,rowspan=2, sticky="nw")
	CreateToolTip(btn_restart2,"Restart\nwith new\nsettings.")

	text_box2 = tk.Text(tab_textbox)
	text_box2.grid(row=31, column=0,columnspan=120,rowspan=21, sticky="nsew")
	sb2 = ttk.Scrollbar(tab_textbox, orient="vertical", command=text_box2.yview)
	sb2.grid(column=120, row=31,rowspan=21, columnspan=6, sticky="nse")
	text_box2['yscrollcommand'] = sb2.set
	text_box2.config(state=tk.DISABLED)
	CreateToolTip(text_box2,"Tab2-text2: Log file of the selected System/RTU is displayed here..")

	window.protocol("WM_DELETE_WINDOW", on_closing)

# read init file
#ntpserver,10.1.1.15,,
#ntp_server,time.windows.com,,
#ntp_server,pool.ntp.org,,
#ntp_update_every_sec,900,,
# id,sys name,portno,rtuno,hosts
if isfile(initfile):
	with open(initfile) as csv_file:
		#variable=value
		csv_reader = reader(csv_file, delimiter=',')
		noofsys=0
		for row in csv_reader:
			if not row:
				pass
			# if first character of first column in any row = '!' then break
			elif row[0][0:1] == '!' or exitprogram:
				break
			# Slave (RTU) entries - each row should start with integer, then sys name, portno, rtuno, maxconn. idletime, t1, t2, t3, w, k, buffsize, logevents, hosts IP:PORT;IP:PORT, master filter.
			elif len(row) >= 16 and row[0].isdigit() and row[2].isdigit() and row[3].isdigit() and row[2] not in portnolist and int(row[2]) in range(1,65535) and int(row[3]) in range(1,65535) and row[14]:
				tmplist=row[14].split(';')
				srvip=[]
				srvport=[]
				for a in tmplist:
					tmpipportlist=a.split(':')
					if tmpipportlist[0] and tmpipportlist[1].isdigit() and int(tmpipportlist[1]) in range(1,65535):	# port no. is ok?
						srvip.append(tmpipportlist[0])
						srvport.append(tmpipportlist[1])
				if srvport and ''.join(srvport) and srvip and ''.join(srvip) and (row[0] not in csvindexlist):
					portnolist.append(row[2])
					srvipport = row[14]
					csvindexlist.append(row[0])
					indexlist.append(noofsys)
					if row[12] and row[12] == 'Y':
						logevents = 1
					else:
						logevents = 0
					if row[10].isdigit() and int(row[10]) > 0:
						k = int(row[10])
					else:
						k=12
					if row[11].isdigit() and int(row[11]) >= k:
						bufsize = int(row[11])
					else:
						bufsize=1000
					tmpth = iec104threadClient(noofsys+1, row[1][0:0+16],int(row[2][0:0+5]),int(row[3][0:0+5]),srvipport,srvport,srvip,row[0],logevents,bufsize)
					mainth.append(tmpth)
					tmpth.daemon = True
					tmpth.index=noofsys
					# generate unique log file name for mm2ss client
					dt=datetime.now()
					currentdate=dt.strftime("%b%d%Y-%H-%M-%S-%f")
					logfilename=row[1] + '-' + currentdate + '-' + row[2]
					tmpth.logfilename = dir + logfilename + '.txt'
					tmpth.logfhw=open(dir + logfilename + '.txt',"w")
					# identify log files
					tmpth.logfhw.write(tmpth.name + ' log file .. RTU: ' + str(tmpth.rtuno) + '\n')
					tmpth.logfhr=open(dir + logfilename + '.txt',"r")
					if not tmpth.logevents:
						tmpth.logfhw.write('Log disabled, you can enable it for this slave in the initial csv file.\n')
						tmpth.logfhw.close()
						tmpth.logfhw=nullfilew
					if row[15]:
						tmpth.acceptnetsys=row[15].split(';')
						tmpth.filternet=row[15]
					if row[4][0:0+5].isdigit() and int(row[4][0:0+5]) > 0:
						tmpth.maxconn = int(row[4][0:0+5])
					# fill iec104 constants
					if row[5].isdigit() and int(row[5]) > 0:
						tmpth.tdisconnect=int(row[5])
					if row[6].isdigit() and int(row[6]) > 0:
						tmpth.t1=int(row[6])
					if row[7].isdigit() and int(row[7]) > 0:
						tmpth.t2 = int(row[7])
					if row[8].isdigit() and int(row[8]) > 0:
						tmpth.t3 = int(row[8])
					if row[9].isdigit() and int(row[9]) > 0:
						tmpth.w = int(row[9])
					tmpth.k = k
					if row[13] and row[13] in ['all','old','new']:
						tmpth.keepsameipconn = row[13]
					# create GUI resources for mm2ss client - 8 gadgets
					# label:ID (5 char) label:System(16 char) label:Online (Yes/No) label:Port label:GI(Run) label:connected at(26 char) listbox:Action(30 char) button:Action
					# added to the class construction
					tmpth.start()
					# generate rest of the threads
					tmpth1 = threading.Thread(target=readpacketthreadClient,args=(tmpth,), daemon=True)
					th.append(tmpth1)
					tmpth1.start()
					tmpth1 = threading.Thread(target=managemastersthread,args=(tmpth,), daemon=True)
					th.append(tmpth1)
					tmpth1.start()
					noofsys += 1
			if not nogui:
				window.update()

# we should have at least 1 group (slave) entry.
if not noofsys:
	if not nogui:
		messagebox.showerror("Error", 'Found ' + str(noofsys) + ' Systems .. Exiting.\nTry "-h" or "--help"')
	else:
		print('Error .. Found ' + str(noofsys) + ' Systems .. Exiting.\nTry "-h" or "--help"')
	exit()

if not nogui:
	if noofsys == 1:
		copytoframe1(mainth[0])
		copytoframe2(mainth[0])
	else:
		copytoframe1(mainth[0])
		copytoframe2(mainth[1])

# starting thread of ntp server update
if	ntpserver:
	if not nogui:
		lbl_adminpriv.configure(text='Trying NTP servers to update local time ..',fg='red')
	tmpth = threading.Thread(target=ntpthread, daemon=True)
	th.append(tmpth)
	tmpth.start()
	
# all thread started, ready.
if not runasservice:
	programstarted=1

logupdate = time()

while True:
	try:
		if exitprogram:
			break

		if nogui:
			# flush log files every 'logupdateperiod' seconds.
			if (time() - logupdate) > logupdateperiod:
				for a in mainth:
					if a.logfilechanged:
						a.logfilechanged=0
						a.logfhw.flush()
				logupdate = time()
		else:
			# update ntp gui
			if 'Time updated' in timeupdated:
				lbl_adminpriv.configure(text=timeupdated,fg='green')
				timeupdated=''
				updatetimegui=0
			elif 'privilege' in timeupdated:
				lbl_adminpriv.configure(text=timeupdated,fg='red')
				timeupdated=''
				updatetimegui=0
			elif updatetimegui:
				timeupdated=''
				updatetimegui=0
				lbl_adminpriv.configure(fg='red')

			for a in mainth:
				if exitprogram:
					break
				# update gui
				# status of connection
				if a.updatestatusgui:
					a.updatestatusgui=0
					a.lbl_sys.configure(fg=a.statuscolor)
					a.lbl_status.configure(text=a.statusvalue,fg=a.statuscolor)
					a.lbl_connectedat.configure(text=a.connectedatvalue,fg='green')
					tmplist.clear()
					a.c_mmainth.acquire()
					tmpmmainth = a.mmainth.copy()
					a.c_mmainth.release()
					for b in tmpmmainth:
						if 'New master' not in b.name and not b.deletemaster:
							tmplist.append(b.name)
					a.cbx_connectedmasters.configure(values=tmplist)
					if a == txtbx1thid:
						ent_sys1.configure(fg=a.statuscolor)
						lbl_status1.configure(text=a.statusvalue,fg=a.statuscolor)
						lbl_connectedat1.configure(text=a.connectedatvalue,fg='green')
					if a == txtbx2thid:
						ent_sys2.configure(fg=a.statuscolor)
						lbl_status2.configure(text=a.statusvalue,fg=a.statuscolor)
						lbl_connectedat2.configure(text=a.connectedatvalue,fg='green')
				window.update()

			# print frame1 log file
			if updatetoframe1:
				updatetoframe1=0
				copytoframe1(txtbx1thid)
			elif txtbx1thid.logfilechanged:
				txtbx1thid.logfilechanged=0
				txtbx1thid.logfhw.flush()
			textsize=len(text_box1.get('1.0',tk.END)) + int(text_box1.index('end').split('.')[0]) - 3
			if txtbx1thid.logevents and getsize(txtbx1thid.logfilename) != textsize:
				copytoframe1(txtbx1thid,fileonly=1)

			# print frame2 log file
			if updatetoframe2:
				updatetoframe2=0
				copytoframe2(txtbx2thid)
			elif txtbx2thid.logfilechanged:
				txtbx2thid.logfilechanged=0
				txtbx2thid.logfhw.flush()
			textsize=len(text_box2.get('1.0',tk.END)) + int(text_box2.index('end').split('.')[0]) - 3
			if txtbx2thid.logevents and getsize(txtbx2thid.logfilename) != textsize:
				copytoframe2(txtbx2thid,fileonly=1)
			
	except KeyboardInterrupt:
		break
exit()
