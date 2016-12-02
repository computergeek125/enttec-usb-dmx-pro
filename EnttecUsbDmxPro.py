# Enttec USB DMX Pro control interface
# Written by Ryan Smith <smit7595@umn.edu>
# Based on the API documented in http://www.enttec.com/docs/dmx_usb_pro_api_spec.pdf
# This library  is available under the MIT license found in the LICENCE file

import sys
import serial
try:
	import serial.tools
	import serial.tools.list_ports
	serial_tools_avail = True
except ImportError:
	serial_tools_avail = False
import struct
import threading
import time
import binascii
import traceback
import colorama

class EnttecUsbDmxPro:
# Constructor, destructors and globals
    def __init__(self):
        colorama.init(autoreset=True)
        self.serial = serial.Serial()
        self.debug = {'SerialBuffer':False, 'RXWarning':False, "RXMessage":False, "TX":True}
        self.widget = {'SerialNumber':0x0FFFFFFFF, 'UserParameters':{'FirmwareVersion':[0,0], 'DMXBreak':96, 'DMXMarkAfterBreak':10, 'DMXRate':40}} # Initialize the register. Note that DMXOutBreak and DMXMarkAfterBreak are in 10.67us units
        self.widget_event = {'SerialNumber':threading.Event(), 'UserParameters':threading.Event(), 'ThreadExit':threading.Event()} # Initialize the data requests variable
        self.serial.port = ""
        self.dmxRX = {"status":0,"frame":[]}
        self.dmxRXDelta = []
        self.receivedEvent = threading.Event()
        self.receivedEvent.clear()
        if sys.version_info > (3,0):
            self.py2 = False
        else:
            self.py2 = True
    def setPort(self,port,baud=57600):
        self.serial.port = port
        self.serial.baudrate = baud
    def getPort(self):
        return self.serial.port
    def setDebug(mode,value):
        self.debug[mode] = value
    def getDebug(mode="all"):
        if mode == "all":
            return self.debug
        else:
            return self.debug[mode]

# Port control
    def connect(self):
        # Open and connect to the serial port
        if self.serial.isOpen():
            print(serial)
            disconnect()
        print("Opening Enttec USB DMX Pro on",self.serial.port,"at",self.serial.baudrate,"baud")
        self.serial.open()
        self.widget_event['ThreadExit'].clear()
        self.thread_read = threading.Thread(target=self.reader)
        self.thread_read.setDaemon(True)
        self.thread_read.setName("EnttecUsbDmxPro Reader on "+self.serial.port)
        self.thread_read.start()
        print("Open successful!")
    def open(self, baud=57600): # Fix baudrate bug
        self.connect(baud)
    def isOpen(self):
        return self.serial.isOpen()
    def list(self):
        if serial_tools_avail:
            print(serial.tools.list_ports.comports())
        else:
            raise RuntimeError("Serial Tools is not available")
    def disconnect(self):
        # Disconnects from the serial port and closes read thread
        print('Stopping the read thread...')
        self.widget_event['ThreadExit'].set() # Signal the thread to stop
        self.widget_event['ThreadExit'].wait() # Wait for the signal to be cleared
        self.thread_read.join() # Make sure the thread is stopped
        print("Closing Enttec USB DMX Pro on",self.serial.port,"at",self.serial.baudrate,"baud")
        self.serial.close() # Close the serial port
        print("Close successful!")
    def close(self): 
        self.disconnect()

    def sendmsg(self,label,message=[]):
        l = len(message)
        lm = l >> 8
        ll = l-(lm << 8)
        if l <= 600:
            if self.isOpen():
                tx=[0x7E,label,ll,lm]+message+[0xE7]
                self.serial.write(bytearray(tx))
                if (self.debug['TX']):
                    sys.stderr.write("TX:{0}\n".format(tx))
        else:
            sys.stderr.write('TX_ERROR: Malformed message! The message to be send is too long!\n')
        
# Serial reading thread (and related)
    def reader(self):
        # loop forever and copy the supported values to their appropriate registers
        rx = b''
        self.serialbuffer = []
        while not self.widget_event['ThreadExit'].is_set():
            try:
                if self.serial.inWaiting() > 0:
                    rx += self.serial.read(self.serial.inWaiting()) # Read the buffer into a variable
                    for i in rx: # Convert the byte string into something a little more useful
                        if self.py2:
                            i =struct.unpack('B',i)[0]
                        self.serialbuffer += [i]
                rx = b''
                si = 0
                for i in self.serialbuffer: # Find the start byte
                    if i != 0x7E:
                        si += 1
                    else:
                        break
                if si > 0: # Remove anything before the start byte
                    if self.debug['RXWarning']:
                        if self.debug['SerialBuffer']:
                            print("IVD:",self.serialbuffer)
                        sys.stderr.write('RX_WARNING: Removing invalid data from buffer\n')
                    self.serialbuffer = self.serialbuffer[si:-1]
                if len(self.serialbuffer) >= 4:
                    m_label = self.serialbuffer[1]
                    m_size = self.serialbuffer[2] + (self.serialbuffer[3] << 8)
                    m_cont = self.serialbuffer[4:4+m_size]
                    if (self.debug['RXMessage']):
                        sys.stderr.write("{0}: {1}, {2}\n".format(m_label, m_size, m_cont))
                    endbyte_loc=4+m_size
                    if endbyte_loc >= len(self.serialbuffer):
                        if self.debug['SerialBuffer']:
                            print(self.serialbuffer)
                        if len(m_cont) == m_size:
                            if self.debug['RXWarning']:
                                sys.stderr.write('RX_WARNING: No end byte was found, but the message appears to be complete. Message will be parsed.\n')
                            self.parse(m_label,m_cont)
                            self.serialbuffer = []
                        else:
                            if self.debug['RXWarning']:
                                sys.stderr.write('RX_WARNING: Received incomplete message {0}\n'.format(self.serialbuffer))
                    elif self.serialbuffer[endbyte_loc] != 0xE7:
                        if self.debug['SerialBuffer']:
                            print(self.serialbuffer)
                        if self.debug['RXWarning']:
                            sys.stderr.write('RX_WARNING: Malformed message! Expecting an end byte, but did not find one! Found byte {0} at location {2} in self.serialbuffer {1}\n'.format(self.serialbuffer[4+m_size],self.serialbuffer,endbyte_loc))
                        self.serialbuffer = self.serialbuffer[endbyte_loc+1:]
                    else:
                        if self.debug['SerialBuffer']:
                            print(self.serialbuffer)
                        self.parse(m_label,m_cont)
                        if len(self.serialbuffer) > endbyte_loc:
                            self.serialbuffer = self.serialbuffer[endbyte_loc+1:]
            except:
                e = sys.exc_info()
                sys.stderr.write('RX_FAIL: {0}: {1}\n'.format(e[0],e[1]))
                traceback.print_tb(e[2])
                sys.stderr.write('Data in queue: {0}\n'.format(self.serialbuffer))
            time.sleep(0.01)
        self.widget_event['ThreadExit'].clear()
    def parse(self,label,message):
        # The message label and remaining data are parsed and values stored in the registers
        if label == 10: # Get widget serial number reply
            l = len(message)
            i = 0
            sn = 0
            for b in message:
                sn += (b << i*8)
                i += 1
            self.widget['SerialNumber'] = sn
            self.widget_event['SerialNumber'].set()
        elif label == 5: # Get received DMX frame
            self.dmxRX["status"] = message[0]
            fr = message[2:-1]
            self.dmxRX["frame"] = fr
            if fr != self.dmxRXDelta:
                self.dmxRXDelta = fr
                #TODO: because buggy Enttec?  For some reason the lbl 9 trigger code doesn't work
                self.receivedEvent.set()
                self.receivedEvent.clear()
        elif label == 9:
            self.receivedEvent.set()
            self.receivedEvent.clear()
        elif label == 3: # Get widget parameters reply
            self.widget['UserParameters']['FirmwareVersion'][0] = message[0]
            self.widget['UserParameters']['FirmwareVersion'][1] = message[1]
            if message[2] >=9 and message[2] <= 127:
                self.widget['UserParameters']['DMXBreak'] = message[2]
            else:
                raise UsbDmxProException("ERROR: The DMX reak time received from the widget is invalid.  Expected range: 9 to 127. Actual value: {0}".format(message[2]))
            if message[3] >=1 and message[3] <= 127:
                self.widget['UserParameters']['DMXMarkAfterBreak'] = message[3]
            else:
                raise UsbDmxProException("ERROR: The DMX mark after break time received from the widget is invalid.  Expected range: 1 to 127. Actual value: {0}".format(message[3]))
            if message[4] >=1 and message[2] <= 40:
                self.widget['UserParameters']['DMXRate'] = message[4]
            else:
                raise UsbDmxProException("ERROR: The DMX Break time received from the widget is invalid.  Expected range: 1 to 40. Actual value: {0}".format(message[4]))
            self.widget_event['UserParameters'].set()

            
# Widget properties and parameters
        
    def getWidgetParameters(self):
        # Writes the message to get the options set in the widget hardware
        # WARNING: Some third-party DMX Pro Compatible devices DO NOT support this operation
        self.sendmsg(3,[1,0])
        if not self.widget_event['UserParameters'].wait(5):
            raise UsbDmxProException("Widget parameters not received!")
        else:
            self.widget_event['UserParameters'].clear()
            return self.widget['UserParameters']

    def setWidgetParameters(self, name, value):
        # Sets the paramter `name` to `value`
        # WARNING: Some third-party DMX Pro Compatible devices DO NOT support this operation
        raise NotImplemented("The function setWidgetParameters in EnttecUsbDmxPro is not implemeted yet")
        
    def getWidgetSerialNumber(self):
        # Returns the serial number of the ENTTEC USB DMX Pro widget
        # WARNING: Some third-party DMX Pro Compatible devices DO NOT support this operation
        self.sendmsg(10)
        if not self.widget_event['SerialNumber'].wait(5):
            raise UsbDmxProException("Widget serial number not received!")
        else:
            self.widget_event['SerialNumber'].clear()
            return self.widget['SerialNumber']
# DMX
    def sendDMX(self, channels):
        # Sends an array of up to 512 channels
        data = [0] + channels
        while len(data) < 25:
            data += [0]
        self.sendmsg(6,data)
        
# RDM
    def getReceivedFrame(self):
        # Returns the last DMX frame received from the widget
        return self.dmxRX
    
    def getNextFrame(self):
        # will block and wait for the next frame
        self.waitForFrame()
        return self.getReceivedFrame()

    def getFrameDiff(self):
        frame = []
        frame.append(self.getReceivedFrame["frame"])
        self.dmxprint(frame[0])
    def waitForFrame(self):
        # block until the next frame is received
        self.receivedEvent.wait()
        
    def requestRDM(self):
        # Sends an RDM packet on the DMX and changes the direction to input to recieve it
        raise NotImplemented("The function requestRDM in EnttecUsbDmxPro is not implemeted yet")
        
    def setDmxOnChange(self, enabled=True):
        # Tells the widget to only send the DMX packet to the comptuer if the 
        #  values have changed on the input port
        print("Setting DMX on change")
        if enabled:
            self.sendmsg(8,[1])
        else:
            self.sendmsg(8,[0])
        
    def sendRdmDiscovery(self):
        # Sends an RDM discovery packet
        raise NotImplemented("The function sendRdmDiscovery in EnttecUsbDmxPro is not implemeted yet")

    def dmxprint(data):
        sys.stdout.write()
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

# Exceptions for handling DMX errors
class DMXException(Exception):
    def __init__(self,message):
        self.message = message
class UsbDmxProException(Exception):
    def __init__(self,message):
        self.message = message
