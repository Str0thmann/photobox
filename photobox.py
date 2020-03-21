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
        Remove for easy workflow, cause so the camera did not start automaticly
        bash sudo rm /usr/share/dbus-1/services/org.gtk.vfs.GPhoto2VolumeMonitor.service
        sudo rm /usr/share/gvfs/mounts/gphoto2.mount
        sudo rm usr/share/gvfs/remote-volume-monitors/gphoto2.mount
        sudo rm /usr/lib/gvfs/gvfs-gphoto2-volume-monitor
        sudo rm /usr/lib/gvfs/gvfsd-gphoto2



    Logging:
        Debug:
            - entering and leaving from Events
        INFO:
            - make a picture status
            -
        WARNING:
            - Could not connect to Server
            - could not make a picture -> reason
            - could not save the image, cause not enough space

        Critical:
            - no camera found
            - libarys not found


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
import sys
import signal
import glob
import atexit
import random
from PIL import Image
from gpiozero import Button
import board
import neopixel
import gphoto2 as gp
import logging
import io
import logging



# setup Logging
logging.basicConfig(filename=str(os.path.dirname(os.path.realpath(__file__))) + '/photobox.log', format='%(asctime)s %(lineno)d %(module)s %(funcName)s %(message)s', level=logging.DEBUG)


# boolean for Develop Modus
devModus = False

threads = {}
captured = False
imageDirectory = "/home/pi/Pictures/"
#imageDirectory = "/home/pi/server/"
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
videoPreviewEvent = Event()

# Subprocess preview
videoPreviewSubProcess = False

# LED initial
ledCyclePin = board.D18
ORDER = neopixel.GRB


def exit_handler():
    print('My application is ending!')
    threads["Camera"].stop_preview()
    threads["Camera"].close_all()
    threads["ScreenSaver"].stop_screen_saver()
    threads["LedRingControl"].turn_off_all()
    logging.info("photobox is closing")


class Camera(Thread):
    global threads
    global capturedEvent
    #global videoPreviewEvent

    logger = logging.getLogger(__name__)

    startPreviewEvent = Event()

    finishCaptureEvent = Event()

    def __init__(self):
        Thread.__init__(self)
        self.logger.info("initialisation")

        Thread.setName(self, "Camera")
        self.logger.info("name the Thread: Camera")


        self.startCapturing = False

        # Kill all gphoto2 processe

        subprocess.Popen('killall /usr/lib/gvfs/gvfs-gphoto2-volume-monitor', shell=True, stdout=False, stdin=False).wait()
        subprocess.Popen('killall /usr/lib/gvfs/gvfsd-gphoto2', shell=True, stdout=False, stdin=False).wait()

        #self.contex = gp.gp_context_new()
        #self.error, self.camera = gp.gp_camera_new()
        #self.error = gp.gp_camera_init(self.camera, self.contex)

        self._camera = gp.Camera()
        self._context = gp.gp_context_new()
        self._context_config = gp.check_result(gp.gp_camera_init(self._camera, self._context))

        self.logger.info("Camera initialized")

        #self._camera.init(self._context)

        self.logger.debug('Camera summary: %s', str(self._camera.get_summary(self._context)))


        #subprocess.Popen('mkfifo fifo.mjpg', shell=True, stdout=False, stdin=subprocess.PIPE).wait()


    def run(self):
        global videoPreviewEvent
        while True:
            self.logger.debug("wait for startPreviewEvent")
            self.startPreviewEvent.wait()

            # preview
            self._start_video_preview_process()

            # wait for subProcess Camera Stream closed
            self.logger.debug("wait for videoPreviewSubProcess")
            videoPreviewEvent.wait()

            if(self.startCapturing):
                self.logger.debug("start capturing")
                self.capture()

                # Das Event brauchen wir vllt nicht wenn wir die wait Funktion des Subprocess nutzen
                #self.finishCaptureEvent.wait()

                # wait for subProcess Picture Preview closed
                self.logger.debug("wait for picturePreviewSubProcess")
                self.picturePreviewSubProcess.wait()


    def start_preview(self):
        self.logger.debug("set startPreviewEvent -> it start")
        self.startPreviewEvent.set()

    def stop_preview(self):
        self.logger.debug("clear startPreviewEvent -> it wait")
        self.startPreviewEvent.clear()

        try:
            self.logger.debug("try _stop_video_preview_process")
            self._stop_video_preview_process()
        except Exception as e:
            self.logger.warning('error in _stop_video_preview_process, i dont know what happend: %s', e)
            pass
        #if(self.pucturePreviewSubProcess != None):
        try:
            self.logger.debug("try _stop_picture_preview_process")
            self._stop_picture_preview_process()
        except Exception as e:
            self.logger.warning('error in _stop_picture_preview_process, i dont know what happend: %s', e)
            pass

    def start_capturing(self):

        self.logger.debug("set startCapturing true -> it start")
        self.startCapturing = True

        self.logger.debug("execute _stop_video_preview_process function")
        self._stop_video_preview_process()


    def is_startPreviewEvent_set(self):
        self.logger.debug("return startPreviewEvent status: %s", self.startPreviewEvent.is_set())
        return self.startPreviewEvent.is_set()

    def start_captured_preview_process(self):

        if(lastCapturedImage != noImageCapturedInfo):

            picturePreviewCommand = "feh -xFY " + imageDirectory + lastCapturedImage
            self.picturePreviewSubProcess = subprocess.Popen(picturePreviewCommand, shell=True, preexec_fn=os.setsid)

        else:
            #picturePreviewCommand = "feh -xFY " + lastCapturedImage
            self.videoPreviewSubProcess.stdin.write("reload()".encode())

        # The os.setsid() is passed in the argument preexec_fn so
        # it's run after the fork() and before  exec() to run the shell.

        self.logger.debug("Start Picture preview")


    def _stop_picture_preview_process(self):

        # Send the signal to all the process groups

        self.videoPreviewSubProcess.stdin.write("quit()".encode())

        os.killpg(os.getpgid(self.picturePreviewSubProcess.pid), signal.SIGTERM)


        self.logger.debug("Stop Picture preview")


    # local function
    def _start_video_preview_process(self):
        global videoPreviewEvent
        self.logger.debug("enter the function")

        # Subprocess Preview Stream
        first = True


        self.logger.debug("Start Camera preview")
        self.logger.debug("videoPreviewEvent: %s", videoPreviewEvent.is_set())

        if(devModus):
            videoPreviewCommand = "feh '" + imageDirectory + "pre.jpg'"
            self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid)

        else:
            while not videoPreviewEvent.is_set():
                #self.logger.debug("create preview Photo")

                camera_file = gp.check_result(gp.gp_camera_capture_preview(self._camera))

                data_file = gp.check_result(gp.gp_file_get_data_and_size(camera_file))

                image = Image.open(io.BytesIO(data_file))
                image.save("tmp.jpg")


                if first:
                    videoPreviewCommand = "pqiv --actions-from-stdin -fit tmp.jpg"
                    self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid,
                                                                stdin=subprocess.PIPE)
                    first = False
                else:
                    self.videoPreviewSubProcess.stdin.write("reload()".encode())


                time.sleep(0.05)

        self.logger.debug("set videoPreviewEvent")
        videoPreviewEvent.set()

    # local function
    def _stop_video_preview_process(self):
        global videoPreviewEvent

        videoPreviewEvent.clear()

        # Stop Subprocess Preview Stream
        if(devModus):
            os.killpg(os.getpgid(self.videoPreviewSubProcess.pid), signal.SIGTERM)
        else:
            self.videoPreviewSubProcess.stdin.write("quit()".encode())

        self.logger.debug("Stop Camera video preview")


    # local function
    def capture(self):
        global captured
        global lastCapturedImage
        global capturedEvent

        self.startCapturing = False

        #Event().wait(2)

        # Subprocess Camera Capturing
        date = time.strftime("%Y-%m-%d-%H-%M-%S")
        # fileName = date + str(hashedName) + imageFileType
        lastCapturedImage = date + "." + imageFileType

        camera_file = gp.check_result(gp.gp_camera_capture(self._camera, gp.GP_CAPTURE_IMAGE))

        data_file = gp.check_result(gp.gp_camera_file_get(self._camera, camera_file.folder, camera_file.name, gp.GP_FILE_TYPE_NORMAL))

        data_file = gp.check_result(gp.gp_file_get_data_and_size(data_file))

        image = Image.open(io.BytesIO(data_file))
        image.save((imageDirectory + lastCapturedImage))


        #captureCommmand = "gphoto2 --keep --capture-image-and-download --stdout > " + imageDirectory + lastCapturedImage

        #subprocess.Popen(captureCommmand, shell=True, stdout=False, stdin=False).wait()
        captured = True

        try:

            checkImg = Image.open(imageDirectory + lastCapturedImage)
            self.logger.debug("Image captured correctly")
            image.save("tmp.jpg")

        except Exception as e:
            self.logger.debug("Image cant captured: %s", e)
            os.remove(imageDirectory + lastCapturedImage)

            lastCapturedImage = noImageCapturedInfo


        # start preview Subprocess
        self.start_captured_preview_process()

        capturedEvent.set()


    def close_all(self):
        self._camera.exit()

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

    ledCountdownEvent = Event()

    # TODO add LED variables
    ledPixels = 24

    pixels = neopixel.NeoPixel(ledCyclePin, ledPixels)

    startindex = 1
    endindex = 23

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "LedRingControl")


    def run(self):

        self.led_ring_function_rainbow_cycle(0.001)

        while True:
            self.ledCountdownEvent.wait()

            self.led_ring_function_countdown(10)
            #self.led_ring_function_rainbow_cycle(10)


    # local
    def increase_led_ring(self):
        pass

    # local
    def reset_led_ring(self):
        pass

    def led_ring_function_countdown(self):

        # TODO break condition
        #while(countdown > 0):
            #self.increase_led_ring()
        for i in range(10, 0, -1):

            if False and self.startindex != 6 and self.startindex != 12 and self.endindex != 18 and self.endindex != 24:
                self.pixels[self.startindex] = (255, 255, 255)
                self.pixels[self.endindex] = (255, 255, 255)

                Event().wait(1)

            self.startindex += 1
            self.endindex -= 1


        # TODO wait for: capture finished

    def wheel(self, pos):
        # Input a value 0 to 255 to get a color value.
        # The colours are a transition r - g - b - back to r.
        if pos < 0 or pos > 255:
            r = g = b = 0
        elif pos < 85:
            r = int(pos * 3)
            g = int(255 - pos * 3)
            b = 0
        elif pos < 170:
            pos -= 85
            r = int(255 - pos * 3)
            g = 0
            b = int(pos * 3)
        else:
            pos -= 170
            r = 0
            g = int(pos * 3)
            b = int(255 - pos * 3)
        return (r, g, b) if ORDER == neopixel.RGB or ORDER == neopixel.GRB else (r, g, b, 0)
    '''
    def led_ring_function_rainbow_cycle(self, speed):
        # rgb LED got three, 8bit colors
        # red   0 - 255
        # green 0 - 255
        # blue  0 - 255
        red = 0
        green = 0
        blue = 0
        max = 255

        led =  0

        for j in range(255):
            for i in range(self.ledPixels):
                pixel_index = int()(i * 256 / self.ledPixels) + j
                self.pixels[i] = self.wheel(pixel_index & 255)
            self.pixels.show()
            time.sleep(speed)
    '''
    def led_ring_function_rainbow_cycle(self, wait):
        r = 0
        g = 0
        b = 0
        steps = 20
        reverse = False
        mini = 30
        for j in range(10):
            for i in range(self.ledPixels):
                self.pixels[i] = (r, g, b)
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
        self.pixels.fill((0, 0, 0))



    def start_led_countdown_event(self):
        self.ledCountdownEvent.set()

    def stop_led_countdown_event(self):
        self.ledCountdownEvent.clear()

    def set_led_color(self, ledNumber, rgb):
        self.pixels[ledNumber] = (rgb[0], rgb[1], rgb[2])

    def set_led_on(self, ledNumber):
        pass

    def set_led_off(self, ledNumber):
        pass

    def turn_off_all(self):
        self.pixels.fill((0, 0, 0))


class Countdown(Thread):
    global threads
    countdownEvent = Event()

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "Countdown")


    def run(self):
        while True:
            self.countdownEvent.wait()

            if(threads["Camera"].is_startPreviewEvent_set()):
                self.countdown(10)
                threads["LedRingControl"].start_led_countdown_event()

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
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 4 -t 2000 ' + path[0] + "/Files/smilePictures/pleaseSmile.png"

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE)

                if(devModus):
                    print("Picture: " + str(i))
                    Event().wait(1)
                else:
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 3 -t 1000 ' + path[0] + "/Files/counterPictures/counterWhite/" + str(i) + '.png'

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
                cameraThread._stop_picture_preview_process()

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
                cameraThread._stop_picture_preview_process()

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
                cameraThread._stop_picture_preview_process()

                deleteImage()
                captured = False

        else:
            print("Wrong Input")
