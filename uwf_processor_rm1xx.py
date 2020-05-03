from uwf_processor import UwfProcessor

class UwfProcessorRM1XX(UwfProcessor):
    """
    Class that encapsulates how to process UWF commands for RM1XX module upgrade
    """

    def __init__(self, port, baudrate):
        UwfProcessor.__init__(self, port, baudrate)

        # Expected registration values for an RM1XX
        self.expected_handle = 0
        self.expected_num_banks = 1
        self.expected_bank_algo = 1

    def enter_bootloader(self):
        self.reset_via_uartbreak(post_delay=2.0)
        return UwfProcessor.enter_bootloader(self)

    def process_reboot(self):
        self.reset_via_uartbreak(post_delay=2.0)
        self.ser.close()
