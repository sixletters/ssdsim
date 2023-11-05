# This file is part of the WAF-Simulator by Nicholas Fiorentini (2015)
# and is released under Creative Common Attribution 4.0 International (CC BY 4.0)
# see README.txt or LICENSE.txt for details

"""
This is the Abstract class interface for all Garbage Collector implementations.
"""

# IMPORTS
from abc import ABCMeta, abstractclassmethod
from simulator.NAND.NANDInterface import NANDInterface
from simulator.NAND.common import check_block, DECIMAL_PRECISION, PAGE_IN_USE, PAGE_EMPTY, PAGE_DIRTY


class GarbageCollectorInterface(NANDInterface, metaclass=ABCMeta):
    """
    To be written ...
    """
    # METHODS
    @abstractclassmethod
    def check_gc_run(self, force_run=False):
        return NotImplemented

    @abstractclassmethod
    def check_gc_block(self, block=0, force_run=False):
        return NotImplemented

    @abstractclassmethod
    def execute_gc_block(self, block=0):
        return NotImplemented

    @abstractclassmethod
    def get_gc_name(self):
        return NotImplemented

    def run_gc(self, force_run=False, run_once=False):
        """

        :return:
        """
        # check the overall conditions to execute the gc
        if run_once:
            max_invalid = 0
            max_invalid_block = 0
            for b in range(0, self.total_blocks):
            # check the conditions on this block
                invalid_count = 0
                for page in self._ftl[b]:
                    if page == PAGE_DIRTY:
                        invalid_count += 1

                if invalid_count > max_invalid:
                    max_invalid = invalid_count
                    max_invalid_block = b
            return max_invalid_block

        if self.check_gc_run(force_run=force_run):
            # run the gc on every block
            execution = False
            for b in range(0, self.total_blocks):
                # check the conditions on this block
                if self.check_gc_block(block=b, force_run=force_run):
                    # ok, run it
                    res = self.execute_gc_block(block=b)
                    if not execution and res:
                        # ok, the gc was executed on at least one block
                        execution = True

            return execution

        # gc not executed
        return False
