'''
    This is a PhotoBox Software

    @author Lars Stratmann
    @Version 2.0
    @modified: 29.09.2019

    What does the Program:
        This Software capture a Image with a camera over the USB port.
        After pressing the "start" button the Countdown starts and a preview Video stream starts.
        On the screen are the Countdown numbers transparent png images.
        If the Countdown is at 2 the preview Stream close an d the camera start focusing and capture the image.
        The captured Image will show on the Screen.
        If "abort" is pressed the Image will not be saved.
        If "recapture" is pressed the Image will be saved and the Countdown starts again.
        If "start" is pressed the Image will be saved and the preview video stream starts.

        After X time the screensaver starts and the preview Image or the preview video stream stops.

        Optional:
            The countdown can expand with an LED ring

    Functions:
        The Program is in 4 Threads splited, camera Control, ScreenSaver, LedControl and Countdown

        The Camera Thread start and stop the preview Viedo stream and start the Capturing.

        The ScreenSaver start after X Time inactive, and call a stop function in the Camera Thread

        The Countdown print transparent PNGs on the top Screen layer and call a start capturing function in the Camera Thread.

        The LedControl expands the the Countdown


    Hardware:
        Raspberry Pi 3+
        LCD Screen
        Nikon XXX
        Adafruit LED RGB Ring

    Requires:
        Remove for easy workflow
        bash sudo rm /usr/share/dbus-1/services/org.gtk.vfs.GPhoto2VolumeMonitor.service
        sudo rm /usr/share/gvfs/mounts/gphoto2.mount
        sudo rm usr/share/gvfs/remote-volume-monitors/gphoto2.mount
        sudo rm /usr/lib/gvfs/gvfs-gphoto2-volume-monitor
        sudo rm /usr/lib/gvfs/gvfsd-gphoto2


    TODO exception picture screen saver between each picture change, if nothing is found print no picture

    TODO please smile picture for the 2 seconds before taking the picture

    TODO LedControl

    TODO pngview check implement
'''

from threading import Thread, Event, Lock
import time
import subprocess
import os
from sys import path
import signal
import glob
import atexit
import random
from PIL import Image
from gpiozero import Button
import board
import neopixel



# boolean for Develop Modus
devModus = False

threads = {}
captured = False
#imageDirectory = "/home/pi/Pictures/"
imageDirectory = "/home/pi/server/"
imageFileType = "jpg"
lastCapturedImage = ""

noImageCapturedInfo = path[0] + "/" + "Files/keinFotofuerDich2.jpg"
noImageFound = path[0] + "/" + "Files/noImageFound.jpg"


saveOnServer = False
serverImageDirectory = "/home/pi/server/"


# The Time how long a picture will be show
diashowTime = 5


captureButton = Button(27)
reCaptureButton = Button(17)
abortButton = Button(22)

# in seconds
screenSaverStartTime = 120

pictureLocationLock = Lock()
capturedEvent = Event()



# Subprocess preview
picturePreviewSubProcess = None

# LED initial
ledCyclePin = board.D18
ORDER = neopixel.GRB


def exit_handler():
    print('My application is ending!')
    threads["Camera"].stop_preview()
    threads["ScreenSaver"].stop_screen_saver()

    #threads["LedRingControl"].stopLeds()

class Camera(Thread):
    global threads
    global capturedEvent

    startPreviewEvent = Event()

    finishCaptureEvent = Event()

    def __init__(self):
        Thread.__init__(self)

        Thread.setName(self, "Camera")

        self.startCapturing = False

        subprocess.Popen('mkfifo fifo.mjpg', shell=True, stdout=False, stdin=subprocess.PIPE).wait()

        # Kill all gphoto2 processe

        subprocess.Popen('killall /usr/lib/gvfs/gvfs-gphoto2-volume-monitor', shell=True, stdout=False, stdin=False).wait()
        subprocess.Popen('killall /usr/lib/gvfs/gvfsd-gphoto2', shell=True, stdout=False, stdin=False).wait()


    def run(self):
        while True:
            self.startPreviewEvent.wait()

            # preview
            self.start_video_preview_process()

            # wait for subProcess Camera Stream closed
            self.videoPreviewSubProcess.wait()

            if(self.startCapturing):
                self.capture()

                # Das Event brauchen wir vllt nicht wenn wir die wait Funktion des Subprocess nutzen
                #self.finishCaptureEvent.wait()

                # wait for subProcess Picture Preview closed
                self.picturePreviewSubProcess.wait()


    def start_preview(self):
        self.startPreviewEvent.set()

    def stop_preview(self):
        self.startPreviewEvent.clear()

        try:
            self.stop_video_preview_process()
        except:
            pass
        #if(self.pucturePreviewSubProcess != None):
        try:
            self.stop_picture_preview_process()
        except:
            pass

    def start_capturing(self):

        self.startCapturing = True

        self.stop_video_preview_process()



    def is_set(self):
        return self.startPreviewEvent.is_set()

    def start_picture_preview_process(self):

        if(lastCapturedImage != noImageCapturedInfo):

            picturePreviewCommand = "feh -xFY " + imageDirectory + lastCapturedImage
        else:
            picturePreviewCommand = "feh -xFY " + lastCapturedImage

        # The os.setsid() is passed in the argument preexec_fn so
        # it's run after the fork() and before  exec() to run the shell.
        self.picturePreviewSubProcess = subprocess.Popen(picturePreviewCommand, shell=True, preexec_fn=os.setsid)

        print("Start Picture preview")


    def stop_picture_preview_process(self):

        # Send the signal to all the process groups
        os.killpg(os.getpgid(self.picturePreviewSubProcess.pid), signal.SIGTERM)
        print("Stop Picture preview")


    # local function
    def start_video_preview_process(self):

        # Subprocess Preview Stream

        if(devModus):
            videoPreviewCommand = "feh '" + imageDirectory + "pre.jpg'"

        else:
            videoPreviewCommand = "gphoto2 --capture-movie --stdout > fifo.mjpg & omxplayer --layer 2 -b --live fifo.mjpg"

        # The os.setsid() is passed in the argument preexec_fn so
        # it's run after the fork() and before  exec() to run the shell.
        self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid)

        print("Start Camera preview")

        #Event().wait(0.3)


    # local function
    def stop_video_preview_process(self):

        # Stop Subprocess Preview Stream
        os.killpg(os.getpgid(self.videoPreviewSubProcess.pid), signal.SIGTERM)

        print("Stop Camera video preview")


    # local function
    def capture(self):
        global captured
        global lastCapturedImage
        global capturedEvent

        self.startCapturing = False

        Event().wait(1)
        threads["LedRingControl"].stop_led_countdown_event()
        threads["LedRingControl"].start_led_wait_event()

        # Subprocess Camera Capturing
        date = time.strftime("%Y-%m-%d-%H-%M-%S")
        # fileName = date + str(hashedName) + imageFileType
        lastCapturedImage = date + "." + imageFileType

        captureCommmand = "gphoto2 --keep --capture-image-and-download --stdout > " + imageDirectory + lastCapturedImage

        subprocess.Popen(captureCommmand, shell=True, stdout=False, stdin=False).wait()
        captured = True


        try:

            checkImg = Image.open(imageDirectory + lastCapturedImage)
            print("Image captured")

        except:
            print("Image cant captured")
            os.remove(imageDirectory + lastCapturedImage)

            lastCapturedImage = noImageCapturedInfo


        # start preview Subprocess
        self.start_picture_preview_process()

        capturedEvent.set()


class ScreenSaver(Thread):
    global threads
    startScreenSaverEvent = Event()
    diashowDelayEvent = Event()



    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "ScreenSaver")

        self.startScreenSaverEvent.set()
        self.lastInteraction = time.time()


    def run(self):
        while True:
            self.startScreenSaverEvent.wait(screenSaverStartTime - (time.time() - self.lastInteraction))

            if(time.time() - self.lastInteraction  > screenSaverStartTime):
                self.start_screen_saver()

            if(self.startScreenSaverEvent.is_set()):
                self.diashow()

    def start_screen_saver(self):
        global captured

        self.startScreenSaverEvent.set()
        self.diashowDelayEvent.clear()

        # Save Image
        saveImage()

        captured = False

        threads['Camera'].stop_preview()

    def stop_screen_saver(self):
        self.startScreenSaverEvent.clear()
        self.diashowDelayEvent.set()

    def is_set(self):
        return self.startScreenSaverEvent.is_set()

    def update_last_interaction(self):
        self.lastInteraction = time.time()

    def diashow(self):
        global diashowTime


        self.globalPictures = glob.glob(imageDirectory + '*.' + imageFileType)

        while not self.diashowDelayEvent.is_set():

            if(len(self.globalPictures) == 0):
                imageViewCommand = 'feh -xFY ' + noImageFound

            else:
                #imageViewCommand = 'feh -xFY ' + tmpDisplayImage
                #imageViewCommand = 'raspidmx/pngview/pngview -b 0 -l 3 -t 10000 ' + tmpDisplayImage

                imageViewCommand = 'cd ' + imageDirectory + '; feh -xFYz -D ' + str(diashowTime)

            pro = subprocess.Popen(imageViewCommand, shell=True, preexec_fn=os.setsid)

            self.diashowDelayEvent.wait()
            os.killpg(os.getpgid(pro.pid), signal.SIGTERM)

    def stock_photos(self):
        pass


class LedRingControl(Thread):
    global threads

    ledEvents = Event()

    ledCountdownEvent = Event()
    ledWaitEvent = Event()
    ledRandomEvent = Event()

    # TODO add LED variables
    ledPixels = 24

    pixels = neopixel.NeoPixel(ledCyclePin, ledPixels)

    startindex = 1
    endindex = 23

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "LedRingControl")
        self.pixels.fill((0,0,0))



    def run(self):

        #self.led_ring_function_rainbow_cycle(0.001)
        #self.led_ring_function_countdown()
        while True:

            self.ledEvents.wait()
            if self.ledCountdownEvent.is_set():

                self.led_ring_function_countdown(10, 0.5)
                self.stop_led_countdown_event()
                self.stop_led_events()

            if self.ledWaitEvent.is_set():
                self.smile(0.3, 0.2)
                #self.led_ring_function_rainbow_cycle(0.01, 0.5)
                self.stop_led_wait_event()
                self.stop_led_events()

            if self.ledRandomEvent.is_set():
                self.led_random_functions()
                self.stop_led_random_event()
                self.stop_led_events()

    # local
    def increase_led_ring(self):
        pass

    # local
    def reset_led_ring(self):
        pass

    def start_led_events(self):
        self.ledEvents.set()

    def stop_led_events(self):
        self.ledEvents.clear()

    def stop_all_led_events(self):
        self.ledEvents.clear()
        self.ledCountdownEvent.clear()
        self.ledWaitEvent.clear()
        self.ledRandomEvent.clear()

    def start_led_wait_event(self):
        self.start_led_events()
        self.ledWaitEvent.set()

    def stop_led_wait_event(self):
        self.ledWaitEvent.clear()

    def start_led_countdown_event(self):
        self.start_led_events()
        self.ledCountdownEvent.set()

    def stop_led_countdown_event(self):
        self.ledCountdownEvent.clear()

    def start_led_random_event(self):
        self.start_led_events()
        self.ledRandomEvent.set()

    def stop_led_random_event(self):
        self.ledRandomEvent.clear()

    def led_ring_function_countdown(self, countdown, brightness):

        startindex = self.startindex
        endindex = self.endindex
        #self.pixels.fill((50,0,0))
        while countdown >= 0 and self.ledCountdownEvent.is_set():
            if startindex != 6 and startindex != 12 and endindex != 18 and endindex != 24:
                self.pixels[startindex] = (255, 255, 255)
                self.pixels[endindex] = (255, 255, 255)
                self.pixels.brightness = brightness
                Event().wait(1)
            countdown -= 1
            startindex += 1
            endindex -= 1

        #Event().wait(1)
        self.pixels.fill((0,0,0))


        # TODO wait for: capture finished

    def led_ring_function_rainbow_cycle(self, wait, brightness):
        r = 0
        g = 0
        b = 0
        steps = 20
        reverse = False
        mini = 30
        while self.ledWaitEvent.is_set():
            for i in range(self.ledPixels):
                self.pixels[i] = (r, g, b)
                self.pixels.brightness = brightness
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
        self.pixels.fill((0,0,0))

    # created by Marius Petersen
    def sub(self, sys, val):
        if val > 2 * sys + 1:
            return val - (2 * sys + 1)
        elif val > sys:
            return val - sys
        elif val < 0:
            return val + sys + 1
        else:
            return val

    # created by Marius Petersen
    def smile(self, wait, brightness):
        bright = int(255 * brightness)
        self.pixels.brightness = brightness
        self.pixels[3] = (0, 0, bright)
        self.pixels[21] = (0, 0, bright)
        tmp = 11
        for j in range(4):
            for i in range(3 + 2 * j):
                self.pixels[i + tmp] = (bright, bright, bright)
                self.pixels.brightness = brightness
            time.sleep(wait)
            tmp = tmp - 1
        time.sleep(wait)
        self.pixels[3] = (0, 0, 0)
        self.pixels[21] = (0, 0, 0)
        time.sleep(0.2)
        self.pixels[3] = (0, 0, bright)
        self.pixels[21] = (0, 0, bright)
        time.sleep(0.6)
        self.pixels[3] = (0, 0, 0)
        self.pixels[21] = (0, 0, 0)
        time.sleep(0.2)
        self.pixels[3] = (0, 0, bright)
        self.pixels[21] = (0, 0, bright)
        time.sleep(0.6)
        self.pixels.fill((0,0,0))

    # created by Marius Petersen
    def wheelRed(self, wait, brightness):
        for i in range(23):
            if not self.ledRandomEvent.is_set():
                break
            for j in range(23):
                if not self.ledRandomEvent.is_set():
                    break
                k = int(255 / (j ** 2 + 1))
                self.pixels[sub(23, i - j)] = (k, 0, 0)
                self.pixels.brightness = brightness
            time.sleep(wait)

    # created by Marius Petersen
    def wheel3(self, wait, fade, brightness):
        bright = 255  # zwischen 0 und 255
        # fade zwischen 1 und 3
        for i in range(23):
            if not self.ledRandomEvent.is_set():
                break
            for j in range(23):
                if not self.ledRandomEvent.is_set():
                    break
                k1 = int(bright / (j ** fade + 1))
                k2 = int(bright / ((j + 16) ** fade + 1))
                k3 = int(bright / ((j + 8) ** fade + 1))
                if j > 7:
                    k2 = int(bright / ((j - 8) ** fade + 1))
                if j > 15:
                    k3 = int(bright / ((j - 16) ** fade + 1))
                pixels[sub(23, i - j)] = (k1, k2, k3)
                self.pixels.brightness = brightness
            time.sleep(wait)

    # created by Marius Petersen
    def wheel4(self, wait, brightness):
        self.pixels.fill((0, 0, 0))
        self.pixels.brightness = brightness
        for i in range(5):
            if not self.ledRandomEvent.is_set():
                break
            k = int(255 / (i ** 2 + 1))
            self.pixels[0 + i] = (255, 0, 0)
            for j in range(i):
                if not self.ledRandomEvent.is_set():
                    break
                self.pixels[0 + j] = ((j + 1) * k, 0, 0)
            self.pixels[6 + i] = (0, 255, 0)
            for j in range(i):
                if not self.ledRandomEvent.is_set():
                    break
                self.pixels[6 + j] = (0, (j + 1) * k, 0)
            self.pixels[12 + i] = (0, 0, 255)
            for j in range(i):
                if not self.ledRandomEvent.is_set():
                    break
                self.pixels[12 + j] = (0, 0, (j + 1) * k)
            self.pixels[18 + i] = (0, 0, 255)
            for j in range(i):
                if not self.ledRandomEvent.is_set():
                    break
                self.pixels[18 + j] = ((j + 1) * k, 0, (j + 1) * k)
            time.sleep(wait)

    def led_random_functions(self):
        while self.ledRandomEvent.is_set():
            #rand = random.randrange(1, 3)
            rand = 1
            if rand == 1:
                self.wheelRed(0.3, 0.6)
            elif rand == 2:
                self.wheel3(0.2, 1.2, 0.6)
            elif rand == 3:
                self.wheel4(0.6, 0.6)
        self.pixels.fill((0, 0, 0))

    def set_led_color(self, ledNumber, rgb):
        self.pixels[ledNumber] = (rgb[0], rgb[1], rgb[2])

    def set_led_on(self, ledNumber):
        pass

    def set_led_off(self, ledNumber):
        pass


class Countdown(Thread):
    global threads
    countdownEvent = Event()

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "Countdown")


    def run(self):
        while True:
            self.countdownEvent.wait()

            if(threads["Camera"].is_set()):
                #self.countdown(10)
                threads["LedRingControl"].start_led_countdown_event()
                self.countdown(10)

    def start_countdown(self):
        self.countdownEvent.set()
        #time.sleep(0.3)
        self.countdownEvent.clear()

    # local function
    def countdown(self, time):
        for i in range(time, 0, -1):

            try:
                if (i == 2):
                    # Der Boolean wird auf True gesetzt es wird auf das wait vom Preview stream Subprocess gewartet
                    threads["Camera"].start_capturing()

                if (i == 1):
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0x000F -l 3 -t 3000 ' + path[0] + "/Files/smilePictures/pleaseSmile.png"

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE)
                elif(devModus):
                    print("Picture: " + str(i))
                    Event().wait(1)
                else:
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 4 -t 1000 ' + path[0] + "/Files/counterPictures/counterWhite/" + str(i) + '.png'

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE).wait()

            except:
                print("Error programm pngview or counter file not found")



def getButton():
    inputCommand = ""


    while(inputCommand == ""):

        Event().wait(0.1)

        if (captureButton.is_pressed):
            inputCommand = 'c'
            captureButton.wait_for_release()

        if (reCaptureButton.is_pressed):
            inputCommand = 'r'
            reCaptureButton.wait_for_release()

        if (abortButton.is_pressed):
            inputCommand = 'a'
            abortButton.wait_for_release()


    return inputCommand

def saveImage():
    global lastCapturedImage
    if(lastCapturedImage != noImageCapturedInfo):

        try:
            if(saveOnServer):
                os.rename(imageDirectory + lastCapturedImage, serverImageDirectory + lastCapturedImage)

            print("Image saved")
        except:
            print("Error: Image cant be moved")

    lastCapturedImage = ""

def deleteImage():
    global lastCapturedImage

    if(lastCapturedImage != noImageCapturedInfo):

        try:
            os.remove(imageDirectory + lastCapturedImage)
            print("Image delete")
        except:
            print("Error: Image cant be delete")

        Event().wait(1)

    lastCapturedImage = ""

if __name__ == '__main__':

    # if the program close all processes will be closed
    atexit.register(exit_handler)
    signal.signal(signal.SIGINT, exit_handler)


    blackBackgroundCommand = 'feh -xFY ' + path[0] + '/Files/black.jpg'
    subprocess.Popen(blackBackgroundCommand, shell=True, stdout=False, stdin=subprocess.PIPE)


    Event().wait(10)

    cameraThread = Camera()
    cameraThread.start()

    countdownThread = Countdown()
    countdownThread.start()

    screenSaverThread = ScreenSaver()
    screenSaverThread.start()

    ledRing1Thread = LedRingControl()
    ledRing1Thread.start()

    # TODO documentation fehlt, was macht das thread.update

    threads.update({cameraThread.getName(): cameraThread})
    threads.update({countdownThread.getName(): countdownThread})
    threads.update({screenSaverThread.getName(): screenSaverThread})
    threads.update({ledRing1Thread.getName(): ledRing1Thread})

    #threads["LedRingControl"].start_led_countdown_event()

    #Event.wait(10)

    #threads["LedRingControl"].stop_led_countdown_event()



    # Main Event
    while True:
        button = getButton()
        #button = input("Please enter: ")
        screenSaverThread.update_last_interaction()

        if(screenSaverThread.is_set()):
            screenSaverThread.stop_screen_saver()

            cameraThread.start_preview()

        elif(button == "c"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                # Save Image
                saveImage()

                captured = False

            else:
                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()


        elif(button == "r"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                # Save Image
                saveImage()

                captured = False

                Event().wait(1)

                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()


        elif(button == "a"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                deleteImage()
                captured = False

        else:
            print("Wrong Input")
