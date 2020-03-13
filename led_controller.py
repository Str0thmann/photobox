
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

def sub(sys, val):
    if val > 2*sys+1:
        return val - (2*sys+1)
    elif val > sys:
        return val-sys
    elif val < 0:
        return val + sys+1
    else:
        return val

def smile(wait):
    bright = 200
    pixels[3] = (0,0,bright)
    pixels[21] = (0,0,bright)
    tmp = 11
    for j in range(4):
        for i in range(3+2*j):
            pixels[i+tmp] = (bright,bright,bright)
        time.sleep(wait)
        tmp = tmp - 1
    time.sleep(wait)
    pixels[3] = (0,0,0)
    pixels[21] = (0,0,0)
    time.sleep(0.7*wait)
    pixels[3] = (0,0,bright)
    pixels[21] = (0,0,bright)
    time.sleep(2*wait)
    pixels[3] = (0,0,0)
    pixels[21] = (0,0,0)
    time.sleep(0.7*wait)
    pixels[3] = (0,0,bright)
    pixels[21] = (0,0,bright)
    time.sleep(2*wait)

def wheelRed(wait):
    for i in range(23):
        for j in range(23):
            k = int(255/(j**2+1))
            pixels[sub(23,i-j)] = (k,0,0)
        time.sleep(wait)
        
def wheel3(wait):
    bright = 200  # zwischen 0 und 255
    fade = 1.2  #zwischen 1 und 3
    for i in range(23):
        for j in range(23):
            k1 = int(bright/(j**fade+1))
            k2 = int(bright/((j+16)**fade+1))
            k3 = int(bright/((j+8)**fade+1))
            if j > 7:
                k2 = int(bright/((j-8)**fade+1))
            if j > 15:
                k3 = int(bright/((j-16)**fade+1))
            pixels[sub(23,i-j)] = (k1,k2,k3)
            pixels.brightness = 0.2
        time.sleep(wait)

def wheel4(wait):
    pixels.fill((0,0,0))
    for i in range(5):
        k = int(255/(i**2+1))
        pixels[0+i] = (255,0,0)
        for j in range(i):
            pixels[0+j] = ((j+1)*k,0,0)
        pixels[6+i] = (0,255,0)
        for j in range(i):
            pixels[6+j] = (0,(j+1)*k,0)
        pixels[12+i] = (0,0,255)
        for j in range(i):
            pixels[12+j] = (0,0,(j+1)*k)
        pixels[18+i] = (0,0,255)
        for j in range(i):
            pixels[18+j] = ((j+1)*k,0,(j+1)*k)
        time.sleep(wait)

 
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

#rainbow_cycle(0.03)
#wheel4(0.6)
#wheelRed(0.3)
#wheel3(0.2)
#smile(0.3)


pixels.fill((0,0,0)) 
