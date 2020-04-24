#!/usr/bin/env python3
"""
This is a command line tool for programming Laird "SmartBASIC" devices.
    - Compile and download smartBASIC applications
    - Download firmware images over the uart

Original works by:
  blutil.py
    Copyright (C)2014 Angus Gratton, released under BSD license as per the LICENSE file.

Subsequently enhanced by:
  Dimitri Siganos
  Oli Solomons
  Mahendra Tailor 
"""

##########################################################################################
# Copyright (C)2014 Angus Gratton, released under BSD license as per the LICENSE file.
##########################################################################################

#-----------------------------------------------------------------------------
# constants
#-----------------------------------------------------------------------------

DEBUGLEVEL=3

#-----------------------------------------------------------------------------
# Module imports
#-----------------------------------------------------------------------------
import blutilc
import uwfloader
import os
import sys
import serial

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def setup_arg_parser():
    parser = blutilc.argparse.ArgumentParser(
        description='Perform smartBASIC Application or Firmware operations with a Laird module.')
    parser.add_argument('-p', '--port', help="Serial port to connect to",required=True)
    parser.add_argument('-b', '--baud', type=int, default=blutilc.SERIAL_DEF_BAUD, help=f"Baud rate, default={blutilc.SERIAL_DEF_BAUD}")
    parser.add_argument('-v','--verbose', action="store_true", help="verbose mode", default=False)
    parser.add_argument('-n','--no-break', action="store_true", help="Do not reset with DTR deasserted")
    parser.add_argument('-t', '--timeout',
                         help="Timeout for commands like --send", default=blutilc.SERIAL_TIMEOUT,type=float,
                         metavar="TIMEOUT")
    cmd_arg = parser.add_mutually_exclusive_group(required=True)
    cmd_arg.add_argument('-f', '--firmware', help="Download a .uwf firmware file to device", metavar="UWF_FILE")
    cmd_arg.add_argument('-c', '--compile', help="Compile specified smartBasic file to a .uwc file.", metavar="SBFILE")
    cmd_arg.add_argument('-l', '--load',
                         help="Upload specified smartBasic file to device (if argument is a .sb file it will be compiled first.)",
                         metavar="FILE")
    cmd_arg.add_argument('-r', '--run',
                         help="Execute specified smartBasic file on device (if argument is a .sb file it will be compiled and uploaded first, if argument is a .uwc file it will be uploaded first.)",
                         metavar="FILE")
    cmd_arg.add_argument('-s', '--send',
                         help="Send the string CMD terminated by and listen for {SERIAL_TIMEOUT} seconds \\r",
                         metavar="CMD")
    cmd_arg.add_argument('--ls', action="store_true", help="List all files uploaded to the device")
    cmd_arg.add_argument('--rm', metavar="FILE", help="Remove specified file from the device")
    cmd_arg.add_argument('--format', action="store_true", help="Erase all stored files from the device")
    cmd_arg.add_argument('--listen', action="store_true",
                         help="Listen over serial for incoming messages, e.g. from print statements in a running program")
    return parser

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def main():
    parser=setup_arg_parser()
    if os.name != 'nt':
        test_wine()
    global args
    args = parser.parse_args()

    if args.firmware is None:
        #make the args visible to blutilc
        blutilc.args=args
        #create an instance of a smartBASIC device as per the class in blutilc.py
        device = BLDevice(args)

        # Preload any .sb or .uwc file
        if args.run is not None:
            split = os.path.splitext(args.run)
            if split[1] == ".uwc" or split[1] == ".sb":
                args.load = args.run

        # Precompile any .sb file
        if args.load is not None:
            split = os.path.splitext(args.load)
            if split[1] == ".sb":
                args.compile = args.load

        ops = []
        if args.compile:
            ops += ["compile"]
        if args.load:
            ops += ["load"]
        if args.run:
            ops += ["run"]

        #if break into command mode via reset/urt_break then do so
        if not args.no_break:
            device.reset_into_cmd_mode()

        if args.compile:
            device.detect_model()

        if len(ops) > 0:
            print("Performing %s for %s..." % (", ".join(ops), sys.argv[-1]))

        if args.ls:
            device.list()
        if args.rm:
            device.delete(args.rm)
        if args.format:
            device.format()
        if args.compile:
            device.compile(args.compile)
        if args.load:
            device.upload(args.load)
        if args.run:
            device.run(args.run)
        if args.send:
            cmdstr=f"{args.send}\r"
            print(device.writerawcmd(cmdstr, timeout=args.timeout))
            print("Command completed")
        if args.listen:
            device.listen()
    else:
        #if break into command mode via reset/urt_break then do so
        #if not args.no_break:
        #    device.reset_into_cmd_mode()
        #print(f"uwfloader.loadfirmware({args.port},{args.baud},{args.firmware},'BL654')")
        uwfloader.loadfirmware(args.port,args.baud,args.firmware,'XXBL654XX')
        
        
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
