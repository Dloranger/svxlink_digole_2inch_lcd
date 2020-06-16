#!/usr/bin/python

# This script is used to drive the digole 2 inch
# LCD to display the status of the control signals
# PTT/SQUELCH

# SCRIPT CONTRIBUTORS:
# Aaron Crawford (N3MBH), Dan Loranger (KG7PAR)


import smbus # for accessing the I2C bus
import socket # for getting the local IP address
import struct #for getting the local IP address
import fcntl
import time
import pigpio # used for writing images to the LCD
import RPi.GPIO as GPIO # used to subscribe to GPIO events
#import sys # used to parse files

# used to monitor the log file with notifications
import os
import traceback
import threading
import inotify.adapters

logfile = '/var/log/svxlink'

GPIO.setmode(GPIO.BCM) # use BCM gpio number for consistency
bus = smbus.SMBus(1)    # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
DEFAULT_DEVICE_ADDRESS = 0x27   #7 bit address (will be left shifted to add the read write bit)
DESIRED_DEVICE_ADDRESS = 0x28   #7 bit address (will be left shifted to add the read write bit)
ADDRESS = DESIRED_DEVICE_ADDRESS
# device address 0x27 conflicts with the gpio expanders, so it needs moved
sleepInterval=0.00
##################################################################

import re

# define regular expressions for pattern matching
TR_RE1='.*?'	# Non-greedy match on filler
TR_RE2='(TX_Port)'	# Field 1
TR_RE3='(\\d+)'	# Integer Number
TR_RE4='.*?'	# Non-greedy match on filler
TR_RE5='(Turning the transmitter )'
TR_RE6='(ON)'
TR_RE7='(OFF)' 
TR_ON =  re.compile(TR_RE1+TR_RE2+TR_RE3+TR_RE4+TR_RE5+TR_RE6,re.IGNORECASE|re.DOTALL)
TR_OFF = re.compile(TR_RE1+TR_RE2+TR_RE3+TR_RE4+TR_RE5+TR_RE7,re.IGNORECASE|re.DOTALL)
SQ_RE1='.*?'	# Non-greedy match on filler
SQ_RE2='(RX_Port)'	# Field 1
SQ_RE3='(\\d+)'	# Integer Number
SQ_RE4='.*?' 	# Non-greedy match on filler
SQ_RE5='(The squelch is )' 
SQ_RE6='(OPEN)'
SQ_RE7='(CLOSED)'
SQ_ON = re.compile(SQ_RE1+SQ_RE2+SQ_RE3+SQ_RE4+SQ_RE5+SQ_RE6,re.IGNORECASE|re.DOTALL)
SQ_OFF = re.compile(SQ_RE1+SQ_RE2+SQ_RE3+SQ_RE4+SQ_RE5+SQ_RE7,re.IGNORECASE|re.DOTALL)
def lcd_set_address (ADDRESS):
  cmd="SI2CA"
  lst=[]
  for i in cmd:
    lst.append(ord(i))
  lst.append (ADDRESS)	
  try:
    bus.write_i2c_block_data(DEFAULT_DEVICE_ADDRESS, 0, lst)
  finally:
    time.sleep(1)
    return 0  
def process(line, history=False):
  #print (line)
  # look for SQL OPENING
  m = SQ_ON.search(line)
  if m:
    RX=m.group(2)
    lcd_draw_indicator(DESIRED_DEVICE_ADDRESS,(ord(RX)-0x30),"SQL",1)
    #print ("turning on squelch indicator")
  # look for SQL CLOSING
  m = SQ_OFF.search(line)
  if m:
    RX=m.group(2)
    lcd_draw_indicator(DESIRED_DEVICE_ADDRESS,(ord(RX)-0x30),"SQL",0)
    #print ("turning off squelch indicator")
  # look for TX ON
  m = TR_ON.search(line)
  #print (m)
  if m:
    TX=m.group(2)
	#print ("turning on PTT indicator:",TX)
    lcd_draw_indicator(DESIRED_DEVICE_ADDRESS,(ord(TX)-0x30),"PTT",1)
  # look for TX OFF
  m = TR_OFF.search(line)
  if m:
    TX=m.group(2)
	#print ("turning off PTT indicator:",TX)
    lcd_draw_indicator(DESIRED_DEVICE_ADDRESS,(ord(TX)-0x30),"PTT",0)  
def lcd_draw_filled_rectangle(ADDRESS,X1,Y1,X2,Y2,ForeGroundColor,BackGroundColor):
  lcd_set_background(ADDRESS,BackGroundColor)
  lcd_set_foreground(ADDRESS,ForeGroundColor)
  lst=[]
  lst.append(ord("F"))
  lst.append(ord("R")) 
  if X1 < 255:
    lst.append(X1)
  else:
    lst.append (255)
    lst.append (X1-255)
  if Y1 < 255:
    lst.append(Y1)
  else:
    lst.append =(255)
    lst.append(Y1-255)
  if X2 < 255:
    lst.append(X2)
  else:
    lst.append(255)
    lst.append(X2-255)
  if Y2 < 255:
    lst.append(Y2)
  else:
    lst.append(255)
    lst.append(Y2-255)
  bus.write_i2c_block_data(ADDRESS, 0, lst)
  return 0
def lcd_clear (ADDRESS):
  lcd_set_background(ADDRESS,0)
  bus.write_i2c_block_data(ADDRESS, 0, [0x43, 0x4C])
  return 0 
def lcd_write_line (ADDRESS,TEXT):
  TEXT="TT"+TEXT
  lst=[]
  for i in TEXT:
    lst.append(ord(i)) 
  lst.append(10)
  lst.append(13)
  bus.write_i2c_block_data(ADDRESS, 0, lst)
  return 0 
def lcd_write_text (ADDRESS,TEXT):
  TEXT="TT"+TEXT
  lst=[]
  for i in TEXT:
    lst.append(ord(i)) 
  bus.write_i2c_block_data(ADDRESS, 0, lst)
  return 0
def lcd_set_background (ADDRESS,color):
  cmd="BGC"
  lst=[]
  for i in cmd:
    lst.append(ord(i))
  lst.append (color)	
  bus.write_i2c_block_data(ADDRESS, 0, lst)
  return 0
def lcd_set_foreground (ADDRESS,color):
  cmd="SC"
  lst=[]
  for i in cmd:
    lst.append(ord(i))
  lst.append (color)	
  bus.write_i2c_block_data(ADDRESS, 0, lst)
  return 0 
def get_ip_address():
  try:#s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  #s.connect(("8.8.8.8", 80))
  #ip=s.getsockname()[0]
  #s.close
  #~~~
    ip = os.system('hostname -I > /tmp/ip.txt')
    pi = pigpio.pi()
    with open('/tmp/ip.txt', 'rb') as f:
      data = f.read()
    os.system('rm -f /tmp/ip.txt')
    #~~~
    #ip = socket.gethostbyname(hostname) 
    return str(data)
  finally:
    return "X.X.X.X" 
def get_interface_ipaddress(network):
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  return socket.inet_ntoa(fcntl.ioctl(
    s.fileno(),
    0x8915,  # SIOCGIFADDR
    struct.pack('256s', network[:15])
  )[20:24])
def lcd_set_orientaion( ADDRESS, Direction ):
  if Direction == "up":
    val=0x0
  elif Direction == "left":
    val=0x1
  elif Direction == "down":
    val=0x2
  elif Direction == "right":
    val=0x3
  else:
    return 1
  bus.write_i2c_block_data(ADDRESS, 0, [0x53, 0x44, val])
  return 0
def lcd_write_ip_address(ADDRESS):
  Leader="IP ADDR:"
  #try 5 times to get the IP address
  for x in range (6):
    try:
      IP=get_ip_address()
      #IP = get_interface_ipaddress('eth0')
      if len(IP) == 1:
        time.sleep (x)
        #lcd_write_text(ADDRESS,"No ADDRESS FOUND")
      else:
        length=len(IP)
        
        lead_lenth=len(Leader)
        size=25-length-lead_lenth
        pad=""
        for i in range (0,size-1,1):
          pad=pad+" "
        message=Leader+pad+IP
        break
    finally:
	  pass
  try:
	lcd_write_text(ADDRESS,message[0:29])
	lcd_write_line(ADDRESS,message[29::])
  finally:
    pass
		
def lcd_load_image(ADDRESS,fileName):
  pi = pigpio.pi()              # use defaults
  with open(fileName, 'rb') as f:
    data = f.read()
  time.sleep (1)
  i2c_handle=pi.i2c_open(1,ADDRESS) # open the I2C bus 1)
  pi.i2c_write_device(i2c_handle,data) # write the data to the lcd
  pi.i2c_close (i2c_handle) # close the bus
  return 0  
def lcd_set_font(ADDRESS,font_code):
  cmd=[]
  cmd.append(ord("S"))
  cmd.append(ord("F"))
  if font_code == 6:
    cmd.append(font_code)
  elif font_code == 10:
    cmd.append(font_code)  
  elif font_code == 18:	
    cmd.append(font_code)
  elif font_code == 51:	
    cmd.append(font_code)
  elif font_code == 120:
    cmd.append(font_code)
  elif font_code == 123:
    cmd.append(font_code)  
  else:
    print ("Invalid font code")
    return 1
  bus.write_i2c_block_data(ADDRESS,0,cmd)
  return 0  
def lcd_set_position(ADDRESS,X,Y):
  cmd=[]
  cmd.append(ord("T"))
  cmd.append(ord("P"))
  cmd.append((X))
  cmd.append((Y))
  bus.write_i2c_block_data(ADDRESS,0,cmd)
  return 0  
def lcd_draw_indicator(Address, channel, Type, Enable): #starts with channel 1
  #print "Entered the drawing function"
  X1=123
  if ((Type == "ptt") | (Type == "PTT")):
    Y1=120
    Color=0xE0
  elif ((Type == "sql") | (Type == "SQL")):
    Y1=144
    Color=0x7C
  elif ((Type == "ctcss") | (Type == "CTCSS")):
    Y1=168
    Color=0x23
  else:
    print("LCD DRAW INDICATOR BAD TYPE")

  X1=X1+(channel*22)
  X2=137+(channel*22)
  Y2=Y1+18
  #print "made it past the calculations"
  
  if Enable:
    lcd_draw_filled_rectangle(ADDRESS,X1,Y1,X2,Y2,Color,0x00)
    #print "successfully drew the rectangle"
  else:
    lcd_draw_filled_rectangle(ADDRESS,X1,Y1,X2,Y2,0x00,0x00)
    #print "successfully erased the rectangle"
  return 0
#####################################################
#
# Initialize the display
#
#####################################################
lcd_set_address(DESIRED_DEVICE_ADDRESS)
lcd_clear(DESIRED_DEVICE_ADDRESS)
lcd_set_orientaion (DESIRED_DEVICE_ADDRESS,"left")
# setup the logo as white on black background
lcd_set_background(DESIRED_DEVICE_ADDRESS,255)
lcd_set_foreground(DESIRED_DEVICE_ADDRESS,0)
#lcd_load_image(DESIRED_DEVICE_ADDRESS,"/usr/local/bin/Digole_lcd_logo.raw")  #Broken or bad file?
#setup the Product Name, white text on black background
lcd_set_background(DESIRED_DEVICE_ADDRESS,0)
lcd_set_foreground(DESIRED_DEVICE_ADDRESS,255)
lcd_set_font(DESIRED_DEVICE_ADDRESS,51)
lcd_set_position(DESIRED_DEVICE_ADDRESS,0x00,0x00)
lcd_write_line(DESIRED_DEVICE_ADDRESS, "       PI-REPEATER-8X")
# setup the IP address as blue on black background
lcd_set_font(DESIRED_DEVICE_ADDRESS,51)
lcd_set_background(DESIRED_DEVICE_ADDRESS,0)
lcd_set_foreground(DESIRED_DEVICE_ADDRESS,63)
lcd_write_ip_address(DESIRED_DEVICE_ADDRESS)
# setup the labels for the channel indicators
lcd_set_position(DESIRED_DEVICE_ADDRESS,14,4)
lcd_set_font(DESIRED_DEVICE_ADDRESS,51)
lcd_set_background(DESIRED_DEVICE_ADDRESS,0)
lcd_set_foreground(DESIRED_DEVICE_ADDRESS,0xFF)
lcd_write_line(DESIRED_DEVICE_ADDRESS, "CH 1 2 3 4 5 6 7 8")
lcd_set_position(DESIRED_DEVICE_ADDRESS,12,5)
lcd_write_line(DESIRED_DEVICE_ADDRESS,"PTT")
lcd_set_position(DESIRED_DEVICE_ADDRESS,12,6)
lcd_write_line(DESIRED_DEVICE_ADDRESS,"SQL") 
#not sure how to monitor these just yet
#lcd_set_position(DESIRED_DEVICE_ADDRESS,7,7)
#lcd_write_line(DESIRED_DEVICE_ADDRESS,"CTCSS")

# MONITORING THE LOG FILES
from_beginning = False
notifier = inotify.adapters.Inotify()
while True:
  #print ("In the loop")
  try:
    #------------------------- check
    if not os.path.exists(logfile):
      print ('logfile does not exist')
      time.sleep(sleepInterval)
      continue
    #print ('opening and starting to watch', logfile)
    #------------------------- open
    file = open(logfile, 'r')
    file.seek(0,2)
    #------------------------- watch
    notifier.add_watch(logfile)
    try:
      for event in notifier.event_gen():
        #print (event)
        if event is not None:
          (header, type_names, watch_path, filename) = event
          if set(type_names) & set(['IN_MOVE_SELF']): # moved
            #print ('logfile moved')
            notifier.remove_watch(logfile)
            file.close()
            time.sleep(sleepInterval)
            break
          elif set(type_names) & set(['IN_MODIFY']): # modified
            #print ("Logfile updated")
            for line in file.readlines():
              process(line, history=False)
              #print (line)
    except (KeyboardInterrupt, SystemExit):
      raise
    except:
      notifier.remove_watch(logfile)
      file.close()
      time.sleep(sleepInterval)
    #-------------------------
  except (KeyboardInterrupt, SystemExit):
    break
  except inotify.calls.InotifyError:
    time.sleep(sleepInterval)
    print ("inotify error")
  except IOError:
    time.sleep(sleepInterval)
    print ("i/o Error")
  except:
    traceback.print_exc()
    time.sleep(sleepInterval)

##################################################################
