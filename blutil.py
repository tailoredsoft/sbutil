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

#-----------------------------------------------------------------------------
# Module imports
#-----------------------------------------------------------------------------
from blutilc import *

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
