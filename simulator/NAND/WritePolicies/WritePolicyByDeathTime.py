# This file is an exetension by harris maung.

"""
This is an improved policy for writes by death time, we choose the block with the most similar
death times as current page as the next candidate. We will chose a block
"""

# IMPORTS
from simulator.NAND.WritePolicies.WritePolicyDefault import WritePolicyInterface
from simulator.NAND.common import check_block, check_page, PAGE_EMPTY, PAGE_DIRTY, PAGE_IN_USE


class WritePolicyByDeathTime(WritePolicyInterface):
    def get_write_policy_name(self):
        return "death time"
    
    @check_block
    @check_page
    def full_block_write_policy(self, block=0, page=0):
        return "HELLO"