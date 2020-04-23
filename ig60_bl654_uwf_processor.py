import dbus
from uwf_processor import UwfProcessor
from uwf_processor import ERROR_REGISTER_DEVICE

BT_BOOTLOADER_MODE = 0
BT_SMART_BASIC_MODE = 1

class Ig60Bl654UwfProcessor(UwfProcessor):
	"""
	Class that encapsulates how to process UWF commands for an IG60
	BL654 module upgrade
	"""

	def __init__(self, port, baudrate):
		UwfProcessor.__init__(self, port, baudrate)

		# Setup the DBus connection to the device service
		self.bus = dbus.SystemBus()
		self.device_svc = dbus.Interface(self.bus.get_object('com.lairdtech.device.DeviceService',
			'/com/lairdtech/device/DeviceService'), 'com.lairdtech.device.public.DeviceInterface')

		# Expected registration values for an IG60 BL654
		self.expected_handle = 0
		self.expected_num_banks = 1
		self.expected_bank_algo = 1

	def enter_bootloader(self):
		success = False

		# Enter the bootloader via the Device Service
		if self.device_svc.SetBtBootMode(BT_BOOTLOADER_MODE) != 0:
			raise Exception('Failed to enter bootloader via smartBASIC and DBus')
		else:
			success = True

			# Clear the serial line before starting
			self.ser.readline()

		return success

	def process_command_register_device(self, file, data_length):
		error = None

		UwfProcessor.process_command_register_device(self, file, data_length)

		# Validate the registration data
		if self.handle == self.expected_handle and self.num_banks == self.expected_num_banks and self.bank_size > 0 and self.bank_algo == self.expected_bank_algo:
			self.registered = True
		else:
			error = ERROR_REGISTER_DEVICE.format('Unexpected registration data')
			self.registered = False

		return error

	def process_reboot(self):
		# Use the device service to return the bt_boot_mode to smartBASIC
		self.device_svc.SetBtBootMode(BT_SMART_BASIC_MODE)

		# Cleanup
		self.ser.close()