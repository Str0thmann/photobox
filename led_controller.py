
import board
import neopixel
import time


pixels = neopixel.NeoPixel(board.D18, 24)

#pixels[0] = (255, 255, 255)
#pixels.show()

#pixels.fill((255, 255, 255))

#time.sleep(1)

pixels.fill((0,0,0))



#pixels[1] = (255,255,255)
#pixels[2] = (255,255,255)

#time.sleep(1)

pixels.fill((0,0,0))

startindex = 1
endindex = 23
pixelsC = 24

ORDER = neopixel.GRB

for i in range(10, 0, -1):

    if False and startindex != 6 and startindex !=12 and endindex != 18 and endindex != 24:
        pixels[startindex] = (255,255,255)
        pixels[endindex] = (255,255,255)
        time.sleep(1)
    startindex += 1
    endindex -= 1
    #time.sleep(1)

pixels.fill((0,0,0))

def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        r = g = b = 0
    elif pos < 85:
        r = int(pos * 3)
        g = int(255 - pos*3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos*3)
        g = 0
        b = int(pos*3)
    else:
        pos -= 170
        r = 0
        g = int(pos*3)
        b = int(255 - pos*3)
    return (r, g, b) if ORDER == neopixel.RGB or ORDER == neopixel.GRB else (r, g, b, 0)
 
 
def rainbow_cycle(wait):
    r = 0
    g = 0
    b = 0
    steps = 20
    reverse = False
    mini = 30
    for j in range(10):
        for i in range(pixelsC):
            pixels[i] = (r, g, b)
            if not reverse:

                if r < 255:
                    r += steps
                    if r > 255:
                        r = 255
                elif g < 255:
                    g += steps
                    if g > 255:
                        g = 255
                elif b < 255:
                    b += steps
                    if b > 255:
                        b = 255
                        reverse = True
            else:
               if r > mini:
                   r -= steps
                   if r < mini:
                       r = mini
               elif g > mini:
                   g -= steps
                   if g < mini:
                       g = mini
               elif b > mini:
                   b -= steps
                   if b < mini:
                       b = mini
                       reverse = False

            time.sleep(wait)

rainbow_cycle(0.03)

pixels.fill((0,0,0)) 
 
