import os
import platform
import sys
import time
import EnttecUsbDmxPro
import colorama

def pulse():
	while True:
		for i in range(0,256):
			dmx.sendDMX([i,i,i,i,i,i,i,i,i,i,i,i,i,i,i,i])
			time.sleep(0.01)
		for i in range(255,-1):
			dmx.sendDMX([i,i,i,i,i,i,i,i,i,i,i,i,i,i,i,i])
			time.sleep(0.01)

def get():
	while True:
		print(dmx.getReceivedFrame())

def getNext():
	dmx.setDmxOnChange(enabled=True)
	while True:
		f = dmx.getNextFrame()["frame"]
		#dmxprint([f[i] for i in [331,383,393,437,110,435,330,328,387,395,385,391,397,98,445,438,434,446]])
		dmxprint(dmx.getNextFrame()["frame"])

def filterList(inlist, string, inverse=False):
	l = []
	for i in range(len(inlist)-1,-1,-1):
		if string in inlist[i] and not inverse:
			l.append(inlist[i])
	return l

def dmxprint(data):
	sys.stdout.write("{0}: ".format(len(data)))
	if len(data) == 0:
		sys.stdout.write("[]\n")
		return
	sys.stdout.write("[")
	for i in data:
		if i < 10:
			sys.stdout.write("  {0}".format(i))
		elif i < 100:
			sys.stdout.write(" {0}".format(i))
		else:
			sys.stdout.write("{0}".format(i))
		sys.stdout.write(", ")
	sys.stdout.write("\b\b")
	sys.stdout.write("]\n")

colorama.init(autoreset=True)
dport = -1

if len(sys.argv) < 2:
	if platform.system() == 'Linux':
		dport = '/dev/ttyUSB0'
	elif platform.system() == 'Darwin':
		#dport = '/dev/tty.usbserial-ENT095626'
		#dport = '/dev/tty.usbserial-EN175330'
		dport = "/dev/" + filterList(filterList(os.listdir("/dev/"), "tty."), "-EN")[0]
		print(dport)
else:
	dport = sys.argv[1]
dmx = EnttecUsbDmxPro.EnttecUsbDmxPro()
if dport == -1:
	dmx.list()
	sys.stderr.write("ERROR: No serial port for DMX detected!\n")
	sys.exit()
dmx.setPort(dport)
dmx.connect()