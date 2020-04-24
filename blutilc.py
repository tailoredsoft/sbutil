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
#= Serial comms related
SERIAL_TIMEOUT=2.0  #e.g 2.456 will mean 2456 milliseconds
SERIAL_DEF_BAUD=115200

#- comilation realted
ALLOW_ONLINE_COMPILE=True   #Set True to disallow online compiling for security reasons
URL_XCOMPILE_SERVER='uwterminalx.lairdconnect.com'
ONLINE_SB_TEMPFILENAME='temp.sb'

#-----------------------------------------------------------------------------
# Module imports
#-----------------------------------------------------------------------------
import argparse, serial, time, subprocess, sys, os, re, tempfile, requests, json

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
if __name__ == "__main__":
    def setup_arg_parser():
        parser = argparse.ArgumentParser(
            description='Perform smartBASIC Application or Firmware operations with a Laird module.')
        parser.add_argument('-p', '--port', help="Serial port to connect to",required=True)
        parser.add_argument('-b', '--baud', type=int, default=SERIAL_DEF_BAUD, help=f"Baud rate, default={SERIAL_DEF_BAUD}")
        parser.add_argument('-v','--verbose', action="store_true", help="verbose mode", default=False)
        parser.add_argument('-n','--no-break', action="store_true", help="Do not reset with DTR deasserted")
        parser.add_argument('-t', '--timeout',
                             help="Timeout for commands like --send", default=SERIAL_TIMEOUT,type=float,
                             metavar="TIMEOUT")
        cmd_arg = parser.add_mutually_exclusive_group(required=True)
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
def to_uwc(filepath):
    parts = os.path.splitext(filepath)
    return "%s.uwc" % parts[0]


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class RuntimeError(Exception):
    pass


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class BLDevice(object):
    def __init__(self, args):
        self.port = serial.Serial(args.port, args.baud, timeout=SERIAL_TIMEOUT)

    #when calling this remember to append \r if it is a command
    def writerawcmd(self, args, expect_response=True, timeout=0.5):
        self.port.write(bytearray(args, "ascii"))
        if not expect_response:
            return
        response = b''
        start = time.time()
        while not response.endswith(b"00\r") and time.time() < start + timeout:
            response += self.port.read(1)
        if response.endswith(b"00\r"):
            return str(response, "ascii")[:-3].strip()
        else:
            if len(response) == 0:
                raise RuntimeError(
                    f"Got no response to command {repr(args)}. Not connected or not in interactive mode?")
            elif len(response) > 4 and response[0:4] == b'\n01\t':
                errorcode = str(response[4:].decode())[:-1]
                raise RuntimeError("Device returned error %s: %s" % (errorcode, get_errordesc(errorcode)))
            else:
                raise RuntimeError("Got unexpected/error response to command 'AT%s': %s" % (args, response))

    def writecmd(self, args, expect_response=True, timeout=0.5):
        command = f"AT{'' if args.startswith('+') else ' '}{args}\r"
        return self.writerawcmd(command, expect_response, timeout)
        
    def writeraw(self, args):
        self.port.write(bytearray(args, "ascii"))
        
    def read_param(self, param):
        return self.writecmd("I %d" % param).split("\t")[-1]

    def reset_into_cmd_mode(self, brk_timeout=0.1, post_timeout=0.5):
        if args.verbose:
            print("Resetting board via DTR and UART_BREAK into cmd mode ...")
        self.port.setDTR(False)
        self.port.break_condition=True
        time.sleep(brk_timeout)
        self.port.break_condition=False
        self.port.setDTR(True)
        time.sleep(post_timeout)
        self.writecmd('')
        if args.verbose:
            print("Cmd mode")

    def detect_model(self):
        print(f"Detecting...")
        self.model = self.read_param(0)
        print(f"    Device   = {self.model}")
        self.version = self.read_param(3)
        print(f"    Version  = {self.version}")
        self.langhash = self.read_param(13).split()
        if args.verbose:
            print(f"    Lang Hash= {self.langhash[0]} {self.langhash[1]}")
        self.xcompname = f"XComp_{self.model}_{self.langhash[0]}_{self.langhash[1]}.exe"
        if args.verbose:
            print(f"Xcompiler name: {self.xcompname}")

    def compile(self, filepath):
        blutil_dir = os.path.dirname(sys.argv[0])
        compiler = os.path.join(blutil_dir, self.xcompname)

        filepath = os.path.expanduser(filepath)
        filepath = os.path.abspath(filepath)
        if not os.path.exists(filepath):
            raise RuntimeError("File '%s' not found" % filepath)
        if not os.path.exists(compiler):
            if ALLOW_ONLINE_COMPILE:
                return self.online_compile(filepath)
            else:
                raise RuntimeError("Compilation failed")            
        print("Compiling %s with %s..." % (filepath, os.path.basename(compiler)))
        args = [compiler, filepath]
        if os.name != 'nt':
            args = ["wine"] + args
        ret = subprocess.call(args, stdin=None, stdout=sys.stdout, stderr=sys.stderr, shell=False)
        if ret != 0:
            raise RuntimeError("Compilation failed")
        print("Compilation success")

    def online_compile(self, filepath):
        if args.verbose:
            print('Using online compiler (Local compiler missing)')
        
        #get the xcompiler model index from online server
        url = f'http://{URL_XCOMPILE_SERVER}/supported.php?JSON=1'
        query=f"{url}&Dev={self.model}&HashA={self.langhash[0]}&HashB={self.langhash[1]}"
        if args.verbose:
            print(f"Query={query}")
        response = requests.get(query)
        if args.verbose:
            print(f"get resp_code={response.status_code}")
        if response.status_code // 100 != 2:
            error = json.loads(response.content, encoding=response.encoding)
            raise RuntimeError(f"Online compiler error code {error['Result']}: {error['Error']}")
        qresp=response.content.decode()
        if args.verbose:
            print(f"QueryResp={response.content.decode()}")
        qresp=eval(qresp)
        #generate the payload for the PUT that comes next
        payload = {'file_XComp': f"{qresp['ID']}"}

        #read the sb app source and replace #includes recursively with the code
        with open(filepath, 'r') as f:
            file_data = f.read()
            file_dir = os.path.dirname(filepath)
            file_data = self.do_include(file_data, file_dir)
            file_data = file_data.encode('utf-8')
        #and write it to a temporary file
        with open(ONLINE_SB_TEMPFILENAME,'wb') as f:
            f.write(file_data)

        #post the sb app to be compiled
        url = f'http://{URL_XCOMPILE_SERVER}/xcompile.php?JSON=1'
        files = {'file_sB': (os.path.basename(filepath), file_data, 'application/octet-stream')}
        response = requests.post(url, data=payload, files=files)
        if args.verbose:
            print('resp_code=%d'%(response.status_code))
        if response.status_code // 100 != 2:
            error = json.loads(response.content, encoding=response.encoding)
            if error['Result'] == '-9':
                raise RuntimeError(f"{error['Error']}:\n{error['Description']}")
            raise RuntimeError(f"Online compiler error code {error['Result']}: {error['Error']}")

        #save the compiled sb app to a file
        f = open(to_uwc(filepath), 'wb')
        f.write(response.content)
        f.close()
        #remove the temporary file if not in verbose mode
        if not args.verbose:
            try:
                os.remove(ONLINE_SB_TEMPFILENAME)
            except:
                pass        
        print("Online compilation success")

    def upload(self, filepath):
        filepath = os.path.expanduser(filepath)
        filepath = os.path.abspath(filepath)

        parts = os.path.splitext(filepath)
        if parts[1] != ".uwc":  # compiled files have .uwc extension
            filepath = "%s.uwc" % (parts[0],)
        appname = get_sbappname(filepath)
        print("Uploading %s as %s" % (filepath, appname))
        self.writecmd('+DEL "%s" +' % appname)
        self.writecmd('+FOW "%s"' % appname)
        with open(filepath, "rb") as f:
            for line in chunks(f, 16):
                row = "".join(["%02x" % x for x in line])
                self.writecmd('+FWRH "%s"' % row)
        self.writecmd('+FCL')
        print("Upload success")

    def run(self, filepath):
        appname = get_sbappname(filepath)
        # check is responding at all
        self.writecmd('')  
        # send run command
        print("Running %s..." % appname)
        self.writecmd('+RUN "%s"' % appname, expect_response=False)
        # try to read up to 1024 bytes for timeout period
        self.port.timeout=1.0
        output = self.port.read(1024)
        if len(output):
            if len(output) >= 3 and output[-3:] == b'00\r':
                if len(output) > 3:
                    print("Output:\n%s" % output[:-3].decode())
                print("Program completed successfully.")
            elif len(output) > 4 and output[0:4] == b'\n01\t':
                errorcode = str(output[4:].decode())[:-1]
                print("Error %s: %s" % (errorcode, get_errordesc(errorcode)))
            elif output != b'\n00':
                print("Immediate output:\n%s" % output.decode('utf-8'))
        else:
            print("No immediate output, program probably running...")

    def list(self):
        if args.verbose:
            print("Listing files...")
        output = self.writecmd('+DIR')
        print(output)

    def delete(self, filename):
        filename = get_sbappname(filename)
        if args.verbose:
            print("Removing %s..." % filename)
        self.writecmd('+DEL "%s"' % filename)
        if args.verbose:
            print("Deleted all files")

    def format(self):
        if args.verbose:
           print("Formatting filesystem only...")
        self.writerawcmd('AT&F 1\r', timeout=10)
        time.sleep(0.2)
        self.port.read(1024)  # discard anything
        if args.verbose:
            print("Format complete. Reconnecting...")
        self.writecmd('')

    def do_include(self, file, dirname):
        pattern = re.compile(r'^#include\s+"(.*)"$', re.MULTILINE)
        match = pattern.search(file)
        if match is None:
            return file

        include_path = os.path.join(dirname, match.group(1))
        include_path = os.path.abspath(include_path)

        if not os.path.exists(include_path):
            raise RuntimeError(f"Included file {include_path} does not exist")

        with open(include_path, 'r') as include_file:
            file_data = include_file.read()
            include_dirname = os.path.dirname(include_path)
            file_data = self.do_include(file_data, include_dirname)
            file = f"{file[:match.start()]}\n{file_data}\n{file[match.end():]}"

        file = self.do_include(file, dirname)

        # the online compiler doesn't allow the string #include anywhere
        # UwTerminalX does this replace too
        file = file.replace('#include', "")
        return file

    def listen(self):
        try:
            while True:
                print(self.port.read(1).decode(), end='')
        except KeyboardInterrupt:
            print('\n')


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def chunks(somefile, chunklen):
    while True:
        chunk = somefile.read(chunklen)
        if len(chunk) == 0:
            return
        yield chunk


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def get_sbappname(filepath):
    """ Given a file path, find an acceptable name on the BL filesystem """
    filename = os.path.split(filepath)[1]
    filename = filename.split('.')[0]
    return re.sub(r'[:*?"<>|]', "", filename)[:24]


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def test_wine():
    """ Check the wine installation is OK """
    try:
        with tempfile.TemporaryFile() as blackhole:
            ret = subprocess.call(["wine", "--version"], stdin=None, stdout=blackhole, stderr=None, shell=False)
        if ret != 0:
            raise RuntimeError("Wine returned error code" % ret)
    except Exception as e:
        print("Wine execution failed. %s. Make sure wine is in your path and properly configured" % e)
        sys.exit(2)


#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def get_errordesc(code):
    """ Go through file with list of error codes to find description """
    blutil_dir = os.path.dirname(sys.argv[0])
    with open(os.path.join(blutil_dir, 'codes.csv')) as f:
        for line in f:
            if str(eval("0x" + code)) in line:
                return line.split('"')[1]
                break
        return "(no description available)"

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
if __name__ == "__main__":
    def main():
        parser=setup_arg_parser()
        if os.name != 'nt':
            test_wine()
        global args
        args = parser.parse_args()
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

