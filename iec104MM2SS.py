#!/usr/bin/env python3
#
# ******************************************************
# IEC 104 Multiple Masters to Single Slave (IEC104MM2SS
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
# *****************************************************
#                       Imports
# ------------------------------------------------------
#import tkinter as tk
#from tkinter import ttk
#from tkinter.font import Font
#from tkinter import messagebox
from getopt import getopt
from ipaddress import ip_address,ip_network
import threading
from os import remove,stat,mkdir,system,name
from datetime import datetime
from socket import socket,AF_INET,SOCK_STREAM,SOL_SOCKET,SO_REUSEADDR,SHUT_RDWR,error,timeout,SOCK_DGRAM,gaierror
from binascii import hexlify
from signal import signal,SIGTERM
from struct import unpack,pack
from select import select
from sys import argv,byteorder,exit
from time import time,sleep
from os.path import isfile,getsize
from csv import reader
from atexit import register
if name == 'nt':
	from win32api import SetSystemTime
else:
	from os import WIFEXITED,WEXITSTATUS

#import ctypes

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
helpmess=help1+help2+help3+help4+help5+help6+help7+help8+help9
if name == 'nt':
	dir='log\\'
	datadir='data\\'
	initfile='iec104mm2ss.csv'
else:
	dir='./log/'
	datadir='./data/'
	initfile='./iec104mm2ss.csv'

ntpserver=[]
timeupdated=''
updatetimegui=0
timeupdateevery=900		# in seconds
#rtuno=0
idletime=60
t2=10					# send S-Format if no receive I-format without sending I format for t2 seconds.
t3=20					# send testfr packet if no data for t3 seconds.
w=8
k=12

exitprogram=0

bufsize=100
mainth=[[]]
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

# *****************************************************
#                       Functions
# -----------------------------------------------------
def signal_term_handler(signal, frame):
	exit()

def cleanup():
	global exitprogram,mainth,th,window,nogui
	exitprogram=1
	fh=[]
	for row in mainth:
		for a in row:
			if a:
				a.dataactive=0
				fh.append(a.logfhw)
				fh.append(a.logfhr)
	for a in th:
		if a:
			a.join(0.1)
	for row in mainth:
		for a in row:
			if a:
				if not nogui:
					deletertu(a)
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
		
def closesocket(s):
	try:
		s.close()
	except (error, OSError, ValueError, AttributeError):
		pass
	return 0

def openconnClient(self):
	global exitprogram
	i=0
	for address in self.srvip:
		if exitprogram:
			break
		# open connection for mm2ss client to real server
		self.conn = socket( AF_INET, SOCK_STREAM )
		try:
			# set timeout = 3 sec.
			self.conn.settimeout(3.0)
			self.conn.connect((address, int(self.srvport[i])))
			self.timeidle=time()
			self.t3timeidle=time()
		except (timeout, gaierror, ConnectionRefusedError,OSError):
			self.conn.close()
			self.conn=0
		if self.conn:
			self.PORT=int(self.srvport[i])
			self.logfhw.write(str(datetime.now()) + f' : Client connected to {address}:{self.PORT}.' + '\n')
			# send startdt
			sendpacket=b'\x68\x04\x07\x00\x00\x00'
			self.conn.sendall(sendpacket)
			self.logfhw.write(str(datetime.now()) + f' : startdt transmitted.' + '\n')
			self.waitserver=0	# should be reset when mm2ss client connect to the real server
			break
		i += 1
	return self.conn

def openconn(self):
	# open connection
	if self.s:
		try:
			self.conn, addr = self.s.accept()
			self.timeidle=time()
			self.t3timeidle=time()
		except (error, OSError, ValueError):
			self.conn = 0
		if self.conn:
			self.conn.setblocking(False)
			self.s=closesocket(self.s)
			acceptedaddr=0
			for i in self.acceptnetsys:
				try:
					if ip_address(addr[0]) in ip_network(i):
						acceptedaddr=1
						break
				except (ValueError):
					pass
			if acceptedaddr or not ''.join(self.acceptnetsys):
				self.logfhw.write(str(datetime.now()) + ' : Connected to IP: ' + str(addr[0]) + ', Port: ' + str(addr[1]) + '\n')
				self.logfilechanged=1
			else:
				self.conn=closeconn(self,0)
				self.s=opensocket(self.PORT)
	return self.conn
	
def closeconnClient(self,setdisconnet=1):
	if self.conn:
		self.conn.close()
		incseqno(self,'I')
		if setdisconnet:
			self.disconnected=1
		closemm2ssservers(self)
	return 0

def closeconn(self,setdisconnet=1):
	if self.conn:
		try:
			self.conn.shutdown(SHUT_RDWR)    # 0 = done receiving, 1 = done sending, 2 = both
			self.conn.close()
		except (error, OSError, ValueError):
			pass
		incseqno(self,'I')
		if setdisconnet:
			self.disconnected=1
	return 0

def closemm2ssservers(self):
	self.waitserver=1
	sleep(1)
	for a in mainth[self.index]:
		if a != self:
			# close connection and socket
			if a.conn:
				a.conn = closeconn(a)
			elif a.s:
				a.s = closesocket(a.s)
	
# read data
def readdata(self):
	global bufsize
	if self.conn:
		if (self.wrpointer+1) != self.rdpointer:
			try:
				data = self.conn.recv(2)
				if data:
					dt = datetime.now()
					packetlen=b'\x00'
					if data[0] == 104:
						packetlen=data[1]
					elif data[1] == 104:
						packetlen=self.conn.recv(1)
					if packetlen != b'\x00':
						data = hexlify(self.conn.recv(packetlen))
						self.databuffer[self.wrpointer + 1] = [('68' + "{:02x}".format(int(packetlen)) + data.decode()), str(dt)]
						self.sentnorec=0
						self.timeidle=time()
						self.t3timeidle=time()
						if self.wrpointer == (bufsize - 1):
							self.wrpointer=-1
						else:
							self.wrpointer += 1
					return packetlen
			except (BlockingIOError, error, OSError, ValueError):
				pass

def senddata(self,data,addtime=0):
	while not len(self.ready_to_write):
		pass
	while self.insenddata:
		pass
	self.insenddata=1
	# wait if exceeded k packets send without receive.
	while self.sentnorec > self.kpackets:
		pass
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
	try:
		# add seq numbers to data packet if it is I format
		if (int.from_bytes(data[2:3], byteorder='little') & 1) == 0:
			data1 = data[0:2] + (self.txlsb*2).to_bytes(1,'little') + self.txmsb.to_bytes(1,'little') + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') + data[6:]
			self.conn.sendall(data1)
			incseqno(self,'TX')
			self.sentnorec += 1
			self.recnosend=0
			#self.t2timeidle=time()
			self.t3timeidle=time()
		else:
			self.conn.sendall(data)
	except (error, OSError, ValueError, AttributeError):
		pass
	self.insenddata=0
	return str(dt)

def incseqno(self,txrx):
	if txrx == 'I':
		self.txlsb=0
		self.txmsb=0
		self.rxlsb=0
		self.rxmsb=0
	if txrx == 'TX':
		self.txlsb += 1
		if self.txlsb == 128:
			self.txlsb=0
			self.txmsb += 1
			if self.txmsb == 256:
				self.txmsb=0
	if txrx == 'RX':
		self.rxlsb += 1
		if self.rxlsb == 128:
			self.rxlsb=0
			self.rxmsb += 1
			if self.rxmsb == 256:
				self.rxmsb=0

def initiate(self):
	self.dataactive=0
	self.statusvalue="NO"
	self.statuscolor='red'
	self.connectedatvalue=' '
	self.updatestatusgui=1
	self.sentnorec=0
	self.recnosend=0
	self.rcvtfperiodmin=1000000
	self.time1=0
	# set initialize flag
	self.initialize=1
	self.logfilechanged=1

# read packet from real server to mm2ss client.
def readpacketClient(self):
	global bufsize,w,t2
	# send S-Format packet if required
	if (self.recnosend > w) or (self.recnosend and ((time() - self.t2timeidle) > t2)):
		self.recnosend=0
		self.t2timeidle=time()
		sendpacket=b'\x68\x04\x01\x00' + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') 
		senddata(self,sendpacket)
	packet=''
	# read the packet from buffer
	if self.rdpointer != self.wrpointer:
		packet, dt=self.databuffer[self.rdpointer+1]
		#packet=packet1[2:]
		seqnotxlsb=int(packet[4:4+2],16)
		if self.rdpointer == (bufsize - 1):
			self.rdpointer=-1
		else:
			self.rdpointer += 1
		# decode U format packets
		if packet[4:4+2] == '0b':			# startdt con packet
			self.logfhw.write(dt + ' : startdt con received.' + '\n')
			self.dataactive=1
			self.statusvalue="YES"
			self.statuscolor='green'
			self.connectedatvalue=dt
			self.updatestatusgui=1
		elif packet[4:4+2] == '07':			# startdt act packet should not come from slave
			# send startdt con
			sendpacket=b'\x68\x04\x0B\x00\x00\x00'
			senddata(self,sendpacket)
			self.logfhw.write(dt + ' : startdt act received and con transmitted.' + '\n')
		elif  packet[4:4+2] == '43':		 	# testfr act packet
			rcvtf=time()
			rcvtfperiod=round(rcvtf - self.time1,1)
			# send testfr con packet
			sendpacket=b'\x68\x04\x83\x00\x00\x00'
			senddata(self,sendpacket)
			if rcvtfperiod < self.rcvtfperiodmin and self.time1 != 0:
				self.rcvtfperiodmin=rcvtfperiod
				self.logfhw.write(dt + ' : Received testfr act minimum period: ' + "{:04.1f}".format(float(rcvtfperiod)) + ' seconds.' + '\n')
			self.time1=rcvtf
		elif  packet[4:4+2] == '13':		 	# stopdt act packet
			# send stopdt con
			sendpacket=b'\x68\x04\x23\x00\x00\x00'
			senddata(self,sendpacket)
			self.logfhw.write(dt + ' : stopdt act/con done.' + '\n')
			# initialize
			initiate(self)
		elif (int(packet[4:4+2],16) & 0x03) == 1:	# neglect S-format packet.
			pass
		# check if it is I format (bit 0=0 of 3rd byte or 4 and 5 digits of databuffer) then increase RX
		if (seqnotxlsb & 1) == 0:
			incseqno(self,'RX')
			if not self.recnosend:
				self.t2timeidle=time()
			self.recnosend += 1
			# neglect end of initialization packet
			if packet[12:12+2] == '46':
				pass
			# forward the packet to mm2ss server
			# if spi, dpi or ami then forward to all mm2ss servers.
			if int(packet[12:12+2],16) <= 40:
				for a in mainth[self.index]:
					if (a != self) and ((a.packet2server_wrp+1) != a.packet2server_rdp) and a.dataactive:
						a.packet2server[a.packet2server_wrp+1] = bytearray.fromhex(packet)
						if a.packet2server_wrp == (bufsize - 1):
							a.packet2server_wrp=-1
						else:
							a.packet2server_wrp += 1
			else:
				index1=int(packet[18:18+2],16)
				if index1 in range(1,len(mainth[self.index])+1):
					if (mainth[self.index][index1].packet2server_wrp+1) != mainth[self.index][index1].packet2server_rdp and mainth[self.index][index1].dataactive:
						mainth[self.index][index1].packet2server[mainth[self.index][index1].packet2server_wrp+1] = bytearray.fromhex(packet)
						if mainth[self.index][index1].packet2server_wrp == (bufsize - 1):
							mainth[self.index][index1].packet2server_wrp=-1
						else:
							mainth[self.index][index1].packet2server_wrp += 1
		self.logfilechanged=1

# read packet from real client to mm2ss server.
def readpacket(self):
	global bufsize,w,t2
	# send S-Format packet if required
	if (self.recnosend > w) or (self.recnosend and (time() - self.t2timeidle) > t2):
		self.recnosend=0
		self.t2timeidle=time()
		sendpacket=b'\x68\x04\x01\x00' + (self.rxlsb*2).to_bytes(1,'little') + self.rxmsb.to_bytes(1,'little') 
		senddata(self,sendpacket)
	packet=''
	# read the packet from buffer
	if self.rdpointer != self.wrpointer:
		packet, dt=self.databuffer[self.rdpointer+1]
		#packet=packet1[2:]
		seqnotxlsb=int(packet[4:4+2],16)
		if self.rdpointer == (bufsize - 1):
			self.rdpointer=-1
		else:
			self.rdpointer += 1
		# decode U format packets
		if packet[4:4+2] == '07':			# startdt act packet
			# if mm2ss client connected to real server? then we will reply for everything
			#if mainth[0].dataactive:
				# send startdt con
				sendpacket=b'\x68\x04\x0B\x00\x00\x00'
				senddata(self,sendpacket)
				self.logfhw.write(dt + ' : startdt act/con done.' + '\n')
				if not self.dataactive:
					# send end of initialization
					sendpacket=b'\x68\x0E\x00\x00\x00\x00\x46\x01\x04\x00' + int(self.rtuno).to_bytes(2,'little') + b'\x00\x00\x00\x00'
					senddata(self,sendpacket)
					self.logfhw.write(dt + ' : End of initialization transmitted.' + '\n')
					self.dataactive=1
					self.statusvalue="YES"
					self.statuscolor='green'
					self.connectedatvalue=dt
					self.updatestatusgui=1
		elif  packet[4:4+2] == '43':		 	# testfr act packet
			rcvtf=time()
			rcvtfperiod=round(rcvtf - self.time1,1)
			# send testfr con packet
			sendpacket=b'\x68\x04\x83\x00\x00\x00'
			senddata(self,sendpacket)
			if rcvtfperiod < self.rcvtfperiodmin and self.time1 != 0:
				self.rcvtfperiodmin=rcvtfperiod
				self.logfhw.write(dt + ' : Received testfr act minimum period: ' + "{:04.1f}".format(float(rcvtfperiod)) + ' seconds.' + '\n')
			self.time1=rcvtf
		elif  packet[4:4+2] == '13':		 	# stopdt act packet
			# send stopdt con
			sendpacket=b'\x68\x04\x23\x00\x00\x00'
			senddata(self,sendpacket)
			self.logfhw.write(dt + ' : stopdt act/con done.' + '\n')
			# initialize
			initiate(self)
		elif (int(packet[4:4+2],16) & 0x03) == 1:	# neglect S-format packet.
			pass
		# check if it is I format (bit 0=0 of 3rd byte or 4 and 5 digits of databuffer) then increase RX
		if (seqnotxlsb & 1) == 0:
			incseqno(self,'RX')
			if not self.recnosend:
				self.t2timeidle=time()
			self.recnosend += 1
			# forward the packet to mm2ss client
			if (self.packet2client_wrp+1) != self.packet2client_rdp:
				self.packet2client[self.packet2client_wrp+1] = bytearray.fromhex(packet)
				# set org address to self.order
				self.packet2client[self.packet2client_wrp+1][9:9+1]=self.order.to_bytes(1,'little')
				if self.packet2client_wrp == (bufsize - 1):
					self.packet2client_wrp = -1
				else:
					self.packet2client_wrp += 1
		self.logfilechanged=1

def readmm2ssclientthread(self):
	global exitprogram,bufsize
	while True:
		if exitprogram:
			break
		# read from mm2ss client and send to real client
		if self.packet2server_rdp != self.packet2server_wrp and self.dataactive:
			packet=self.packet2server[self.packet2server_rdp+1]
			if self.packet2server_rdp == (bufsize - 1):
				self.packet2server_rdp = -1
			else:
				self.packet2server_rdp += 1
			# if org is ours then set it to 0 and send the packet to real client
			if int.from_bytes(packet[9:9+1],'little') == self.order:
				packet[9:9+1]=b'\x00'	# set it back to 0
				# set rtu no.
				packet[10:10+2]=int(self.rtuno).to_bytes(2,'little')
				senddata(self,packet)			
			# else if type id is spi,dpi or AMI then change packet org address and send it to real client
			elif int.from_bytes(packet[6:6+1],'little') <= 40:
				packet[9:9+1]=b'\x00'	# set it back to 0
				# set rtu no.
				packet[10:10+2]=int(self.rtuno).to_bytes(2,'little')
				senddata(self,packet)

def readmm2ssserverthread(self):
	global exitprogram,mainth,bufsize
	while True:
		if exitprogram:
			break
		# read from mm2ss servers and send to real server
		for a in mainth[self.index]:
			if (a != self) and (a.packet2client_rdp != a.packet2client_wrp):
				packet=a.packet2client[a.packet2client_rdp+1]
				if a.packet2client_rdp == (bufsize - 1):
					a.packet2client_rdp = -1
				else:
					a.packet2client_rdp += 1
				packet[10:10+2]=int(self.rtuno).to_bytes(2,'little')
				senddata(self,packet)			

def readpacketthreadClient (self):
	global exitprogram
	initiate(self)
	while True:
		if exitprogram:
			break
		if self.initialize:
			self.logfhw.write(str(datetime.now()) + ' : Initialized ..\n')
			self.initialize=0
		if self.disconnected:
			self.logfhw.write(str(datetime.now()) + ' : Disconnected .. trying connection ..\n')
			initiate(self)
			self.initialize=0
			self.disconnected=0
		readpacketClient(self)

def readpacketthread (self):
	global exitprogram
	initiate(self)
	while True:
		if exitprogram:
			break
		if self.initialize:
			self.logfhw.write(str(datetime.now()) + ' : Initialized ..\n')
			self.initialize=0
		if self.disconnected:
			self.logfhw.write(str(datetime.now()) + ' : Disconnected .. waiting for connection ..\n')
			initiate(self)
			self.initialize=0
			self.disconnected=0
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
    except (timeout, gaierror):
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
						exitcode = system(f'date +%T -s {localTimetoset}')
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

# define iec104 thread for mm2ss client
class iec104threadClient (threading.Thread):
	global bufsize,dir,idletime,k,nogui
	def __init__(self, threadID, name,rtuno,srvipport,srvport,srvip,csvindex, logfilename):
		threading.Thread.__init__(self)
		self.threadID = threadID
		self.order=0
		self.name = name
		self.PORT = int(srvport[0])
		self.logfilename = dir + logfilename + '.txt'
		#self.logfilenamegi = dir + logfilename + '-gi.txt'
		self.logfhw=0
		self.logfhr=0
		self.logfilechanged=0
		self.rtunohex = "{:04x}".format(int(rtuno))
		self.rtunohex = self.rtunohex[2:2+2] + self.rtunohex[0:2]
		self.rtuno = rtuno
		self.dataactive=0
		self.initialize=0
		self.rcvtfperiodmin=1000000
		self.insenddata=0
		self.sentnorec=0
		self.recnosend=0
		self.srvip=srvip.copy()
		self.srvport=srvport.copy()
		self.kpackets=k
		# timeidle > t3 (time of testfr packet). if not receiving data during timeidle then disconnect.
		self.tdisconnect=idletime
		self.waitrestart=0
		self.waitserver=1		# all mm2ss servers start waiting mm2ss client connection to real server (RTU or SCS)
		self.index=0
		self.csvindex=csvindex

		# py will write this variable when connection disconnected.
		self.disconnected=0
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
		# fifo buffer variables used between this mm2ss client and real server
		self.rdpointer=-1
		self.wrpointer=-1
		self.databuffer=[0 for i in range(bufsize+1)]

		self.ready_to_write=[]

		if not nogui:
			# GUI variables
			self.filternet=srvipport
			self.lbl_seqno=tk.Label(frame, text=f'{self.csvindex}', relief=tk.RIDGE, width=5,bg="white", fg="blue")
			self.lbl_seqno.grid(row=self.threadID, column=0)
			self.lbl_sys=tk.Label(frame, text=self.name, relief=tk.RIDGE, width=16,bg="white", fg="red")
			self.lbl_sys.grid(row=self.threadID, column=1)
			self.lbl_status=tk.Label(frame, text='NO', relief=tk.RIDGE, width=6, bg="white", fg="red")
			self.lbl_status.grid(row=self.threadID, column=2)
			self.statusvalue='NO'
			self.statuscolor='red'
			self.updatestatusgui=0
			self.lbl_portno=tk.Label(frame, text=self.PORT, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_portno.grid(row=self.threadID, column=3)
			self.lbl_rtuno=tk.Label(frame, text=self.rtuno, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_rtuno.grid(row=self.threadID, column=4)
			self.lbl_connectedat=tk.Label(frame, text=' ',bg="white", relief=tk.RIDGE, width=26, fg="green")
			self.lbl_connectedat.grid(row=self.threadID, column=5)
			self.connectedatvalue=' '
			self.cbx_action=ttk.Combobox(frame, width=21,
										values=[
												"Open log file", 
												"Show log in Tab2-Text1",
												"Show log in Tab2-Text2"])
			self.cbx_action.grid(row=self.threadID, column=6)
			CreateToolTip(self.cbx_action,"Select action to be applied/executed for Client.")
			self.btn_apply=tk.Button(master=frame, text="Apply", command=lambda: applyaction(self))
			self.btn_apply.grid(row=self.threadID, column=7)
			CreateToolTip(self.btn_apply,"Apply action selected in combo box to Client.")

	def run(self):
		global exitprogram,programstarted,t3
		ready_to_read=[]
		# wait until starting all threads.
		while not programstarted:
			pass
		while True:
			while self.waitrestart:
				pass
			if exitprogram:
				# close conn
				if self.conn:
					self.conn=closeconnClient(self)
				break
			# if no data for t3 seconds then send testfr packet.
			if ((time() - self.t3timeidle) > t3) and self.conn:
				# send testfr act packet
				sendpacket=b'\x68\x04\x43\x00\x00\x00'
				senddata(self,sendpacket)
				self.t3timeidle=time()
			# timeidle > tdisconnect. if not receiving data during timeidle then disconnect.
			if ((time() - self.timeidle) > self.tdisconnect) and self.conn:
				self.logfhw.write(str(datetime.now()) + ' : No received data for ' + str(self.tdisconnect) + ' seconds .. disconnecting ..\n')
				self.logfilechanged=1
				closeconnClient(self)
				self.conn=openconnClient(self)
			if not self.conn:
				self.conn=openconnClient(self)
			try:
				ready_to_read, self.ready_to_write, in_error = \
					select([self.conn,], [self.conn,], [], 1)
			except (OSError, WindowsError, ValueError):
				closeconnClient(self)
				self.conn=openconnClient(self)
				# connection error event here, maybe reconnect
			if len(ready_to_read) > 0:
				recv=readdata(self)
				if not recv:
					closeconnClient(self)
					self.conn=openconnClient(self)
		
# define iec104 thread for mm2ss server
class iec104thread (threading.Thread):
	global bufsize,dir,idletime,k,nogui
	def __init__(self, threadID, name, PORT,rtuno,csvindex,logfilename):
		threading.Thread.__init__(self)
		self.threadID = threadID
		self.order=0
		self.name = name
		self.PORT = int(PORT)
		self.logfilename = dir + logfilename + '.txt'
		#self.logfilenamegi = dir + logfilename + '-gi.txt'
		self.logfhw=0
		self.logfhr=0
		self.logfilechanged=0
		self.rtunohex = "{:04x}".format(int(rtuno))
		self.rtunohex = self.rtunohex[2:2+2] + self.rtunohex[0:2]
		self.rtuno = rtuno
		self.dataactive=0
		self.initialize=0
		self.rcvtfperiodmin=1000000
		self.insenddata=0
		self.sentnorec=0
		self.recnosend=0
		self.acceptnetsys=[]
		self.kpackets=k
		# timeidle > t3 (time of testfr packet). if not receiving data during timeidle then disconnect.
		self.tdisconnect=idletime
		self.waitrestart=0
		self.index=0
		self.csvindex=csvindex

		# py will write this variable when connection disconnected.
		self.disconnected=0
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
		# fifo buffer variables used between this mm2ss server and real client
		self.rdpointer=-1
		self.wrpointer=-1
		self.databuffer=[0 for i in range(bufsize+1)]
		# fifo buffer variables used between this mm2ss server thread and mm2ss client thread
		self.packet2client=[0 for i in range(bufsize+1)]	# fifo buffer where mm2ss server put packet to mm2ss client.
		self.packet2client_rdp=-1							# fifo buffer read pointer used by mm2ss client.
		self.packet2client_wrp=-1							# fifo buffer write pointer used by mm2ss server.
		self.packet2server=[0 for i in range(bufsize+1)]	# fifo buffer where mm2ss client put packet to mm2ss server.
		self.packet2server_rdp=-1							# fifo buffer read pointer used by mm2ss server.
		self.packet2server_wrp=-1							# fifo buffer write pointer used by mm2ss client.

		self.ready_to_write=[]

		if not nogui:
			# GUI variables
			self.filternet=''
			self.lbl_seqno=tk.Label(frame, text=f'{self.csvindex}', relief=tk.RIDGE, width=5,bg="white", fg="blue")
			self.lbl_seqno.grid(row=self.threadID, column=0)
			self.lbl_sys=tk.Label(frame, text=self.name, relief=tk.RIDGE, width=16,bg="white", fg="red")
			self.lbl_sys.grid(row=self.threadID, column=1)
			self.lbl_status=tk.Label(frame, text='NO', relief=tk.RIDGE, width=6, bg="white", fg="red")
			self.lbl_status.grid(row=self.threadID, column=2)
			self.statusvalue='NO'
			self.statuscolor='red'
			self.updatestatusgui=0
			self.lbl_portno=tk.Label(frame, text=self.PORT, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_portno.grid(row=self.threadID, column=3)
			self.lbl_rtuno=tk.Label(frame, text=self.rtuno, relief=tk.RIDGE, width=5, bg="white", fg="blue")
			self.lbl_rtuno.grid(row=self.threadID, column=4)
			self.lbl_connectedat=tk.Label(frame, text=' ',bg="white", relief=tk.RIDGE, width=26, fg="green")
			self.lbl_connectedat.grid(row=self.threadID, column=5)
			self.connectedatvalue=' '
			self.cbx_action=ttk.Combobox(frame, width=21,
										values=[
												"Open log file", 
												"Show log in Tab2-Text1",
												"Show log in Tab2-Text2"])
			self.cbx_action.grid(row=self.threadID, column=6)
			CreateToolTip(self.cbx_action,"Select acction to be applied/executed for this Server.")
			self.btn_apply=tk.Button(master=frame, text="Apply", command=lambda: applyaction(self))
			self.btn_apply.grid(row=self.threadID, column=7)
			CreateToolTip(self.btn_apply,"Apply acction selected in combo box to this Server.")

	def run(self):
		global exitprogram,programstarted,t3
		ready_to_read=[]
		# wait until starting all threads.
		while not programstarted:
			pass
		while True:
			while self.waitrestart or mainth[self.index][0].waitserver:
				pass
			if exitprogram:
				# close conn
				if self.conn:
					self.conn=closeconn(self)
				elif self.s:
					self.s=closesocket(self.s)
				break
			# if no data for t3 seconds then send testfr packet.
			if ((time() - self.t3timeidle) > t3) and self.conn:
				# send testfr act packet
				sendpacket=b'\x68\x04\x43\x00\x00\x00'
				senddata(self,sendpacket)
				self.t3timeidle=time()
			# timeidle > tdisconnect. if not receiving data during timeidle then disconnect.
			if ((time() - self.timeidle) > self.tdisconnect) and self.conn:
				self.logfhw.write(str(datetime.now()) + ' : No received data for ' + str(self.tdisconnect) + ' seconds .. disconnecting ..\n')
				self.logfilechanged=1
				closeconn(self)
				self.s=opensocket(self.PORT)
				self.conn=openconn(self)
			if not self.s and not self.conn:
				self.s=opensocket(self.PORT)
			if not self.conn and self.s:
				self.conn=openconn(self)
			try:
				ready_to_read, self.ready_to_write, in_error = \
					select([self.conn,], [self.conn,], [], 1)
			except (OSError, WindowsError, ValueError):
				closeconn(self)
				self.s=opensocket(self.PORT)
				self.conn=openconn(self)
				# connection error event here, maybe reconnect
			if len(ready_to_read) > 0:
				recv=readdata(self)
				if not recv:
					closeconn(self)
					self.s=opensocket(self.PORT)
					self.conn=openconn(self)
					
def restartaction(self,ind):
	global txtbx1thid,txtbx2thid,updatetoframe1,updatetoframe2,portnolist
	if ind == 1:
		# take sysname, rtuno, portno and filter from frame1
		sysname = ent_sys1.get()
		rtuno = ent_rtuno1.get()
		portno = ent_portno1.get()
		filternet = ent_filter1.get()
	else:
		# take sysname, rtuno, portno and filter from frame2
		sysname = ent_sys2.get()
		portno = ent_portno2.get()
		rtuno = ent_rtuno2.get()
		filternet = ent_filter2.get()
	tmplist=portnolist.copy()
	tmplist[self.threadID]='0'
	if not portno or not rtuno or not sysname:
		messagebox.showerror("Error", 'Port, RTU numbers and System name are required.')
	elif not int(rtuno) or not int(portno):
		messagebox.showerror("Error", f'Wrong port {portno} or rtu {rtuno}, must not equal zero.')
	elif (self.order != 0) and (portno in tmplist):
		messagebox.showerror("Error", f'Wrong port {portno}, already used for other slaves/RTUs.')
	# confirm from user
	elif messagebox.askokcancel("Restart sys", f'Do you want to restart "{self.csvindex}" with:\nName: {sysname}\nPort: {portno}\nRTU: {rtuno}\nIP/filter: {filternet}'):
		# close connection and socket
		if self.order == 0:		# slave RTU entry
			tmpipportlist1=filternet.split(';')
			srvip=[]
			srvport=[]
			for a in tmpipportlist1:
				tmpipportlist=a.split(':')
				if tmpipportlist[0] and tmpipportlist[1].isdigit() and int(tmpipportlist[1]) in range(1,65535):	# port no. is ok?
					srvip.append(tmpipportlist[0])
					srvport.append(tmpipportlist[1])
			if not srvport or not ''.join(srvport) or not srvip or not ''.join(srvip):
				messagebox.showerror("Error", f'Wrong port number, must be in range (1,65535).')
			else:
				self.waitrestart=1
				sleep(1)
				if self.conn:
					self.conn = closeconnClient(self)
				if sysname[0:0+2] == 'S/':
					self.name=sysname
				else:
					self.name='S/' + sysname
				self.PORT=int(portno)
				self.rtuno=int(rtuno)
				self.srvip.clear()
				self.srvip=srvip.copy()
				self.srvport.clear()
				self.srvport=srvport.copy()
				self.filternet=filternet
		else:					# master SCADA system entry
			self.waitrestart=1
			sleep(1)
			if self.conn:
				self.conn = closeconn(self)
			elif self.s:
				self.s = closesocket(self.s)
			if sysname[0:0+2] == 'M/':
				self.name=sysname
			else:
				self.name='M/' + sysname
			self.PORT=int(portno)
			self.rtuno=int(rtuno)
			portnolist[self.threadID]=portno
			self.acceptnetsys.clear()
			self.acceptnetsys=filternet.split(';')
			self.filternet=filternet
		# open connection with new settings
		self.waitrestart=0
		#self.s=opensocket(self.PORT)
		#self.conn=openconn(self)
		self.logfhw.write(str(datetime.now()) + ' : Restarted as per user request.\n')
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
		system(f'start notepad {self.logfilename}')
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
		ent_filter1.delete(0, 'end')
		ent_filter1.insert(tk.END, self.filternet)
		#print('filter: ',self.filternet)
		if self.order == 0:		# disable port label for mm2ss slave.
			ent_portno1.configure(state='disabled')
		else:
			ent_portno1.configure(state='normal')
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
		ent_filter2.delete(0, 'end')
		ent_filter2.insert(tk.END, self.filternet)
		if self.order == 0:		# disable port label for mm2ss slave.
			ent_portno2.configure(state='disabled')
		else:
			ent_portno2.configure(state='normal')
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
	elif 'filter' in name:
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

#def sendindex():

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
        "Display text in tooltip window"
        self.text = text
        if self.tipwindow or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except (TypeError):
            pass
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

# create log folder
try:
	mkdir(dir)
except FileExistsError:
	pass

# get program arguments
# -h or --help							help message
# -i or --ini							init file
# -t or --ntp_update_every_sec			NTP update interval
# -s or --ntp_server					NTP server
argvl = argv[1:]
try:
	options, args = getopt(argvl, "i:t:s:hn",
						["ini=",
						"ntp_update_every_sec=",
						"ntp_server=",
						"help",
						"nogui"])
except:
	print(helpmess)
	exit()

# parse program aguments
for argname, argvalue in options:
	if argname in ['-h', '--help']:
		print(helpmess)
		exit()
	elif argname in ['-n', '--nogui']:
		nogui = 1
	elif argname in ['-i', '--ini']:
		initfile = argvalue
	elif argname in ['-t','--ntp_update_every_sec']:
		if argvalue.isdigit():
			timeupdateevery=int(argvalue)
	elif argname in ['-s', '--ntp_server']:
		ntpserver.append(argvalue)

# read init file
#ntpserver,10.1.1.15,,
#ntp_server,time.windows.com,,
#ntp_server,pool.ntp.org,,
#ntp_update_every_sec,900,,
#rtuno,32,,
#idletime,60,,
#w,8,,
#k,12,,
# id,sys name,portno,rtuno,hosts
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
			# general settings
			elif row[0] == 'ntp_update_every_sec' and row[1].isdigit():
				timeupdateevery=int(row[1])
			elif row[0] == 'nogui':
				nogui = 1
			elif row[0] == 'ntp_server' and row[1]:
				ntpserver.append(row[1])
			elif row[0] == 'idletime' and row[1].isdigit():
				idletime=int(row[1])
			elif row[0] == 't2' and row[1].isdigit():
				t2=int(row[1])
			elif row[0] == 't3' and row[1].isdigit():
				t3=int(row[1])
			elif row[0] == 'w' and row[1].isdigit():
				w=int(row[1])
			elif row[0] == 'k' and row[1].isdigit():
				k=int(row[1])

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
	listcol=[]
	listrow=[]
	listcol.extend(range(128))
	listrow.extend(range(72))
	window.rowconfigure(listrow, minsize=10, weight=1)
	window.columnconfigure(listcol, minsize=10, weight=1)

	tab_parent = ttk.Notebook(window)

	tab_canvas = ttk.Frame(tab_parent)
	tab_textbox = ttk.Frame(tab_parent)

	tab_parent.add(tab_canvas, text="Tab1: Full Systems list")
	tab_parent.add(tab_textbox, text="Tab2: Log files and data edit")

	#tab_parent.pack(expand=1, fill='both')
	tab_parent.grid(row=3, column=1,columnspan=127,rowspan=64,sticky="nsew")

	tab_canvas.rowconfigure(listrow, minsize=10, weight=1)
	tab_canvas.columnconfigure(listcol, minsize=10, weight=1)

	tab_textbox.rowconfigure(listrow, minsize=10, weight=1)
	tab_textbox.columnconfigure(listcol, minsize=10, weight=1)

	myFont = Font(family="Courier New", size=10)

	dt=str(datetime.now())
	lbl_startedat = tk.Label(master=window,relief=tk.GROOVE, borderwidth=3, fg='blue', text=f'Started at: {dt}')
	lbl_startedat.grid(row=1, column=1,columnspan=30,rowspan=2,sticky="nw")

	reg = window.register(digitvalidation)

	lbl_adminpriv = tk.Label(master=window,relief=tk.GROOVE, text=' ')
	lbl_adminpriv.grid(row=1, column=55,columnspan=60,rowspan=2,sticky="nw")

	#      System        Online    Port  RTU       Connected at           Select action            Apply
	# 1234567890123456    Yes     12345 12345  2021-04-22 06:27:47.462463  Open GI log file           Apply
	#																				      	   Open log file
	#																					 	   Show log in textbox 1
	#																					       Show log in textbox 2
	lbl_header = tk.Label(master=tab_canvas, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System      Online  Port RTU       Connected at             Select action        Apply ')
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
	lbl_header1 = tk.Label(master=tab_textbox, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System     Online  Port RTU        Connected at               Filter net/IP       Restart ')
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
	#str_filter1 = tk.StringVar()
	ent_filter1 = tk.Entry(frame1, name='filter', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_filter1.grid(row=row, column=7, sticky="nsew")
	CreateToolTip(ent_filter1,"Enter new hosts or networks filters separated by ;\nnexample: 192.168.1.1:2404;10.1.1.100:2405 or\n192.168.1.0/24;10.10.1.2")
	btn_restart1 = tk.Button(master=frame1, text="Restart")
	btn_restart1.grid(row=row, column=8,rowspan=2,sticky="nw")
	CreateToolTip(btn_restart1,"Restart\nwith new\nsettings.")

	text_box1 = tk.Text(tab_textbox)
	text_box1.grid(row=5, column=0,columnspan=120,rowspan=21, sticky="nsew")
	sb1 = ttk.Scrollbar(tab_textbox, orient="vertical", command=text_box1.yview)
	sb1.grid(column=120, row=5,rowspan=21, columnspan=2, sticky="nse")
	text_box1['yscrollcommand'] = sb1.set
	text_box1.config(state=tk.DISABLED)
	CreateToolTip(text_box1,"Tab2-text1: Log file of the selected System/RTU is displayed here..")

	# second frame and textbox2
	frame2 = tk.Frame(tab_textbox)
	frame2.option_add("*Font", myFont)
	frame2.grid(row=29, column=0,columnspan=130,rowspan=2,sticky="nsew")
	lbl_header2 = tk.Label(master=tab_textbox, font=myFont, relief=tk.GROOVE, borderwidth=3, fg='blue', text='Group      System     Online  Port RTU        Connected at               Filter net/IP       Restart ')
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
	ent_filter2 = tk.Entry(frame2, name='filter', validate ="key", validatecommand =(reg, '%P', '%S', '%W'), relief=tk.GROOVE, width=26, bg="light yellow", fg="blue")
	ent_filter2.grid(row=row, column=7, sticky="nsew")
	CreateToolTip(ent_filter2,"Enter new hosts or networks filters separated by ;\nexample: 192.168.1.1:2404;10.1.1.100:2405 or\n192.168.1.0/24;10.10.1.2")
	btn_restart2 = tk.Button(master=frame2, text="Restart")
	btn_restart2.grid(row=row, column=8,rowspan=2, sticky="nw")
	CreateToolTip(btn_restart2,"Restart\nwith new\nsettings.")

	text_box2 = tk.Text(tab_textbox)
	text_box2.grid(row=31, column=0,columnspan=120,rowspan=21, sticky="nsew")
	sb2 = ttk.Scrollbar(tab_textbox, orient="vertical", command=text_box2.yview)
	sb2.grid(column=120, row=31,rowspan=21, columnspan=2, sticky="nse")
	text_box2['yscrollcommand'] = sb2.set
	text_box2.config(state=tk.DISABLED)
	CreateToolTip(text_box2,"Tab2-text2: Log file of the selected System/RTU is displayed here..")

	window.protocol("WM_DELETE_WINDOW", on_closing)

# read init file
#ntpserver,10.1.1.15,,
#ntp_server,time.windows.com,,
#ntp_server,pool.ntp.org,,
#ntp_update_every_sec,900,,
#rtuno,32,,
#idletime,60,,
#w,8,,
#k,12,,
# id,sys name,portno,rtuno,hosts
if isfile(initfile):
	with open(initfile) as csv_file:
		#variable=value
		csv_reader = reader(csv_file, delimiter=',')
		noofsys=0
		indexgroup= -1
		for row in csv_reader:
			if not row:
				pass
			# if first character of first column in any row = '!' then break
			elif row[0][0:1] == '!' or exitprogram:
				break
			# Master entries - each row should start with integer, then sys name, portno (not required), rtuno, master(Y/N) and IP:PORT;IP:PORT.
			elif row[0].isdigit() and row[3].isdigit() and row[4] != "Y" and int(row[3]) in range(1,65535) and row[5]:
				tmplist=row[5].split(';')
				srvip=[]
				srvport=[]
				for a in tmplist:
					tmpipportlist=a.split(':')
					if tmpipportlist[0] and tmpipportlist[1].isdigit() and int(tmpipportlist[1]) in range(1,65535):	# port no. is ok?
						srvip.append(tmpipportlist[0])
						srvport.append(tmpipportlist[1])
				if not srvport or not ''.join(srvport) or not srvip or not ''.join(srvip):
					pass
				else:
					portnolist.append('0')
					srvipport = row[5]
					if row[0] not in csvindexlist:
						indexgroup += 1
						indexlist.append(indexgroup)
						csvindexlist.append(row[0])
						mainth.append([])
						# reserve first place for the virtual master
						mainth[indexgroup].append(0)
					# generate unique log file name for mm2ss client
					dt=datetime.now()
					currentdate=dt.strftime("%b%d%Y-%H-%M-%S-%f")
					logfilename=f'{row[1]}-{currentdate}-{row[2]}'
					# create thread class for mm2ss servers
					tmpth = iec104threadClient(noofsys, f'S/{row[1][0:0+14]}',int(row[3][0:0+5]),srvipport,srvport,srvip,row[0],logfilename)
					mainth[indexgroup][0]=tmpth
					tmpth.daemon = True
					tmpth.index=indexgroup
					tmpth.order=len(mainth[indexgroup]) - 1
					# identify log files
					tmpth.logfhw=open(dir + logfilename + '.txt',"w")
					tmpth.logfhw.write(f'{tmpth.name} log file .. RTU: {tmpth.rtuno}\n')
					tmpth.logfhr=open(dir + logfilename + '.txt',"r")
					tmpth.kpackets=k
					tmpth.tdisconnect=idletime
					# create GUI resources for mm2ss client - 8 gadgets
					# label:ID (5 char) label:System(16 char) label:Online (Yes/No) label:Port label:GI(Run) label:connected at(26 char) listbox:Action(30 char) button:Action
					# added to the class construction
					tmpth.start()
					# generate rest of the threads
					tmpth1 = threading.Thread(target=readpacketthreadClient,args=(tmpth,), daemon=True)
					th.append(tmpth1)
					tmpth1.start()
					tmpth1 = threading.Thread(target=readmm2ssserverthread,args=(tmpth,), daemon=True)
					th.append(tmpth1)
					tmpth1.start()
					noofsys += 1
			# slave (RTU) entries - each row should start with integer, then sys name, portno, rtuno, master(Y/N) and IP/Network filter.
			elif row[0].isdigit() and row[2].isdigit() and row[3].isdigit() and row[4] == "Y" and row[2] not in portnolist and int(row[2]) in range(1,65535) and int(row[3]) in range(1,65535):
				portnolist.append(row[2])
				if row[0] not in csvindexlist:
					indexgroup += 1
					indexlist.append(indexgroup)
					csvindexlist.append(row[0])
					mainth.append([])
					# reserve first place for the virtual master
					mainth[indexgroup].append(0)
				# generate unique log file names
				dt=datetime.now()
				currentdate=dt.strftime("%b%d%Y-%H-%M-%S-%f")
				logfilename=f'{row[1]}-{currentdate}-{row[2]}'
				tmpth = iec104thread(noofsys, f'M/{row[1][0:0+14]}',int(row[2][0:0+5]),int(row[3][0:0+5]),row[0],logfilename)
				mainth[indexgroup].append(tmpth)
				tmpth.daemon = True
				tmpth.index=indexgroup
				tmpth.order=len(mainth[indexgroup]) - 1
				# identify log files
				tmpth.logfhw=open(dir + logfilename + '.txt',"w")
				tmpth.logfhw.write(f'{tmpth.name} log file .. RTU: {tmpth.rtuno}, listen port: {row[2]}\n')
				tmpth.logfhr=open(dir + logfilename + '.txt',"r")
				# get accepted hosts
				if row[5]:
					tmpth.acceptnetsys=row[5].split(';')
					tmpth.filternet=row[5]
				tmpth.kpackets=k
				tmpth.tdisconnect=idletime
				# create GUI resources for this rtu - 8 gadgets
				# label:ID (5 char) label:System(16 char) label:Online (Yes/No) label:Port label:RTU label:connected at(26 char) listbox:Action(30 char) button:Action
				# added to the class construction
				tmpth.start()
				# generate rest of the threads
				tmpth1 = threading.Thread(target=readpacketthread,args=(tmpth,), daemon=True)
				th.append(tmpth1)
				tmpth1.start()
				tmpth1 = threading.Thread(target=readmm2ssclientthread,args=(tmpth,), daemon=True)
				th.append(tmpth1)
				tmpth1.start()
				noofsys += 1
			if not nogui:
				window.update()

# we should have at least 1 master and one client in each group
if not len(indexlist) or not noofsys:
	if not nogui:
		messagebox.showerror("Error", f'Found {noofsys} Systems .. Exiting.\nTry "-h" or "--help"')
	else:
		print(f'Error .. Found {noofsys} Systems .. Exiting.\nTry "-h" or "--help"')
	exit()

for ind in indexlist:
	if len(mainth[ind]) < 2 or not mainth[ind][0]:
		if not nogui:
			messagebox.showerror("Error", 'Each group should have at least one master and one slave .. Exiting.\nTry "-h" or "--help"')
		else:
			print('Error .. Each group should have at least one master and one slave .. Exiting.\nTry "-h" or "--help"')
		exit()

if not nogui:
	copytoframe1(mainth[indexlist[0]][0])
	copytoframe2(mainth[indexlist[0]][1])

# starting thread of ntp server update
if	ntpserver:
	if not nogui:
		lbl_adminpriv.configure(text='Trying NTP servers to update local time ..',fg='red')
	tmpth = threading.Thread(target=ntpthread, daemon=True)
	th.append(tmpth)
	tmpth.start()
	
# all thread started, ready.
programstarted=1

while True:
	try:
		if exitprogram:
			break

		if not nogui:
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

			for row in mainth:
				for a in row:
					if exitprogram:
						break
					# update gui
					# status of connection
					if a.updatestatusgui:
						a.updatestatusgui=0
						a.lbl_sys.configure(fg=a.statuscolor)
						a.lbl_status.configure(text=a.statusvalue,fg=a.statuscolor)
						a.lbl_connectedat.configure(text=a.connectedatvalue,fg='green')
						#if a.threadID == txtbx1thid:
						if a == txtbx1thid:
							ent_sys1.configure(fg=a.statuscolor)
							lbl_status1.configure(text=a.statusvalue,fg=a.statuscolor)
							lbl_connectedat1.configure(text=a.connectedatvalue,fg='green')
						#if a.threadID == txtbx2thid:
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
			if getsize(txtbx1thid.logfilename) != textsize:
				copytoframe1(txtbx1thid,fileonly=1)

			# print frame2 log file
			if updatetoframe2:
				updatetoframe2=0
				copytoframe2(txtbx2thid)
			elif txtbx2thid.logfilechanged:
				txtbx2thid.logfilechanged=0
				txtbx2thid.logfhw.flush()
			textsize=len(text_box2.get('1.0',tk.END)) + int(text_box2.index('end').split('.')[0]) - 3
			if getsize(txtbx2thid.logfilename) != textsize:
				copytoframe2(txtbx2thid,fileonly=1)
			
	except KeyboardInterrupt:
		break
exit()
