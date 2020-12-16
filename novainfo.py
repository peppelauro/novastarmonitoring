#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2018  Matthias Kolja Miehl
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
DESCRIPTION: Python script for reading and sending command via UART to
             a NovaStar M300 device
Based on the original code by https://github.com/makomi/uart2csv
"""


# -----------------------------------------------------------------------------
# include libraries and set defaults
# -----------------------------------------------------------------------------

import os
import sys
import operator
import serial
import serial.tools.list_ports
import binascii
from datetime import datetime
import struct

folder_output = "csv"
#file_cfg      = "settings.cfg"

# -----------------------------------------------------------------------------
# settings (change this as required)
# -----------------------------------------------------------------------------

serial_baud_rate     = 115200
serial_timeout_read  = 1        # number of seconds after which we consider the serial read operation to have failed
serial_timeout_msg   = "--READ-TIMEOUT--"
serial_too_short_msg = "--ADDR-TOO-SHORT: "
length_device_id     = 1024

# -----------------------------------------------------------------------------
# global variables
# -----------------------------------------------------------------------------

global selected_port       # serial port that will be used
global operator_initials   # used to identify the operator in the CSV file log
global uart                # serial port object
global file_csv            # file object for the CSV file
global serial_read_ok      # 'True' if we read what we expected

# -----------------------------------------------------------------------------
# helper functions
# -----------------------------------------------------------------------------

def mkdir(folder_name):
    """create a new folder"""
    if not os.path.isdir(folder_name):
        try:
            os.makedirs(folder_name)
        except OSError:
            if not os.path.isdir(folder_name):
                raise

def get_available_serial_ports():
    available_ports_all = list(serial.tools.list_ports.comports())               # get all available serial ports
    available_ports = [port for port in available_ports_all if port[2] != 'n/a'] # remove all unfit serial ports
    available_ports.sort(key=operator.itemgetter(1))                             # sort the list based on the port
    return available_ports

def select_a_serial_port(available_ports):                                       # TODO: check file_cfg for preselected serial port
    global selected_port
    if len(available_ports) == 0:       # list is empty -> exit
        print("[!] No suitable serial port found.")
        exit(-1)
    elif len(available_ports) == 1:     # only one port available
        (selected_port,_,_) = available_ports[0]
        print("[+] Using only available serial port: %s" % selected_port)
    else:                               # let user choose a port
        successful_selection = False
        while not successful_selection:
            #print("[+] Select one of the available serial ports:")
            # port selection
            item=1
            for port,desc,_ in available_ports:
                #print ("    (%d) %s \"%s\"" % (item,port,desc))
                item=item+1
                if desc.find("Silicon Labs CP210x USB to UART Bridge") > -1:
                    selected_item = item - 1
            #selected_item = int(raw_input(">>> "))                               # TODO: handle character input
            # check if a valid item was selected
            if (selected_item > 0) and (selected_item <= len(available_ports)):
                (selected_port,_,_) = available_ports[selected_item-1]
                successful_selection = True
            else:
                print("[!] Invalid serial port.\n")

def open_selected_serial_port():
    global uart
    try:
        uart = serial.Serial(
            selected_port,
            serial_baud_rate,
            timeout  = serial_timeout_read,
            bytesize = serial.EIGHTBITS,
            parity   = serial.PARITY_NONE,
            stopbits = serial.STOPBITS_ONE,
        )
        print("[+] Successfully connected.")
    except serial.SerialException:
        print("[!] Unable to open %s." % selected_port)
        sys.exit(-1)

def set_operator_initials():
    global operator_initials
    # get operator's initials
    print("\n[+] Operator's initials:")
    operator_initials = raw_input(">>> ")

    # make it obvious that the operator did not provide initials
    if len(operator_initials) == 0:
        operator_initials = "n/a"

def create_csv_file():
    global file_csv              # file object for CSV file
    mkdir(folder_output)         # create the output folder for the CSV files if it does not already exist
    file_csv = open('%s/%s.csv' % (folder_output,datetime.now().strftime("%Y-%m-%d %H-%M-%S")), 'w+', -1)  # FIXME: make sure the file is continuously flushed

def print_usage_guide():
    print("\nPress ENTER to read a line from the serial port.")
    print("Press 'q' and ENTER to exit.")

def check_for_exit_condition():
    """exit program after releasing all resources"""
    global uart
    global file_csv
    global serial_cmd
    if user_input == "q":
        successful_exit = False
        # close serial port
        try:
            uart.close()
            print("[+] Closed %s." % selected_port)
            successful_exit = True
        except serial.SerialException:
            print("[!] Unable to close %s." % selected_port)
        # close file
        try:
            file_csv.close()
            print("[+] Closed CSV file.")
            successful_exit = True
        except:
            print("[!] Unable to close CSV file.")
        # exit
        if successful_exit:
            exit(0)
        else:
            exit(-1)
    else:
        serial_cmd = user_input

def get_device_id():
    global uart
    global device_id
    global serial_read_ok
    # request the device's ID and read the response
    uart.write(serial_cmd)
    line = uart.readline() #.decode('ascii')
    print(line)
    line = hex(int(line.encode('hex'), 16))
    print(len(line))

    # extract the device_id (expected: "<16 character device ID>\n")
    device_id = line[0:length_device_id]
    

    # make typical whitespace characters visible
    if device_id == '\n':
        device_id = "<LF>"
    elif device_id == '\r':
        device_id = "<CR>"
    elif device_id == "\n\r":
        device_id = "<LF><CR>"
    elif device_id == "\r\n":
        device_id = "<CR><LF>"

    # display read timeout message to notify the operator
    if len(device_id) == 0:
        device_id = serial_timeout_msg
    elif len(device_id) < length_device_id:
        device_id = serial_too_short_msg + "'" + device_id + "'"
    else:
        serial_read_ok = True

def handle_device_id_duplicates():
    pass                                                                         # TODO: check if the device_id is a duplicate

def output_data():
    global file_csv
    # create a timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # display the result
    print("%s  %s" % (timestamp, device_id))

    # append the result to the CSV
    if serial_read_ok:
        file_csv.write("%s,%s,%s\n" % (timestamp, device_id, operator_initials))

    # TODO: print the device_id on paper
    # Zebra S4M, v53.17.11Z

def get_data(serial_cmd):
    global uart
    global device_id
    global serial_read_ok
    #global serial_cmd

    #print("IN GET DATA:" + hex(int(serial_cmd.encode('hex'), 16)))

    #print("CMD: " + serial_cmd)
    
    #print(serial_cmd)
    
    uart.write(serial_cmd)
    line = uart.read(1024) #.decode('ascii')
    #print(line)
    line = hex(int(line.encode('hex'), 16))
    #print(line)
    #print(len(line))

    device_id = line
    
    # display read timeout message to notify the operator
    if len(line) == 0:
        device_id = serial_timeout_msg
    elif len(device_id) < length_device_id:
        device_id = serial_too_short_msg + "'" + device_id + "'"
    else:
        serial_read_ok = True

    return line

"""
HexByteConversion

Convert a byte string to it's hex representation for output or visa versa.

ByteToHex converts byte string "\xFF\xFE\x00\x01" to the string "FF FE 00 01"
HexToByte converts string "FF FE 00 01" to the byte string "\xFF\xFE\x00\x01"
"""

#-------------------------------------------------------------------------------

def ByteToHex( byteStr ):
    """
    Convert a byte string to it's hex string representation e.g. for output.
    """
    
    # Uses list comprehension which is a fractionally faster implementation than
    # the alternative, more readable, implementation below
    #   
    #    hex = []
    #    for aChar in byteStr:
    #        hex.append( "%02X " % ord( aChar ) )
    #
    #    return ''.join( hex ).strip()        

    return ''.join( [ "%02X " % ord( x ) for x in byteStr ] ).strip()

#-------------------------------------------------------------------------------

def HexToByte( hexStr ):
    """
    Convert a string hex byte values into a byte string. The Hex Byte values may
    or may not be space separated.
    """
    # The list comprehension implementation is fractionally slower in this case    
    #
    #    hexStr = ''.join( hexStr.split(" ") )
    #    return ''.join( ["%c" % chr( int ( hexStr[i:i+2],16 ) ) \
    #                                   for i in range(0, len( hexStr ), 2) ] )
 
    bytes = []

    hexStr = ''.join( hexStr.split(" ") )

    for i in range(0, len(hexStr), 2):
        bytes.append( chr( int (hexStr[i:i+2], 16 ) ) )

    return ''.join( bytes )

#-------------------------------------------------------------------------------
def checkAck(hexStr):
    #print(hexStr)
    response = ''
    if hexStr[:6] == '0xaa55':
        res = hexStr[6:8]
        if res == '00':
            pass
        elif res == '01':
            response = 'Command failed due to time out (time out on trying to access devices connected to a sending card)'
        elif res == '02':
            response = 'Command failed due to check error on request data package'
        elif res == '03':
            response = 'Command failed due error on acknowledge data package'
        elif res == '04':
            response = 'Command failed due to invalid command'
    else:
        response = 'ACK not match HEADER!'
    if response != '':
        print('[ACK][ERROR]: ' + response)
    
    return response == ''

def checksum(hexCmd):
    hexCmd = hex(int(hexCmd.encode('hex'), 16))

    header = hexCmd[2:6]

    #Remove HEADER
    hexCmd = hexCmd[6:]

    #Remove L
    hexCmd = hexCmd[:len(hexCmd)-1]

    #print(hexCmd)

    cnt = 0
    for i in range(0, len(hexCmd), 2):
        #print(hexCmd[i:i+2])
        cnt = cnt + int(hexCmd[i:i+2], 16)
    cnt = cnt + int("5555", 16)
    chksum = hex(cnt) 
    chksum = chksum[-4:]

    #Inverte le coppie del chksum
    chksum = chksum[-2:] + chksum[:2]

    #print(chksum)
    hexCmd = header + hexCmd + chksum
    #print(hexCmd)
    hexCmd = hexCmd.decode('hex')
    #print(hexCmd)
    hexCmd = hex(int(hexCmd.encode('hex'), 16))
    #print(hexCmd)
    #print(type(hexCmd))

    hexCmd = hexCmd[2:-1]
    #print(hexCmd)
    #print(HexToByte(hexCmd))
    hexCmd = HexToByte(hexCmd)
    return hexCmd

def TempValidOfScanCard( hexStr ):
    #print("*******"+hexStr)
    ini_string = hexStr[-9:][:4]
    scale = 16
    #print(ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    #print(bin_str)

    bin_str = str(bin_str[2:])
    #print("STR " + bin_str)

    valid = bin_str[0]
    if valid == '1':
        valid = 'Ok'
    else:
        valid = 'KO'

    sign = bin_str[-1:]
    if sign == '0':
        sign = '+'
    else:
        sign = '-'
    #print(sign)

    temperature_str = bin_str[-8:][:7]
    #print(temperature_str)

    temperature_int = int(temperature_str, 2)
    value = sign + str(temperature_int)
    #print("Temperatura: " + valid + " " + value)
    return [valid, value]

def AttachedMonitorCardExist(h):
    pass

def TempOfScanCard(hexStr):
    ini_string = hexStr[-9:][:4]
    scale = 16
    #print(ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    print(bin_str)
    
def calcVolt(hexStr):
    ini_string = hexStr
    scale = 16
    #print("INI " + ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    #print("BIN " + bin_str)

    volt_str = str(bin_str[-8:])
    #print("STR " + volt_str)
    valid = volt_str[0]
    print(valid)
    if valid == '1':
        valid = 'Ok'
    else:
        valid = 'KO'
    #print(sign)

    volt_str = volt_str[1:]

    volt_int = float(int(volt_str, 2))/10
    return [valid, volt_int]

def calcHumidity(hexStr):
    ini_string = hexStr
    scale = 16
    #print("INI " + ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    #print("BIN " + bin_str)

    volt_str = str(bin_str[-8:])
    #print("STR " + volt_str)
    valid = volt_str[0]
    print(valid)
    if valid == '1':
        valid = 'Ok'
    else:
        valid = 'KO'
    #print(sign)

    volt_str = volt_str[1:]

    volt_int = int(volt_str, 2)
    value = volt_int
    return [valid, value]

def calcTemperature(hexStr):
    #print("*******"+hexStr)
    ini_string = hexStr
    scale = 16
    #print(ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    #print(bin_str)

    valid = ''
    #valid = bin_str[0]
    #if valid == '1':
    #    valid = 'Ok'
    #else:
    #    valid = 'KO'

    sign = bin_str[-1:]
    if sign == '0':
        sign = '+'
    else:
        sign = '-'
    #print(sign)

    temperature_str = bin_str[-8:][:7]
    #print(temperature_str)

    temperature_int = int(temperature_str, 2)
    value = sign+str(temperature_int)
    return [valid, value]

def VoltageOfScanCard(hexStr):
    part_volt = hexStr[-9:][:4]
    ret = calcVolt(part_volt)
    #print("Volt: " + ret[0] + str(ret[1]))
    return ret

def DVISignalChecking(hexStr):
    ini_string = hexStr[-9:][:4]
    scale = 16
    print("INI " + ini_string)
    bin_str = bin(int(ini_string, scale)).zfill(8)
    print("BIN " + bin_str)
    
def DataRefreshLux(hexStr):
    print('ref: '+hexStr)

def DataReadLux(hexStr):
    print('read: '+hexStr)

def FuncTempHumVolt(hexStr):
    #print('FuncTempHumVolt'+hexStr)

    retall = {}

    #Remove checksum
    hexStr = hexStr[:-5]
    #print(hexStr)

    part_volt = hexStr[-2:]
    #print(part_volt)
    ret = calcVolt(part_volt)
    retall['volt'] = ret
    #print("Volt: " + ret[0] + str(ret[1]))

    part_humi = hexStr[-4:-2]
    #print(part_humi)    
    ret = calcHumidity(part_humi)
    retall['humidity'] = ret
    #print("Humidity: " + ret[0] + str(ret[1]) + "%")


    part_temp = hexStr[-8:-4] 
    #print(part_temp)
    ret = calcTemperature(part_temp)
    retall['temperature'] = ret
    #print("Temperatura: " + ret[0] + " " + str(ret[1]))

    return retall

# -----------------------------------------------------------------------------
# main program
# -----------------------------------------------------------------------------

if __name__ == '__main__':

    has_multifunc = 0
    if len(sys.argv) < 3:
        print("\nError: missing parameters.")
        sys.exit(1)
    hostname = '"'+sys.argv[1]+'"' #M700 Ticker Temp
    nb_cards = int(sys.argv[2])
    has_multifunc = int(sys.argv[3])

    select_a_serial_port(get_available_serial_ports())
    open_selected_serial_port()

    #set_operator_initials()

    #create_csv_file()

    #print_usage_guide()

    commands = [
        #{'AttachedMonitorCardExist' : b'\x55\xAA\x00\x00\xFE\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x0A\x02\x00' },
        {'TempValidOfScanCard'      : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x0A\x02\x00' },
        #{'TempValidOfScanCard'      : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x0A\x02\x00' },
        #{'TempValidOfScanCard'      : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x02\x00\x00\x00\x00\x00\x00\x0A\x02\x00' },
        #{'TempOfScanCard'           : b'\x55\xAA\x00\x04\xFE\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x0A\x02\x00' },
        {'VoltageOfScanCard'        : b'\x55\xAA\x00\x05\xFE\x00\x01\x00\x00\x00\x00\x00\x03\x00\x00\x0A\x01\x00' },
        #{'VoltageOfScanCard'        : b'\x55\xAA\x00\x06\xFE\x00\x01\x00\x01\x00\x00\x00\x03\x00\x00\x0A\x01\x00' },
        #{'VoltageOfScanCard'        : b'\x55\xAA\x00\x06\xFE\x00\x01\x00\x02\x00\x00\x00\x03\x00\x00\x0A\x01\x00' },
        #{'TempValidOfScanCard'      : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x0A\x02\x00\x92\x56' },
        #{'TempOfScanCard'           : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x00\x00\x00\x00\x01\x00\x00\x0A\x02\x00\x92\x56' },
        #{'VoltageOfScanCard'        : b'\x55\xAA\x00\x00\xFE\x00\x01\x00\x00\x00\x00\x00\x03\x00\x00\x0A\x01\x00\x94\x56' },
        #{'OOO'                      : b'\x55\xAA\x00\x32\xFE\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x0A\x00\x01\x91\x56'}
        #{'DVISignalChecking'        : b'\x55\xAA\x00\x16\xFE\x00\x00\x00\x00\x00\x00\x00\x17\x00\x00\x02\x01\x00'},
        #{'DVISignalChecking'        : b'\x55\xAA\x00\x16\xFE\x00\x01\x00\x00\x00\x00\x00\x17\x00\x00\x02\x01\x00\x83\x56'},
        #{'DVISignalChecking'        : b'\x55\xAA\x00\x16\xFE\x00\x02\x00\x00\x00\x00\x00\x17\x00\x00\x02\x01\x00\x83\x56'}
        ]
    func_commands = [
        #{'DataRefreshLux'          : b'\x55\xAA\x00\x15\xFE\x00\x02\x00\x00\x00\x01\x00\x00\x00\x00\x06\x07\x00\x00\x00\x00\x00\x55\xAA\x82'},
        #{'DataReadLux'             : b'\x55\xAA\x00\x15\xFE\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x06\x07\x00'},
        #{'DataRefresh'     : b'\x55\xAA\x00\x15\xFE\x00\x02\x00\x00\x00\x01\x00\x00\x00\x00\x06\x0B\x00\x00\x00\x00\x00\x55\xAA\x01\x02\x80\xFF\x81'},
        #{'DataRead'        : b'\x55\xAA\x00\x15\xFE\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x06\x05\x00'},
        {'FuncTempHumVolt'         : b'\x55\xAA\x00\x16\xFE\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x04\x04\x00' },
    ]

    this_module = sys.modules[__name__]

    #checksum(b'\x55\xAA\x00\x00\xFE\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x0A\x02\x00')

    while True:

        serial_read_ok = False

        # wait for enter
        #user_input = raw_input("")

        # avoid empty line between results          # FIXME: this only works on Linux terminals
        #CURSOR_UP_ONE = '\x1b[1A'
        #ERASE_LINE    = '\x1b[2K'
        #print(CURSOR_UP_ONE + ERASE_LINE + CURSOR_UP_ONE)

        #check_for_exit_condition()

        result = {}

        #print('+++RECEIVING CARDS:')     
        for cmd in commands:
            for k in cmd:
                for i in range(0, nb_cards):
                    s = cmd[k][:8] + struct.pack('B', i) + cmd[k][9:]                    
                    #print(s)
                    #print(checksum(s))

                    cmd2 = checksum(s)
                    #print(k)
                    res = get_data(cmd2)
                    if checkAck(res):
                        if k in result:
                            result[k].append(getattr(this_module, k)(res))
                        else:
                            result[k] = [getattr(this_module, k)(res)]
                    #output_data()

        #print("+++MULTIFUNC CARDS:")
        if has_multifunc > 0:
            for cmd in func_commands:
                for k in cmd:
                    #print(cmd[k])
                    #print(checksum(cmd[k]))
                    cmd = checksum(cmd[k])
                    #print(k)                
                    res = get_data(cmd)
                    if checkAck(res):
                        if k in result:
                            result[k].append(getattr(this_module, k)(res))
                        else:
                            result[k] = [getattr(this_module, k)(res)]
                    #output_data()
        print(result)

        file = open('C:/zabbix/senderfile.txt', 'w')        
        count = 0
        for i in result['TempValidOfScanCard']:
            count = count + 1
            tmp = hostname + " rec_card[temperature,"+str(count)+"] " + str(i[1]) +"\n"
            print tmp
            file.write(tmp)
        count = 0
        for i in result['VoltageOfScanCard']:
            count = count + 1
            tmp = hostname + " rec_card[volt,"+str(count)+"] " + str(i[1]) + "\n"
            print tmp
            file.write(tmp)
        if 'FuncTempHumVolt' in result:
            for i in result['FuncTempHumVolt']:
                tmp = hostname + " mfun_card[volt] " + str(i["volt"][1]) + "\n"
                file.write(tmp)
                tmp = hostname + " mfun_card[temperature] " + str(i["temperature"][1]) + "\n"
                file.write(tmp)
                tmp = hostname + " mfun_card[humidity] " + str(i["humidity"][1]) + "\n"
                file.write(tmp)
        break

        #handle_device_id_duplicates()

        
