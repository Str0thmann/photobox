from threading import Thread
import os
import time
import subprocess
import hashlib
import random
import atexit
import board
import neopixel
from gpiozero import Button

# Config files

imageDir = "/home/pi/"

imageFileType = ".jpg"

# captureButton = Button(4)
# abortButton = Button()
# saveButton = Button()

ledNumbers = 12
lightSteps = 40

pixels = neopixel.NeoPixel(board.D18, ledNumbers)


# Path to the transparent PNG's
# the counter Number need to be at the end
# myFile5.png myFile4.png ....
counterPath = "/home/pi/photoBox/counter/counterWhite/"


# TODO pngview check einbauen


ledController = None




def exit_handler():
	print ('My application is ending!')
	setAllLedsOFF()

class ledControl(Thread):
    def __init__(self):
        Thread.__init__(self)

        #self.color = [white[255, 255, 255], red[255, 0, 0]]
        self.ledControlActive = False


    def run(self):
        red = 255
        green = 255
        blue = 255
        self.ledControlActive = True
        reverse = False

        while self.ledControlActive:
            for j in range(ledNumbers):
                try:
                    pixels[j] = (red, green, blue)
                except:
                    print(red, green, blue)

                if(not self.ledControlActive):
                    break
                elif (red >= 30 and not reverse):
                    red -= lightSteps
                elif (green >= 30 and not reverse):
                    green -= lightSteps
                elif (blue >= 30 and not reverse):
                    blue -= lightSteps
                elif (red < 255):
                    red += lightSteps
                    reverse = True
                elif (green < 255):
                    green += lightSteps
                elif (blue < 255):
                    blue += lightSteps
                    if (blue == 255):
                        reverse = False

                time.sleep(0.1)


    def stop(self):
        self.ledControlActive =  False
        time.sleep(0.3)
        setAllLedsOFF()

class holtCamera(Thread):
    def __init__(self):
        Thread.__init__(self)

        self.lastTimeActive = time.time()
        self.holtCameraTimer = 15

        Thread.setName(self, "holtCamera")
        print("Create " + Thread.getName(self))

    def run(self):
        self.update()
        while True:
            time.sleep(self.holtCameraTimer)
            if (self.lastTimeActive + self.holtCameraTimer < time.time()):
                # TODO stop Camera function
                # TODO maybe start screenSave Thread
                break

    def update(self):
        self.lastTimeActive = time.time()

def setLedDefault():
    pixels[0] = (255, 255, 255)
    pixels[11] = (255, 255, 255)


def setLedWhite(ledNumber):
    pixels[ledNumber-1] = (255, 255, 255)

def setLedOFF(ledNumber):
    pixels[ledNumber-1] = (0, 0, 0)

def setAllLedsOFF():
    pixels.fill((0, 0, 0))



class previewThread(Thread):
    def __init__(self):
        Thread.__init__(self)

        self.previewStream = None
        self.preview_omx = None
        self.statusBit = False

        Thread.setName(self, 'previewThread')
        print("Create " + Thread.getName(self))

        subprocess.Popen('mkfifo fifo.mjpg', shell=True, stdout=False, stdin=subprocess.PIPE)

        # Kill all gphoto2 processes
        subprocess.Popen('killall /usr/lib/gvfs/gvfs-gphoto2-volume-monitor', shell=True, stdout=False, stdin=False)
        subprocess.Popen('killall /usr/lib/gvfs/gvfsd-gphoto2', shell=True, stdout=False, stdin=False)

        setLedDefault()

    def run(self):

        if not self.statusBit:

            self.statusBit = True

            self.previewStream = subprocess.Popen('gphoto2 --capture-movie --stdout > fifo.mjpg', shell=True,
                                                  stdin=subprocess.PIPE)

            self.preview_omx = subprocess.Popen('omxplayer --layer 2 -b --live fifo.mjpg', shell=True,
                                                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            time.sleep(5)

    def stop(self):

        try:
            self.preview_omx.stdin.write('q')
        except:
            print("\npreview STOP\n")

        os.system('killall gphoto2')

        self.statusBit = False


def countdown(previewThread):
    for i in range(10, 0, -1):

        if (i == 1):
            # TODO stopo preview Thread  and capture
            setLedWhite(i + 1)
            previewThread.stop()
            time.sleep(1)

            print("Preview Thread stoped")

            return capture()
        else:
            try:
                setLedWhite(i+1)
                counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 3 -t 1000 ' + counterPath + str(i) + '.png'

                subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE).wait()
            except:
                print("Error programm pngview or counter file not found")


def capture():
    #hashedName = hashlib.md5(str(random.random())).hexdigest()

    date = time.strftime("%Y-%m-%d-%H-%M-%S")
    #fileName = date + str(hashedName) + imageFileType
    fileName = date + imageFileType


    captureCommmand = "gphoto2 --keep --capture-image-and-download --stdout > " + fileName

    setAllLedsOFF()

    ledController = ledControl()

    ledController.start()

    subprocess.Popen(captureCommmand, shell=True, stdout=False, stdin=False).wait()

    ledController.stop()

    setLedWhite(1)
    setLedWhite(12)

    return fileName



def showImage(imageFile):
    # x is for borderless
    # F is for fullscreen
    # Y is for without pointer
    fehSubProcess = subprocess.Popen(['feh', '-xFY', '/home/pi/' + imageFile], shell=False, stdout=False, stdin=subprocess.PIPE)


    return fehSubProcess


def checkButtons():
    inputCommand = ""
    if (captureButton.wait_for_press() or saveButton.wait_for_press() or abortButton.wait_for_press()):
        if (captureButton.is_pressed):
            inputCommand = 'c'
            captureButton.wait_for_release()

        elif (saveButton.is_pressed):
            inputCommand = 's'
            saveButton.wait_for_release()

        elif (abortButton.ispressed):
            inputCommand = 'a'
            saveButton.wait_for_release()
        else:
            inputCommand = "nothing"

    return inputCommand


if __name__ == '__main__':
    print("Start PhotoBox")
    atexit.register(exit_handler)

    myPreviewThread = previewThread()

    holtCameraThread = holtCamera()



    myPreviewThread.start()
    imageFile = ""
    while True:
        # Empty the Input
        inputCommand = ""

        imagePath = imageDir + imageFile
        imageExists = os.path.isfile(imagePath)

        if (imageExists):

            displayedImage = showImage(imageFile)
            print("Please press \n-c- to capture a new one\n-s- to save the photo  \n-a- for abord")

            # inputCommand = checkButtons()

            try:
                inputCommand = input()

            except:
                pass

            displayedImage.kill()
            # TODO holtCamera Thread start
            myPreviewThread.run()

        else:
            print("Please press \n-c- to capture a new one\n-s- to save the photo  \n-a- for abord")
            try:
                inputCommand = input()

            except:
                pass

            # inputCommand = checkButtons()

        if (inputCommand == 'c'):

            print("start Countdown")
            imageFile = countdown(myPreviewThread)

        elif (inputCommand == 's'):
            if (imageExists):
                # TODO eventuell speicherpfad einfuegen
                pass

            else:
                print("No Image File")

            # Empty the imageFile Name
            imageFile = ""

        elif (inputCommand == 'a'):
            print("Delete the Image")
            os.remove(imagePath)
            # Empty the imageFile Name
            imageFile = ""


        elif (inputCommand == 'q'):
            myPreviewThread.stop()
            setAllLedsOFF()
            exit(1)

        else:
            print("Wrond Input")

