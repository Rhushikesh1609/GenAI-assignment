#Given two non-negative integers num1 and num2 represented 
#as strings, return the product of num1 and num2, 
#also represented as a string.


class Solution(object):
    def multiply(self, num1, num2):
        """
        :type num1: str
        :type num2: str
        :rtype: str
        """
        if num1 == '0' or num2 == '0':
            return '0'

        m,n = len(num1), len(num2)
        result = [0] * (m + n)

        for i in range (m - 1, -1, -1):
            for j in range (n -1, -1, -1):
                mul = int(num1[i]) * int(num2[j])

                p1,p2 = i + j, i + j + 1

                total = mul + result[p2]

                result[p2] = total % 10
                result[p1] += total // 10

        start_idx = 0
        while start_idx < len(result) and result[start_idx] == 0:
            start_idx += 1

        return "".join(map(str, result[start_idx:]))
        