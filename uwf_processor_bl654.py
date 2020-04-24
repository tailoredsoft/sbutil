from uwf_processor import UwfProcessor

class UwfProcessorBl654(UwfProcessor):
    """
    Class that encapsulates how to process UWF commands for an IG60
    BL654 module upgrade
    """

    def __init__(self, port, baudrate):
        UwfProcessor.__init__(self, port, baudrate)

        # Expected registration values for an BL654
        self.expected_handle = 0
        self.expected_num_banks = 1
        self.expected_bank_algo = 1

    def enter_bootloader(self):
        return UwfProcessor.enter_bootloader(self)

    def process_reboot(self):
        self.reset_via_uartbreak()
        self.ser.close()
