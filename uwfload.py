#!/usr/bin/env python3
"""
This is a command line tool for downloading firmware to Laird "SmartBASIC" devices.

Usage: python3 uwfload.py serialport baudrate model filepath
           port      example on windows would be COM123
           baudrate  e.g. 115200
           model     one of BL652,BL653,BL654,BL654IG,RM1XX,GENERIC
           filepath  path and name of .uwf file (delimited by "" if space in name)

Original works by:
  uwf_processer_*.py, uwfloader.py
    Moses Corriea of Laird Connectivity.

Subsequently enhanced by:
  Mahendra Tailor 
"""

##########################################################################################
# Copyright (C)2014 Angus Gratton, released under BSD license as per the LICENSE file.
##########################################################################################

#-----------------------------------------------------------------------------
# constants
#-----------------------------------------------------------------------------

VERBOSELEVEL=0
DEFAULT_MODULE='BL654'

#-----------------------------------------------------------------------------
# Module imports
#-----------------------------------------------------------------------------
import uwfloader
import os
import sys
import serial

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def main():
    if len(sys.argv) != 5:
        print(f"Usage: python3 {sys.argv[0]} serialport baudrate model filepath")
        print('      [serialport] is like COM12 on Windows, or /dev/ttyUSB34 on Linux')
        print('      [baudrate] is like 115200')
        print('      [model] is one of BL652,BL653,BL654,BL654IG,RM1XX,GENERIC')
        print('      Delimit [filepath] with "" when it contains spaces')
    else:
        #download firmware
        uwfloader.loadfirmware(sys.argv[1],sys.argv[2],sys.argv[4],sys.argv[3])
        
        
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(e)
        sys.exit(2)
    except serial.SerialException as e:
        print(e)
        sys.exit(3)
