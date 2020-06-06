##########################################################################################
# Copyright (C)2020 Laird Connectivity
# Original author : Moses Corriea
# Modified by     : Mahendra Tailor
##########################################################################################
import serial
import binascii
import struct
import time

VERBOSELEVEL=2

DEVICE_TYPE_BL654IG  = 'BL654IG'
DEVICE_TYPE_BL654    = 'BL654'
DEVICE_TYPE_BL653    = 'BL653'
DEVICE_TYPE_BL652    = 'BL652'
DEVICE_TYPE_RM1XX    = 'RM1XX'
DEVICE_TYPE_BT900    = 'BT900'

SERIAL_TIMEOUT_SEC = 3
DATA_BLOCK_SIZE=252      #16 to 252, uwflash uses 128, value must be divisible by 4

COMMAND_ENTER_BOOTLOADER = b'AT+FUP\r'
COMMAND_SYNC_WITH_BOOTLOADER = '80'
COMMAND_PLATFORM_CHECK = 'p'
COMMAND_ERASE_SECTOR = 'e'
COMMAND_WRITE_SECTOR = 'w'
COMMAND_DATA_SECTION = 'd'
COMMAND_VERIFY_DATA = 'v'
COMMAND_REBOOT_BOOTLOADER = 'z'

UWF_OFFSET_HANDLE = 1
UWF_OFFSET_BANK = 2
UWF_OFFSET_BASE_ADDRESS = 5
UWF_OFFSET_NUM_BANKS = 6
UWF_OFFSET_BANK_SIZE = 10
UWF_OFFSET_BANK_ALGO = 11
UWF_OFFSET_SECTORS = 4
UWF_OFFSET_SECTOR_SIZE = 8
UWF_OFFSET_ERASE_START_ADDR = 4
UWF_OFFSET_ERASE_SIZE = 8
UWF_OFFSET_WRITE_OFFSET = 4
UWF_OFFSET_WRITE_FLAGS = 8

UWF_WRITE_BLOCK_HDR_LENGTH = 8
UWF_UI32_SIZE = 4

RESPONSE_ATS_SIZE = 14
RESPONSE_ACKNOWLEDGE = 'a'
RESPONSE_ERROR = 'f'
RESPONSE_ACKNOWLEDGE_SIZE = 1

ERROR_BOOTLOADER = 'enter_bootloader: {}\n'
ERROR_TARGET_PLATFORM = 'process_command_target_platform: {}\n'
ERROR_REGISTER_DEVICE = 'process_command_register_device: {}\n'
ERROR_ERASE_BLOCKS = 'process_command_erase_blocks: {}\n'
ERROR_WRITE_BLOCKS = 'process_command_write_blocks: {}\n'

def init_processor(dev_type, port, baudrate):
    """
    Instantiates and returns the requested processor
    """

    if dev_type == DEVICE_TYPE_BL654IG:
        # Import the IG60_BL654 custom processor
        from uwf_processor_ig60_bl654 import UwfProcessorIg60Bl654
        processor = UwfProcessorIg60Bl654(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")
        
    elif dev_type == DEVICE_TYPE_BL654:
        # Import the BL654 custom processor
        from uwf_processor_bl654 import UwfProcessorBl654
        processor = UwfProcessorBl654(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")
        
    elif dev_type == DEVICE_TYPE_BL653:
        # Import the BL653 custom processor
        from uwf_processor_bl653 import UwfProcessorBl653
        processor = UwfProcessorBl653(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")
        
    elif dev_type == DEVICE_TYPE_BL652:
        # Import the BL653 custom processor
        from uwf_processor_bl652 import UwfProcessorBl652
        processor = UwfProcessorBl652(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")
        
    elif dev_type == DEVICE_TYPE_RM1XX:
        # Import the RM1XX custom processor
        from uwf_processor_rm1xx import UwfProcessorRM1XX
        processor = UwfProcessorRM1XX(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")

    elif dev_type == DEVICE_TYPE_BT900:
        # Import the BT900 custom processor
        from uwf_processor_bt900 import UwfProcessorBT900
        processor = UwfProcessorBT900(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type}")
        
    else:
        # Use the generic processor
        processor = UwfProcessor(port, baudrate)
        if VERBOSELEVEL>=2:
            print(f"Initialise {dev_type} as GENERIC")

    processor.enter_bootloader()

    return processor

class SectorMapIter():
    def __init__(self, tupSectors, tupSectorSz, nOffsetStart, nOffsetEnd):
        if len(tupSectors)>0 and len(tupSectors) == len(tupSectorSz):
            self.tSectors = tupSectors
            self.tSectorSz = tupSectorSz
        else:
            raise Exception('Sector map invalid')            
        self.nOffset    = nOffsetStart
        self.nOffsetEnd = nOffsetEnd

    def __iter__(self):
        self.tuple_Idx=0
        self.sector_num=0
        self.sectorThisBase=0
        return self

    def __next__(self):
        for idx in range(self.tuple_Idx,len(self.tSectors)):
            sector_numof=self.tSectors[idx]
            sector_size =self.tSectorSz[idx]
            for num in range(self.sector_num,sector_numof):
                sectorNextBase = self.sectorThisBase + sector_size
                if self.nOffset < sectorNextBase:
                    self.nOffset = sectorNextBase
                    self.sector_num=num
                    self.tuple_Idx=idx
                    return self.sectorThisBase
                self.sectorThisBase=sectorNextBase
                #check if above range end
                if sectorNextBase >= self.nOffsetEnd:
                    raise StopIteration  
            self.sector_num=0
        raise StopIteration


class UwfProcessor():
    """
    Base class that captures the foundational data and functions
    to process a UWF file
    """
    def __init__(self, port, baudrate):
        self.synchronized = False
        self.registered = False
        self.erased = False
        self.write_complete = False
        self.sectors = []
        self.sector_size = []
        self.selected_handle = None

        # Number of bytes of data to write for each write command
        self.write_block_size = DATA_BLOCK_SIZE

        # The number of data blocks writes to perform before verifying
        self.verify_write_limit = 8

        # Open the COM port to the Bluetooth adapter
        self.ser = serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT_SEC)
        
        #initialise storage for registered memory blocks
        self.mem_base_address = {}
        self.mem_num_banks    = {}
        self.mem_bank_size    = {}
        self.mem_bank_algo    = {}
        

    def write_to_comm(self, data, resp_size):
        self.ser.write(data)
        return self.ser.read(resp_size)

    def enter_bootloader(self, postdelay=0.5):
        if VERBOSELEVEL>=2:
            print(f"Entering Bootloader mode..")
            
        result = True
        #flush the serial rx buffer 
        self.ser.reset_input_buffer()

        # Send the bootloader command via smartBasic
        self.ser.write(COMMAND_ENTER_BOOTLOADER)

        #wait for the module to reset and start
        time.sleep(postdelay)
        
        # Verify no error
        response = self.ser.readline()
        if len(response) != 0:
            result = False
        elif VERBOSELEVEL>=2:
            print(f"In Bootloader")

        return result
        
    def process_command_target_platform(self, file, data_length):
        if VERBOSELEVEL>=3:
            print(f"TARGET_PLATFORM")
        error = None

        # Synchronize with the bootloader
        port_cmd_bytes = bytearray.fromhex(COMMAND_SYNC_WITH_BOOTLOADER)
        response = self.write_to_comm(port_cmd_bytes, RESPONSE_ATS_SIZE)

        if len(response) == RESPONSE_ATS_SIZE:
            # Acknowledge the response
            port_cmd_bytes = bytearray(RESPONSE_ACKNOWLEDGE, 'utf-8')
            response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)

            if response.decode('utf-8') == RESPONSE_ACKNOWLEDGE:
                # Send the target platform data
                platform_command = bytearray(COMMAND_PLATFORM_CHECK, 'utf-8')
                platform_id = file.read(data_length)
                if VERBOSELEVEL>=2:
                    targetId = struct.unpack('I', platform_id)[0]
                    print(f"Platform: id={'0x%08X'%(targetId)}")
                port_cmd_bytes = platform_command + platform_id
                response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)

                if response.decode('utf-8') == RESPONSE_ACKNOWLEDGE:
                    self.synchronized = True
                elif response.decode('utf-8') == RESPONSE_ERROR:
                    error = ERROR_TARGET_PLATFORM.format('Invalid platform ID')
                else:
                    error = ERROR_TARGET_PLATFORM.format('Non-ack to platform ID')
            else:
                error = ERROR_TARGET_PLATFORM.format('Non-ack or error in ATS acknowledge response')
        else:
            error = ERROR_TARGET_PLATFORM.format('Failed to sync with the bootloader')

        return error

    def process_command_register_device(self, file, data_length):
        if VERBOSELEVEL>=3:
            print(f"REGISTER_DEVICE")
        register_device_data = file.read(data_length)
        #extract handle
        handle = struct.unpack('B', register_device_data[:UWF_OFFSET_HANDLE])[0]
        #extract base address
        base_address = struct.unpack('<I', register_device_data[UWF_OFFSET_HANDLE:UWF_OFFSET_BASE_ADDRESS])[0]
        self.mem_base_address[handle]=base_address
        #extract banks
        num_banks = struct.unpack('B', register_device_data[UWF_OFFSET_BASE_ADDRESS:UWF_OFFSET_NUM_BANKS])[0]
        self.mem_num_banks[handle]=num_banks
        #extract bank size
        bank_size = struct.unpack('<I', register_device_data[UWF_OFFSET_NUM_BANKS:UWF_OFFSET_BANK_SIZE])[0]
        self.mem_bank_size[handle]=bank_size
        #extarct bank alogorithm
        bank_algo = struct.unpack('B', register_device_data[UWF_OFFSET_BANK_SIZE:UWF_OFFSET_BANK_ALGO])[0]
        self.mem_bank_algo[handle]=bank_algo
        
        if VERBOSELEVEL>=2:
            print(f"Register Device: hndl={handle} addr={base_address} banks={num_banks} size={bank_size} algo={bank_algo}")

        self.registered = True

        return None

    def process_command_select_device(self, file, data_length):
        if VERBOSELEVEL>=3:
            print(f"SELECT_DEVICE")
        select_device_data = file.read(data_length)
        self.selected_handle = struct.unpack('B', select_device_data[:UWF_OFFSET_HANDLE])[0]
        self.selected_bank = struct.unpack('B', select_device_data[UWF_OFFSET_HANDLE:UWF_OFFSET_BANK])[0]
        if VERBOSELEVEL>=2:
            print(f"Select Device: hndl={self.selected_handle} bank={self.selected_bank}")

        return None

    #will return True if 'memsize' is equal to the sum of all sectors mentioned in the map
    def __VerifySectorMap(self,banksize):
        sum=0
        for i in range(len(self.sectors)):
            sum += self.sectors[i] * self.sector_size[i]
        if sum != banksize:
            return False
        return True

    def process_command_sector_map(self, file, data_length):
        if VERBOSELEVEL>=3:
            print(f"SECTOR_MAP")
        sector_map_data = file.read(data_length)
        arrsize=int(data_length/(UWF_UI32_SIZE+UWF_UI32_SIZE))
        if arrsize*(UWF_UI32_SIZE+UWF_UI32_SIZE) != data_length:
            raise Exception('SectorMap length error in uwf file')
        pos=0
        self.sectors = []
        self.sector_size = []
        while arrsize>0:
            sectors = struct.unpack('<I', sector_map_data[pos:pos+UWF_UI32_SIZE])[0]
            self.sectors.append(sectors)
            pos = pos+UWF_UI32_SIZE
            sector_size = struct.unpack('<I', sector_map_data[pos:pos+UWF_UI32_SIZE])[0]
            self.sector_size.append(sector_size)
            pos = pos+UWF_UI32_SIZE
            arrsize -= 1
        if VERBOSELEVEL>=2:
            print(f"Sector Map: sectors={self.sectors} size={self.sector_size}")
        if not self.selected_handle is None :
            if self.__VerifySectorMap(self.mem_bank_size[self.selected_handle]) == False:
                raise Exception('SectorMap not consistent with bank size')
        return None

    def process_command_erase_blocks(self, file, data_length):
        """
        Erases blocks according to the sector size value from the the UWF file
        """
        if VERBOSELEVEL>=3:
            print(f"ERASE_BLOCK")
        error = None

        if self.synchronized       and \
           self.registered         and \
           len(self.sectors)>0     and self.sectors[0] > 0 and \
           len(self.sector_size)>0 and self.sector_size[0] > 0:
            # Get the UWF erase data
            erase_data = file.read(data_length)
            baseaddr=self.mem_base_address[self.selected_handle]
            offset = struct.unpack('<I', erase_data[:UWF_OFFSET_ERASE_START_ADDR])[0]
            size = struct.unpack('<I', erase_data[UWF_OFFSET_ERASE_START_ADDR:UWF_OFFSET_ERASE_SIZE])[0]
            if VERBOSELEVEL>=2:
                print(f"Erase Block: addr=0x{baseaddr+offset:08x} (offset=0x{offset:x}) size={size} (0x{size:x})")
            
            if offset+size <= self.mem_bank_size[self.selected_handle]:
                erase_command = bytearray(COMMAND_ERASE_SECTOR, 'utf-8')
                map_iter=SectorMapIter(self.sectors, self.sector_size, offset, offset+size)
                for ofs in map_iter:
                    erase_sector = struct.pack('<I', ofs+baseaddr)
                    port_cmd_bytes = erase_command + erase_sector
                    response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)
                    if response.decode('utf-8') != RESPONSE_ACKNOWLEDGE:
                        error = ERROR_ERASE_BLOCKS.format('Non-ack to erase command')
                        break
                    if VERBOSELEVEL>=2:
                        print('.',end='',flush=True)
                else:
                    self.erased = True
                if VERBOSELEVEL>=2:
                    print('.',end='\n',flush=True)
            else:
                error = ERROR_ERASE_BLOCKS.format('Erase block size plus offset > bank size')
        else:
            error = ERROR_ERASE_BLOCKS.format('Target platform, register device, or sector map commands not yet processed')

        return error

    def process_command_write_blocks(self, file, data_length):
        """
        Sends the write command, then a data block 'X' times, then verifies
        The size of the data block and the number of data blocks before verification are configurable
        """
        if VERBOSELEVEL>=3:
            print(f"WRITE_BLOCK")
        error = None

        if self.erased:
            last_write = False
            verify_checksum = 0
            verify_count = 1
            verify_data_block_size = 0

            # Get the UWF write data
            write_data = file.read(UWF_WRITE_BLOCK_HDR_LENGTH)
            baseaddr=self.mem_base_address[self.selected_handle]
            offset = struct.unpack('<I', write_data[:UWF_OFFSET_WRITE_OFFSET])[0]
            flags = struct.unpack('<I', write_data[UWF_OFFSET_WRITE_OFFSET:UWF_OFFSET_WRITE_FLAGS])[0]
            remaining_data_size = data_length - UWF_WRITE_BLOCK_HDR_LENGTH
            if VERBOSELEVEL>=2:
                print(f"Write Block: addr=0x{offset+baseaddr:08x} (offset=0x{offset:x}) flags=0x{flags:x}  len={remaining_data_size} (0x{remaining_data_size:x})")

            if remaining_data_size <= self.mem_bank_size[self.selected_handle]:
                verify_start_addr = struct.pack('<I', offset+baseaddr)
                while remaining_data_size > 0:
                    if remaining_data_size < self.write_block_size:
                        bytes_to_write = remaining_data_size
                        last_write = True
                    else:
                        bytes_to_write = self.write_block_size

                    if VERBOSELEVEL>=2:
                        print('.',end='',flush=True)
                        
                    # Send the write command
                    write_command = bytearray(COMMAND_WRITE_SECTOR, 'utf-8')
                    start_addr = struct.pack('<I', offset+baseaddr)
                    data_block_size = struct.pack('B', bytes_to_write)
                    port_cmd_bytes = write_command + start_addr + data_block_size
                    response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)

                    if response.decode('utf-8') == RESPONSE_ACKNOWLEDGE:
                        # Prepare the data
                        data_command = bytearray(COMMAND_DATA_SECTION, 'utf-8')
                        data = file.read(bytes_to_write)

                        # Generate the checksum
                        i = 0
                        checksum = 0
                        while i < len(data):
                            checksum += struct.unpack('B', data[i:i+1])[0]
                            i += 1
                        checksum_bytes = struct.pack('<I', checksum)

                        # Write the data
                        port_cmd_bytes = data_command + data
                        port_cmd_bytes.append(checksum_bytes[0])    # Only need the LSB of the checksum
                        response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)

                        if response.decode('utf-8') == RESPONSE_ACKNOWLEDGE:
                            # Data write was successful; move on to the next data block
                            offset += len(data)
                            remaining_data_size -= len(data)

                            # Verify the data after the expected number of data blocks have been written
                            if last_write or verify_count >= self.verify_write_limit:
                                verify_command = bytearray(COMMAND_VERIFY_DATA, 'utf-8')
                                verify_data_block_size_bytes = struct.pack('<I', verify_data_block_size)
                                verify_checksum_bytes = struct.pack('<I', verify_checksum)
                                port_cmd_bytes = verify_command + verify_start_addr + verify_data_block_size_bytes + verify_checksum_bytes        # Need the full checksum here
                                response = self.write_to_comm(port_cmd_bytes, RESPONSE_ACKNOWLEDGE_SIZE)

                                if response.decode('utf-8') == RESPONSE_ACKNOWLEDGE:
                                    # Verification successful; reset for next verification
                                    verify_start_addr = struct.pack('<I', offset+baseaddr)
                                    verify_count = 1
                                    verify_checksum = 0
                                    verify_data_block_size = 0
                                else:
                                    # Verification failed; abort
                                    error = ERROR_WRITE_BLOCKS.format('Non-ack to verify command')
                                    break
                            else:
                                verify_count += 1
                                verify_checksum += checksum
                                verify_data_block_size += len(data)
                        else:
                            # Failed to write the data; abort
                            error = ERROR_WRITE_BLOCKS.format('Non-ack to data write')
                            break
                    else:
                        # Write command failed; abort
                        error = ERROR_WRITE_BLOCKS.format('Non-ack to write command')
                        break
                else:
                    self.write_complete = True
                if VERBOSELEVEL>=2:
                    print('.',end='\n',flush=True)
            else:
                error = ERROR_WRITE_BLOCKS.format('Data to write > bank size')
        else:
            error = ERROR_WRITE_BLOCKS.format('Erase command not yet processed')

        return error

    def process_command_unregister(self, file, data_length):
        if VERBOSELEVEL>=3:
            print(f"UNREGISTER_DEVICE")
        unregister_device_data = file.read(data_length)
        handle = struct.unpack('B', unregister_device_data[:UWF_OFFSET_HANDLE])[0]
        if VERBOSELEVEL>=2:
            print(f"Unregister Device: hndl={handle}")

        return None

    def reset_via_uartbreak(self,brk_timeout=0.1, post_delay=0.5):
        if VERBOSELEVEL>=2:
            print(f"Reseting via uart_break")
        self.ser.setDTR(False)
        self.ser.break_condition=True
        time.sleep(brk_timeout)
        self.ser.break_condition=False
        self.ser.setDTR(True)
        time.sleep(post_delay)
        return None
            
    def process_reboot(self):
        if VERBOSELEVEL>=2:
            print(f"Reboot")
        port_cmd_bytes = bytearray(COMMAND_REBOOT_BOOTLOADER, 'utf-8')
        self.ser.write(port_cmd_bytes)

        # Cleanup
        self.ser.close()
