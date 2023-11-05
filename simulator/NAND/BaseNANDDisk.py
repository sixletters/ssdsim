# This file is part of the WAF-Simulator by Nicholas Fiorentini (2015)
# and is released under Creative Common Attribution 4.0 International (CC BY 4.0)
# see README.txt or LICENSE.txt for details

"""
This is the base class to handle a single NAND cell in a very naive and basic implementation.
"""

# IMPORTS
from decimal import Decimal, getcontext
from simulator.NAND.NANDInterface import NANDInterface
from simulator.NAND.common import PAGE_EMPTY, PAGE_IN_USE, PAGE_DIRTY, DECIMAL_PRECISION, bytes_to_mib, pages_to_mib, \
    OPERATION_SUCCESS, OPERATION_FAILED_DIRTY, OPERATION_FAILED_DISKFULL
from simulator.NAND.common import get_quantized_decimal as qd, check_block, check_page
from simulator.NAND.common import get_integer_decimal as qz
from math import sqrt

# BaseNANDDISK class
class BaseNANDDisk(NANDInterface):
    """
    This class ...
    """

    # CONSTRUCTOR
    def __init__(self, total_blocks=256, pages_per_block=128, page_size=4096,
                 write_page_time=40, read_page_time=20, erase_block_time=1500):
        """

        :return:
        """
        super().__init__()

        # ATTRIBUTES
        # PHYSICAL CHARACTERISTICS
        self.total_blocks = total_blocks
        """ The total physical number of block available. Usually should be a multiple of 2.
            This is an integer value. Must be greater than zero.
        """

        self.pages_per_block = pages_per_block
        """ The number of pages per single block. Usually should be a multiple of 2.
            This is an integer value. Must be greater than zero.
        """

        self.page_size = page_size
        """ The physical size of a single page in [Bytes].
            This is an integer value. Must be greater than zero.
        """

        self.total_pages = self.pages_per_block * self.total_blocks
        """ The total physical number of pages available.
            This is an integer value. Must be greater than zero.
        """

        self.block_size = self.page_size * self.pages_per_block
        """ The physical size of a single block in [Bytes].
            It's computed as the number of pages per block times the size of a page.
            This is an integer value. Must be greater than zero.
        """

        self.total_disk_size = self.total_pages * self.page_size
        """ The total physical size of this NAND cell in [Bytes].
            It's computed as the number of total physical blocks times the size of a block.
            This is an integer value. Must be greater than zero.
        """

        self.write_page_time = write_page_time
        """ The time to write a single page in [microseconds] (10^-6 seconds).
            This is an integer value. Must be greater than zero.
        """

        self.read_page_time = read_page_time
        """ The time to read a single page in [microseconds] (10^-6 seconds).
            This is an integer value. Must be greater than zero.
        """

        self.erase_block_time = erase_block_time
        """ The time to erase a single block in [microseconds] (10^-6 seconds).
            This is an integer value. Must be greater than zero.
        """

        # INTERNAL STATISTICS
        self._elapsed_time = 0
        """ Keep track of the total elapsed time for the requested operations [microseconds].
            A microsecond is 10^-6 seconds. This variable is an integer.
        """

        self._host_page_write_request = 0
        """ Number of page written as requested by the host.
            This is an integer value.
        """

        self._page_write_executed = 0
        """ Total number of page actually written by the disk.
            This is an integer value.
        """

        self._page_write_failed = 0
        """ Total number of page unable to be writted due to disk error (no empty pages).
            This is an integer value.
        """

        self._host_page_read_request = 0
        """ Number of page read as requested by the host.
            This is an integer value.
        """

        self._page_read_executed = 0
        """ Total number of page actually read by the disk.
            This is an integer value.
        """

        self._block_erase_executed = 0
        """ Total number of block erase executed.
            This is an integer value.
        """

        self._gc_forced_count = 0
        """ Total number of times the gc was forced to clean dirty pages.
            This is an integer value.
        """

        # INTERNAL STATE
        self._ftl = dict()
        """ This is the full state of the flash memory.
            It's an array of blocks. Every block is an array of page.
            For every page we keep the status of the page.
            Furthermore, every block has the following extra information:
                empty:  total number of empty pages in the given block;
                dirty:  total number of dirty pages in the given block.
        """

        # INTERNAL STATE
        self._death_times = dict()
        """ This is the death times of the pages.
            It's an array of blocks. Every block has an array of death times, representing the deathtime of a page.
        """

        # set the decimal context
        getcontext().prec = DECIMAL_PRECISION

        # initialize the FTL
        for b in range(0, self.total_blocks):
            # for every block initialize the page structure
            self._ftl[b] = dict()
            self._death_times[b] = [-1 for i in range(self.pages_per_block)]
            for p in range(0, self.pages_per_block):
                # for every page set the empty status
                self._ftl[b][p] = PAGE_EMPTY

            # for every block initialize the internal data
            self._ftl[b]['empty'] = self.pages_per_block  # all pages are empty
            self._ftl[b]['dirty'] = 0  # no dirty pages at the beginning

    # METHODS
    # PYTHON UTILITIES
    def __str__(self):
        """

        :return:
        """
        return "WP: {}\t\tGC: {}\n" \
               "{} pages per block, {} blocks, {} pages of {} [Bytes]. Capacity {} [MiB]\n" \
               "Max bandwidth read: {}\t write: {} [MiB\s] (theoretical)\n" \
               "Dirty: {}\{} ([pages]\[MiB])\n" \
               "Empty: {}\{} ([pages]\[MiB])\n" \
               "In Use: {}\{} ([pages]\[MiB])\n" \
               "Host read: {}\{}, write: {}\{} ([pages]\[MiB])\n" \
               "Disk read: {}\{}, write: {}\{} ([pages]\[MiB])\n" \
               "Erased blocks: {}\{} ([blocks]\[MiB])\n" \
               "Failures: {} % ({} [pages], {} [MiB])\n" \
               "GC Forced count: {}\n" \
               "Time: {} [s]\t IOPS: {}\t Bandwidth: {} [MiB\s]\n" \
               "Write Amplification: {}\n" \
               "".format(self.get_write_policy_name(), self.get_gc_name(),
                         self.pages_per_block, self.total_blocks, self.total_pages, self.page_size,
                         qd(bytes_to_mib(self.total_disk_size)),
                         qd(bytes_to_mib(Decimal(10 ** 6 / self.read_page_time)) * self.page_size),
                         qd(bytes_to_mib(Decimal(10 ** 6 / self.write_page_time)) * self.page_size),
                         self.number_of_dirty_pages(),
                         qd(pages_to_mib(self.number_of_dirty_pages(), self.page_size)),
                         self.number_of_empty_pages(),
                         qd(pages_to_mib(self.number_of_empty_pages(), self.page_size)),
                         self.number_of_in_use_pages(),
                         qd(pages_to_mib(self.number_of_in_use_pages(), self.page_size)),
                         self._host_page_read_request,
                         qd(pages_to_mib(self._host_page_read_request, self.page_size)),
                         self._host_page_write_request,
                         qd(pages_to_mib(self._host_page_write_request, self.page_size)),
                         self._page_read_executed,
                         qd(pages_to_mib(self._page_read_executed, self.page_size)),
                         self._page_write_executed,
                         qd(pages_to_mib(self._page_write_executed, self.page_size)),
                         self._block_erase_executed,
                         qd(bytes_to_mib(self._block_erase_executed * self.block_size)),
                         qd(self.failure_rate()), self._page_write_failed,
                         qd(pages_to_mib(self._page_write_failed, self.page_size)),
                         self._gc_forced_count,
                         qd(self.elapsed_time_seconds()), qz(self.IOPS()), qd(self.bandwidth_host()),
                         qd(self.write_amplification()))

    # STATISTICAL UTILITIES
    def write_amplification(self):
        """

        :return:
        """
        # avoid divide by zero errors
        if self._host_page_write_request <= 0:
            return Decimal('0')

        return Decimal(self._page_write_executed) / Decimal(self._host_page_write_request)

    def number_of_empty_pages(self):
        """

        :return:
        """
        tot = 0
        for b in range(0, self.total_blocks):
            tot += self._ftl[b]['empty']
        return tot

    def number_of_dirty_pages(self):
        """

        :return:
        """
        tot = 0
        for b in range(0, self.total_blocks):
            tot += self._ftl[b]['dirty']
        return tot

    def number_of_in_use_pages(self):
        """

        :return:
        """
        return self.total_pages - (self.number_of_empty_pages() + self.number_of_dirty_pages())

    def failure_rate(self):
        """

        :return:
        """
        # avoid divide by zero errors
        if self._page_write_executed <= 0:
            return Decimal('0')

        return Decimal(self._page_write_failed * 100) / Decimal(self._page_write_executed)

    def elapsed_time(self):
        """

        :return:
        """
        return self._elapsed_time

    def elapsed_time_seconds(self):
        """

        :return:
        """
        return Decimal(self._elapsed_time) / Decimal(10 ** 6)

    def IOPS(self):
        """

        :return:
        """
        # avoid divide by zero errors
        if self._elapsed_time <= 0:
            return Decimal('0')

        ops = self._page_write_executed + self._page_read_executed
        return Decimal(ops) / self.elapsed_time_seconds()

    def bandwidth_host(self):
        """

        :return:
        """
        # avoid divide by zero errors
        if self._elapsed_time <= 0:
            return Decimal('0')

        # in MiB
        return pages_to_mib((self._host_page_write_request + self._host_page_read_request),
                            self.page_size) / Decimal(self.elapsed_time_seconds())

    def get_stats(self):
        """

        :return:
        """
        return self._elapsed_time, qz(self.IOPS()), qd(self.bandwidth_host()), \
            qd(self.write_amplification()), self._host_page_write_request, self._host_page_read_request, \
            self._page_write_executed, self._page_read_executed, self._block_erase_executed,\
            self._page_write_failed, self.number_of_dirty_pages()

    # DISK OPERATIONS UTILITIES
    def is_write_failing(self):
        """

        :return:
        """
        return self._page_write_failed > 0

    @check_block
    def get_empty_page(self, block=0):
        """

        :param block:
        :return:
        """
        # first check availability
        if self._ftl[block]['empty'] <= 0:
            raise ValueError("No empty pages available in this block.")

        # get the first empty page available in the provided block
        for p in range(0, self.pages_per_block):
            if self._ftl[block][p] == PAGE_EMPTY:
                return p

        # should not be reachable
        raise ValueError("No empty pages available in this block.")

    def get_empty_block(self):
        """

        :return:
        """
        # get the first empty block available
        for b in range(0, self.total_blocks):
            if self._ftl[b]['empty'] == self.pages_per_block:
                return True, b

        # should not be reachable
        return False, 0

    # RAW DISK OPERATIONS
    @check_block
    @check_page
    def raw_write_page(self, block=0, page=0, death_time=-1):
        """

        :param block:
        :param page:
        :return: True if the write is successful, false otherwise (the write is discarded)
        """
        # read the FTL to check the current status
        s = self._ftl[block][page]

        # if status is EMPTY => WRITE OK
        if s == PAGE_EMPTY:
            # change the status of this page
            self._ftl[block][page] = PAGE_IN_USE
            # update the death time if it is ok
            self._death_times[block][page] = death_time

            # we need to update the statistics
            self._ftl[block]['empty'] -= 1  # we lost one empty page in this block
            self._elapsed_time += self.write_page_time  # time spent to write the data
            self._page_write_executed += 1  # one page written
            return True, OPERATION_SUCCESS

        # if status is IN USE => we consider a data change,
        # we use the current disk policy to find a new page to write the new data. In case of success we invalidate
        # the current page, otherwise the operation fails.
        if s == PAGE_IN_USE:
            # is the block full?
            if self._ftl[block]['empty'] <= 0:
                # yes, we need a policy to decide how to write
                if self.full_block_write_policy(block=block, page=page):
                    # all statistic MUST BE updated inside the policy method
                    return True, OPERATION_SUCCESS
                else:
                    # we didn't found a suitable place to write the new data, the write request failed
                    # this is a disk error: the garbage collector was unable to make room for new data
                    self._page_write_failed += 1
                    return False, OPERATION_FAILED_DISKFULL
            else:
                # no, we still have space, we just need a new empty page on this block
                # find and write the new page
                newpage = self.get_empty_page(block=block)

                # change the status of this page
                self._ftl[block][page] = PAGE_DIRTY

                # change the status of the new page
                self._ftl[block][newpage] = PAGE_IN_USE

                # we need to update the statistics
                self._ftl[block]['empty'] -= 1  # we lost one empty page in this block
                self._ftl[block]['dirty'] += 1  # we have one more dirty page in this block
                self._elapsed_time += self.write_page_time  # time spent to write the data
                self._page_write_executed += 1  # one page written
                return True, OPERATION_SUCCESS

        # if status is DIRTY => we discard this write operation
        # (it's not a disk error, it's a bad random value)
        return False, OPERATION_FAILED_DIRTY

    @check_block
    @check_page
    def raw_read_page(self, block=0, page=0):
        """

        :param block:
        :param page:
        :return:
        """
        # read the FTL to check the current status
        s = self._ftl[block][page]

        if s == PAGE_IN_USE:
            # update statistics
            self._elapsed_time += self.read_page_time  # time spent to read the data
            self._page_read_executed += 1  # we executed a read of a page
            return True, OPERATION_SUCCESS

        # no valid data to read
        return False, OPERATION_FAILED_DIRTY  # always fail to dirty read (empty or dirty page)

    @check_block
    def raw_erase_block(self, block=0):
        """

        :param block:
        :return:
        """
        # should mark the full block as dirty and then erase it
        # as we are in a simulation, we directly erase it
        for p in range(0, self.pages_per_block):
            # for every page set the empty status
            self._ftl[block][p] = PAGE_EMPTY

        # for every block initialize the internal data
        self._ftl[block]['empty'] = self.pages_per_block  # all pages are empty
        self._ftl[block]['dirty'] = 0  # fresh as new

        # update the statistics
        self._block_erase_executed += 1  # new erase operation
        self._elapsed_time += self.erase_block_time  # time spent to erase a block
        return True

    @check_block
    @check_page
    def host_write_page(self, block=0, page=0, death_time=-1, gc_was_forced=False, run_gc_once=False):
        """

        :param block:
        :param page:
        :return:
        """
        # check if we need to run the garbage collector
        self.run_gc(force_run=gc_was_forced, run_once=run_gc_once)
        
        # execute the write
        res, status = self.raw_write_page(block=block, page=page, death_time=death_time)
        if res:
            # update statistics
            self._host_page_write_request += 1  # the host actually asked to write a page
        elif not gc_was_forced and status == OPERATION_FAILED_DISKFULL:
            # if we had a failure, we try it again
            self._page_write_failed -= 1

            # force a gc run and retry
            self._gc_forced_count += 1
            return self.host_write_page(block=block, page=page, death_time=death_time, gc_was_forced=True)

        return res, status
    
    @check_block
    @check_page
    def host_deathtime_page_write(self, block=0, page=0, death_time=-1, gc_was_forced=False):
        """
        We inject our deathtime logic plug in here. Instead of writing to the given block and page, we first check
        if it the block/page is clean, if it is, this means that it is a fresh write and not an update. This means, we can simply, replace with
        a block/page that has the most similiar death time
        """
        # read the FTL to check the current status
        s = self._ftl[block][page]

        # fresh write
        if s == PAGE_EMPTY:
            optimized_block, optimized_page = self.get_min_deathtime_block(block=block, page=page, death_time=death_time)
            res, status = self.raw_write_page(block=block, page=page, death_time=death_time)
            if res:
                # update statistics
                self._host_page_write_request += 1  # the host actually asked to write a page
            return res, status
        # an update, let write policy and GC handle it
        else:
            return self.host_write_page(block=0, page=0, death_time=-1, gc_was_forced=False, run_gc_once=True)
    
    @check_block
    @check_page
    def get_min_deathtime_block(self, block=0, page=0, death_time=-1):
        """
        This function returns the block with the most similiar death time. We calculate this as the Root mean square
        between the current write's death time and all valid page's death time in a block
        """
        if death_time == -1:
            return (block, page)
        
        min_deathtime_block =block
        # maximum deathtime possble
        mean_root_square = self.total_blocks
        for block in self._ftl:
            block_score = self.get_deathtime_score_for_block(block=block, death_time=death_time)
            if mean_root_square > block_score:
                mean_root_square = block_score
                min_deathtime_block = block
        return min_deathtime_block, self.get_empty_page(block=min_deathtime_block)
            
    @check_block
    @check_page
    def get_deathtime_score_for_block(self, block=0, death_time=-1):
        mean_root_square = 0
        n = 0
        for page in self._ftl[block]:
            if page == PAGE_EMPTY:
                continue
            mean_root_square += (self._death_times[block][page] - death_time) ** 2
            n += 1
        # block is completely empty, return squareroot
        if n == 0:
            return sqrt(self._ftl[block])
        return sqrt(mean_root_square / n)
        
    @check_block
    @check_page
    def host_read_page(self, block=0, page=0):
        """

        :param block:
        :param page:
        :return:
        """
        # check if we need to run the garbage collector
        self.run_gc()

        # execute the write
        res, status = self.raw_read_page(block=block, page=page)
        if res:
            # update statistics
            self._host_page_read_request += 1  # the host actually asked to read a page

        return res, status
