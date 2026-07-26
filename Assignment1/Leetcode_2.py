#You are given two non-empty linked lists representing two 
#non-negative integers. The digits are stored in reverse order, 
#and each of their nodes contains a single digit. 
#Add the two numbers and return the sum as a linked list.



# Definition for singly-linked list.
# class ListNode(object):
#     def __init__(self, val=0, next=None):
#         self.val = val
#         self.next = next
class Solution(object):
    def addTwoNumbers(self, l1, l2):
        """
        :type l1: Optional[ListNode]
        :type l2: Optional[ListNode]
        :rtype: Optional[ListNode]
        """
        dummy_head = ListNode(0)
        current = dummy_head
        carry = 0

        while l1 is not None or l2 is not None or carry != 0:
            #Extract values from nodes using 0 if the list has ended
            val1 = l1.val if l1 is not None else 0
            val2 = l2.val if l2 is not None else 0

            #Calculate sum and the new carry
            total_sum = val1 + val2 + carry
            carry = total_sum // 10
            new_digit = total_sum % 10

            #Create a node with single digit and attach it
            current.next = ListNode(new_digit)
            current = current.next

            #Move pointers forward if possible
            if l1 is not None:
                l1 = l1.next
            if l2 is not None:
                l2 = l2.next

        return dummy_head.next