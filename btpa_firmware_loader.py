#!/usr/bin/python3
import sys
import errno
import serial
import struct
import uwf_processor

SERIAL_TIMEOUT = 1

EXIT_CODE_SUCCESS = 0

UWF_READ_SUCCESS = 1
UWF_READ_DONE = 0
UWF_COMMAND_HEADER_LENGTH = 6
UWF_TARGET_PLATFORM_LENGTH = 4
UWF_REGISTER_DEVICE_LENGTH = 11
UWF_SELECT_DEVICE_LENGTH = 2
UWF_SECTOR_MAP_LENGTH = 8
UWF_ERASE_BLOCK_LENGTH = 8
UWF_WRITE_BLOCK_LENGTH = 8
UWF_UNREGISTER_DEVICE_LENGTH = 1

UWF_OFFSET_HEADER_COMMAND_ID = 1
UWF_OFFSET_HEADER_LENGTH_START = 2
UWF_OFFSET_HEADER_LENGTH_END = 6

UWF_COMMAND_TARGET_PLATFORM = 'T'
UWF_COMMAND_REGISTER = 'G'
UWF_COMMAND_SELECT = 'S'
UWF_COMMAND_SECTOR_MAP = 'M'
UWF_COMMAND_ERASE = 'E'
UWF_COMMAND_WRITE = 'W'
UWF_COMMAND_UNREGISTER = 'U'

exit_code = EXIT_CODE_SUCCESS	# Success (for now)
if len(sys.argv) >= 4:
	port = sys.argv[1]
	baudrate = int(sys.argv[2])
	file_path = sys.argv[3]

	if len(sys.argv) == 5:
		type = sys.argv[4]
	else:
		type = None

	try:
		# Open the UWF file
		f = open(file_path,'rb')
	except IOError as i:
		# Failed to open the file
		sys.stderr.write('{}\n'.format(i))
		exit_code = errno.ENOENT
	else:
		if f.mode == 'rb':
			# Initialize the processor
			try:
				processor = uwf_processor.init_processor(type, port, baudrate)
				status = UWF_READ_SUCCESS
				while (status == UWF_READ_SUCCESS):
					# Read the next section (in bytes)
					bytes = f.read(UWF_COMMAND_HEADER_LENGTH)
					if bytes:
						cmd = bytes[:UWF_OFFSET_HEADER_COMMAND_ID].decode('utf-8')
						data_length = struct.unpack('<I', bytes[UWF_OFFSET_HEADER_LENGTH_START:UWF_OFFSET_HEADER_LENGTH_END])[0]

						if cmd == UWF_COMMAND_TARGET_PLATFORM and data_length == UWF_TARGET_PLATFORM_LENGTH:
							error = processor.process_command_target_platform(f, data_length)
						elif cmd == UWF_COMMAND_REGISTER and data_length == UWF_REGISTER_DEVICE_LENGTH:
							error = processor.process_command_register_device(f, data_length)
						elif cmd == UWF_COMMAND_SELECT and data_length == UWF_SELECT_DEVICE_LENGTH:
							error = processor.process_command_select_device(f, data_length)
						elif cmd == UWF_COMMAND_SECTOR_MAP and data_length == UWF_SECTOR_MAP_LENGTH:
							error = processor.process_command_sector_map(f, data_length)
						elif cmd == UWF_COMMAND_ERASE and data_length == UWF_ERASE_BLOCK_LENGTH:
							error = processor.process_command_erase_blocks(f, data_length)
						elif cmd == UWF_COMMAND_WRITE and data_length >= UWF_WRITE_BLOCK_LENGTH:
							error = processor.process_command_write_blocks(f, data_length)
						elif cmd == UWF_COMMAND_UNREGISTER and data_length == UWF_UNREGISTER_DEVICE_LENGTH:
							error = processor.process_command_unregister(f, data_length)
						else:
							# Unknown command; read to the next section and continue
							f.read(data_length)
							status = UWF_READ_SUCCESS

						if error != None:
							processor.process_reboot()
							status = UWF_READ_DONE
							sys.stderr.write(error)
							exit_code = errno.EPERM
					else:
						# Reached the end of the file
						processor.process_reboot()
						status = UWF_READ_DONE
			except serial.SerialException as s:
				sys.stderr.write('{}\n'.format(s))
				exit_code = errno.ENETUNREACH
			except Exception as e:
				sys.stderr.write('{}\n'.format(e))
				exit_code = errno.EPERM
		# Close the local file
		f.close()
else:
	print('usage: btpa_firmware_loader <port> <baudrate> <path to UWF file> [device type]\n')
	exit_code = errno.EINVAL

sys.exit(exit_code)
