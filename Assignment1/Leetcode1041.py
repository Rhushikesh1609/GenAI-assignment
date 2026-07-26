class Solution(object):
    def isRobotBounded(self, instructions):
        """
        :type instructions: str
        :rtype: bool
        """
        #start position
        x,y = 0,0
        
        #dx,dy is change in x and y
        dx,dy = 0,1

        for instruction in instructions:
            if instruction == 'G':
                #Move straight 1 unit
                x += dx
                y += dy
            elif instruction == 'L':
                #Turn 90 degree anti-clockwise
                dx,dy = -dy,dx
            elif instruction == 'R':
                #Turn 90 degree clockwise
                dx,dy = dy,-dx

        return (x == 0 and y == 0) or (dx != 0 or dy != 1)
