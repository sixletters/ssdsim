# This file is part of the WAF-Simulator by Nicholas Fiorentini (2015)
# and is released under Creative Common Attribution 4.0 International (CC BY 4.0)
# see README.txt or LICENSE.txt for details

"""
This is the simplest Garbage Collector: it cleans the block with a minimum percentage of dirty pages and
only if a certain amount of time is passed after the last gc execution.
"""

# IMPORTS
from decimal import Decimal, getcontext
from simulator.NAND.GarbageCollectors.GarbageCollectorInterface import GarbageCollectorInterface
from simulator.NAND.common import check_block, DECIMAL_PRECISION, PAGE_IN_USE, PAGE_EMPTY


class GarbageCollectorSimple(GarbageCollectorInterface):
    """
    To be written ...
    """
    def __init__(self, mintime=500000, dirtiness='0.4', greedy=False):
        getcontext().prec = DECIMAL_PRECISION

        # ATTRIBUTES
        # PARAMETERS
        self.gc_param_mintime = mintime  # = 0.5 seconds (see simulation/simple_gc_test)
        """ Minimum time to wait before another run of the garbage collector.
            It's in microseconds (10^-6). Is an integer value. Must be greater or equal zero.
            If this value is zero then the gc is always executed.
        """

        self.gc_param_dirtiness = Decimal(dirtiness)  # 40 % (see simulation/simple_gc_test)
        """ Minimum percentage of dirty pages in a block to execute the garbage collector.
            It's a Decimal value and must be greater than 0 and maximum equal to 1.
            If it's equal to 1 then a block is cleaned only if all pages are dirty.
        """
        self.greedy = True

        # GARBAGE COLLECTOR INTERNAL STATE
        self._last_run = 0
        """ Last simulation time when the garbage collector was executed.
            It's in microseconds (10^-6). Is an integer value. Must match the simulation time dimension.
        """

        super().__init__()

    # METHODS
    def get_gc_name(self):
        return "simple ({}, {})".format(self.gc_param_mintime, self.gc_param_dirtiness)

    def check_gc_run(self, force_run=False):
        """

        :return:
        """
        # the gc is executed if it's elapsed enough time
        if self._elapsed_time - self._last_run >= self.gc_param_mintime:
            return True
        return False

    @check_block
    def check_gc_block(self, block=0, force_run=False):
        """
        :param block:
        :return:
        """
        # if the force is set, we need at least a dirty page in a block
        if force_run and self._ftl[block]['dirty'] > 0:
            return True

        # check the percentage of dirty pages of this block
        if Decimal(self._ftl[block]['dirty']) / Decimal(self.pages_per_block) >= self.gc_param_dirtiness:
            return True
        return False

    @check_block
    def execute_gc_block(self, block=0):
        """

        :param block:
        :return:
        """
        # STEP 1: temporary copy the block data
        #         this is a read and only useful data are read
        temp_block = dict()
        for p in range(0, self.pages_per_block):
            res, status = self.raw_read_page(block=block, page=p)
            if res:
                temp_block[p] = PAGE_IN_USE  # the page is valid and in use
            else:
                temp_block[p] = PAGE_EMPTY  # reset the page, even if is dirty

        # STEP 2: erase
        self.raw_erase_block(block=block)

        # STEP 3: write the IN USE pages only
        for p in range(0, self.pages_per_block):
            if temp_block[p] == PAGE_IN_USE:
                self.raw_write_page(block=block, page=p)

        return True
